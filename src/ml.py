"""
ml.py  -  "Riskli sipariş" tahmin modeli.

Ne yapar?
    1) data/siparisler.csv'yi okur (yoksa gen_data ile üretir).
    2) 4 modeli (LR, RF, XGBoost, SVM) karşılaştırır:
         - hiperparametre ayarı (GridSearch, 3 katlı iç CV) her modelin kendi eğitim verisi içinde
         - 5 katlı çapraz doğrulama (CV) = dış sınama; ayar ve test birbirine karışmaz
         - zaman bölmesi: eski siparişlerle eğit, en yeni siparişlerle test et
         - "sadece tedarikçi adını bilen" baz çizgisiyle kıyas
    3) En iyi modeli kaydeder: models/risk_modeli.joblib
    4) risk_yuzdeleri(): yeni bir sipariş için HER tedarikçinin risk yüzdesini verir.
       KDS'deki 5. kriter ("sipariş riski") budur.

Çalıştırma:   python src/ml.py
"""

import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC
from xgboost import XGBClassifier

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "src"))
import config as cfg
import gen_data

warnings.filterwarnings("ignore")

VERI_YOLU = KOK / "data" / "siparisler.csv"
MODEL_YOLU = KOK / "models" / "risk_modeli.joblib"
SONUC_YOLU = KOK / "results" / "ml_sonuclar.csv"

# ---------------------------------------------------------------------------
# Modelin göreceği sütunlar: SADECE sipariş anında bilinenler.
# Gecikme, sorun oranı, kısmi teslim, iptal siparişten SONRA bilinir -> girdi olamaz (sızıntı olur).
# ---------------------------------------------------------------------------
KATEGORIK = ["kategori", "tedarikci", "yontem"]
SAYISAL = ["yogun_ay", "soguk_ay", "km", "log_miktar", "acil", "iskonto_yuzde", "sozlesme_gun"]
HEDEF = "riskli"


# ---------------------------------------------------------------------------
# 1) VERİ
# ---------------------------------------------------------------------------
def veri_yukle():
    """CSV yoksa üretir, sonra okur ve model için log_miktar ekler."""
    if not VERI_YOLU.exists():
        VERI_YOLU.parent.mkdir(exist_ok=True)
        gen_data.uret().to_csv(VERI_YOLU, index=False, encoding="utf-8-sig")
    df = pd.read_csv(VERI_YOLU, parse_dates=["tarih"])
    df["log_miktar"] = np.log1p(df["miktar"])        # miktar çok çarpık dağılır, log daha dengeli
    df["yogun_ay"] = df["ay"].isin(cfg.YOGUN_AYLAR).astype(int)   # ay sayısı doğrusal etki değil;
    df["soguk_ay"] = df["ay"].isin(cfg.SOGUK_AYLAR).astype(int)   # sezonu 0/1 işaretle
    return df.sort_values("tarih").reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2) MODELLER
# ---------------------------------------------------------------------------
def on_isleme(kategorik, sayisal):
    """Kategorikleri 0/1 sütunlara çevirir, sayısalları ölçekler."""
    adimlar = [("kat", OneHotEncoder(handle_unknown="ignore"), kategorik)]
    if sayisal:
        adimlar.append(("say", StandardScaler(), sayisal))
    return ColumnTransformer(adimlar)


def model_listesi():
    return {
        "Lojistik Regresyon": LogisticRegression(max_iter=2000),
        "Random Forest": RandomForestClassifier(
            n_estimators=300, min_samples_leaf=5, random_state=cfg.SEED, n_jobs=-1),
        "XGBoost": XGBClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8,
            eval_metric="logloss", random_state=cfg.SEED, n_jobs=-1),
        "SVM (RBF)": SVC(probability=True, random_state=cfg.SEED),
    }


# Hiperparametre ızgaraları (küçük tutuldu: 3000 satırda aşırı ayar overfit riski yaratır)
IZGARALAR = {
    "Lojistik Regresyon": {"logisticregression__C": [0.1, 1, 10]},
    "Random Forest": {"randomforestclassifier__max_depth": [4, 8, None],
                      "randomforestclassifier__min_samples_leaf": [5, 15]},
    "XGBoost": {"xgbclassifier__max_depth": [2, 3, 4],
                "xgbclassifier__n_estimators": [100, 200],
                "xgbclassifier__learning_rate": [0.05, 0.1]},
    "SVM (RBF)": {"svc__C": [0.5, 1, 5]},
}


def pipeline_olustur(model, kategorik=KATEGORIK, sayisal=SAYISAL, izgara=None):
    """
    Ön işleme + model. izgara verilirse model, GridSearch ile KENDİ eğitim verisi içinde
    (3 katlı iç CV) ayar yapar; dış test verisine hiç bakmaz.
    """
    pipe = make_pipeline(on_isleme(kategorik, sayisal), model)
    if izgara is None:
        return pipe
    ic_cv = StratifiedKFold(3, shuffle=True, random_state=cfg.SEED)
    return GridSearchCV(pipe, izgara, cv=ic_cv, scoring="roc_auc", n_jobs=-1)


# ---------------------------------------------------------------------------
# 3) DEĞERLENDİRME
# ---------------------------------------------------------------------------
def capraz_dogrulama(pipe, df, kategorik=KATEGORIK, sayisal=SAYISAL):
    """5 katlı tabakalı CV: AUC (her katta ayrı) ve Brier (olasılık kalitesi)."""
    cv = StratifiedKFold(5, shuffle=True, random_state=cfg.SEED)
    X, y = df[kategorik + sayisal], df[HEDEF]
    olasilik = cross_val_predict(pipe, X, y, cv=cv, method="predict_proba")[:, 1]

    aucler = [roc_auc_score(y.iloc[te], olasilik[te]) for _, te in cv.split(X, y)]
    return np.mean(aucler), np.std(aucler), brier_score_loss(y, olasilik)


def zaman_bolmesi(pipe, df, kategorik=KATEGORIK, sayisal=SAYISAL):
    """Eski %70 ile eğit, en yeni %30'u test et (gerçek hayata en yakın sınama)."""
    kesim = int(len(df) * 0.7)
    egitim, test = df.iloc[:kesim], df.iloc[kesim:]
    pipe.fit(egitim[kategorik + sayisal], egitim[HEDEF])
    olasilik = pipe.predict_proba(test[kategorik + sayisal])[:, 1]
    return roc_auc_score(test[HEDEF], olasilik)


def karsilastir(df):
    """Tüm modelleri + baz çizgisini değerlendirir, tablo döndürür."""
    satirlar = []

    # Baz çizgisi: sadece tedarikçi adı. ML bunun üstüne ne katıyor?
    baz = pipeline_olustur(LogisticRegression(max_iter=2000), ["tedarikci"], [])
    ort, std, brier = capraz_dogrulama(baz, df, ["tedarikci"], [])
    satirlar.append(("Baz çizgisi (sadece tedarikçi)", ort, std, brier,
                     zaman_bolmesi(baz, df, ["tedarikci"], [])))

    for ad, model in model_listesi().items():
        pipe = pipeline_olustur(model, izgara=IZGARALAR[ad])
        ort, std, brier = capraz_dogrulama(pipe, df)
        satirlar.append((ad, ort, std, brier,
                         zaman_bolmesi(pipeline_olustur(model, izgara=IZGARALAR[ad]), df)))

    return pd.DataFrame(satirlar, columns=["Model", "AUC (CV ort.)", "AUC (CV std)",
                                           "Brier", "AUC (zaman bölmesi)"]).round(3)


def kalibrasyon_tablosu(pipe, df):
    """
    Tahmin edilen risk yüzdesi gerçekle uyuşuyor mu?
    Siparişleri tahmin edilen riske göre 5 gruba böler; her grupta ortalama tahmin ile
    gerçekte riskli çıkan oran yan yana yazılır. Yakınsa model güvenilirdir.
    """
    cv = StratifiedKFold(5, shuffle=True, random_state=cfg.SEED)
    X, y = df[KATEGORIK + SAYISAL], df[HEDEF]
    tahmin = cross_val_predict(pipe, X, y, cv=cv, method="predict_proba")[:, 1]
    tablo = pd.DataFrame({"tahmin": tahmin, "gercek": y})
    tablo["grup"] = pd.qcut(tablo["tahmin"], 5, labels=False, duplicates="drop") + 1
    return tablo.groupby("grup").agg(ort_tahmin=("tahmin", "mean"),
                                     gercek_oran=("gercek", "mean"),
                                     adet=("gercek", "size")).round(3)


# ---------------------------------------------------------------------------
# 4) KDS İÇİN: BİR SİPARİŞ İÇİN HER TEDARİKÇİNİN RİSK YÜZDESİ
# ---------------------------------------------------------------------------
def siparis_satirlari(kategori, miktar, ay, acil):
    """Seçilen kategorideki her tedarikçi için modele girecek bir satır hazırlar."""
    kat = cfg.KATEGORILER[kategori]
    aralik = gen_data.sac_teslim_araligi(miktar) if kategori == "Sac" else kat["teslim_gun"]
    sozlesme = (aralik[0] + aralik[1]) / 2
    if acil:
        sozlesme = max(1, sozlesme // 2)

    satirlar = []
    for ad in kat["tedarikciler"]:
        ted = cfg.TEDARIKCILER[ad]
        satirlar.append(dict(
            kategori=kategori, tedarikci=ad, yontem=ted["yontem"], km=ted["km"],
            yogun_ay=int(ay in cfg.YOGUN_AYLAR), soguk_ay=int(ay in cfg.SOGUK_AYLAR),
            log_miktar=np.log1p(miktar), acil=int(acil),
            iskonto_yuzde=gen_data.iskonto_orani(kat, miktar, ted), sozlesme_gun=sozlesme))
    return pd.DataFrame(satirlar)


def risk_yuzdeleri(model, kategori, miktar, ay, acil=False):
    """Tedarikçi -> risk yüzdesi (0-100). Streamlit ve TOPSIS bunu kullanır."""
    satirlar = siparis_satirlari(kategori, miktar, ay, acil)
    olasilik = model.predict_proba(satirlar[KATEGORIK + SAYISAL])[:, 1].astype(float)
    return pd.Series(olasilik * 100, index=satirlar["tedarikci"]).round(1)


def model_yukle():
    return joblib.load(MODEL_YOLU)


# ---------------------------------------------------------------------------
# ÇALIŞTIR
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    df = veri_yukle()
    print(f"Veri: {len(df)} sipariş, riskli oranı {df[HEDEF].mean():.3f}\n")

    sonuc = karsilastir(df)
    print(sonuc.to_string(index=False))
    SONUC_YOLU.parent.mkdir(exist_ok=True)
    sonuc.to_csv(SONUC_YOLU, index=False, encoding="utf-8-sig")

    # En iyi modeli (baz çizgisi hariç) CV AUC'ye göre seç ve tüm veriyle eğit
    en_iyi = sonuc.iloc[1:].sort_values("AUC (CV ort.)", ascending=False).iloc[0]["Model"]
    final = pipeline_olustur(model_listesi()[en_iyi], izgara=IZGARALAR[en_iyi])
    print(f"\nSeçilen model: {en_iyi}")

    print("\nKalibrasyon (tahmin edilen risk ile gerçek risk yakın olmalı):")
    print(kalibrasyon_tablosu(pipeline_olustur(model_listesi()[en_iyi], izgara=IZGARALAR[en_iyi]), df).to_string())

    final.fit(df[KATEGORIK + SAYISAL], df[HEDEF])
    print("Seçilen ayarlar:", final.best_params_)
    final = final.best_estimator_                    # sadece en iyi ayarlı pipeline kaydedilir
    MODEL_YOLU.parent.mkdir(exist_ok=True)
    joblib.dump(final, MODEL_YOLU)

    # Örnek: aynı sipariş normal ve acil
    print("\nÖRNEK: Sac, 900 kg, Nisan")
    for acil in (False, True):
        print(f"  acil={acil}:")
        print(risk_yuzdeleri(final, "Sac", 900, 4, acil).to_string())