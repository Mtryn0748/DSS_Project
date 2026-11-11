"""
mcdm.py  -  Çok kriterli karar: TOPSIS ve Gri İlişkisel Analiz (GİA) ile tedarikçi sıralama.

Akış (bir sipariş için):
    1) Kriter tablosu kurulur: her tedarikçi için 5 değer
         Efektif maliyet | İndirim | Teslimat süresi | Sözleşme uyumu | Sipariş riski (ML)
    2) AHP'nin persona ağırlıkları (ahp.py) alınır.
    3) TOPSIS ve GİA bu tabloyu ağırlıklarla sıralar.
    4) Spearman ile iki sıralamanın uyumu, duyarlılık analiziyle sıralamanın kararlılığı ölçülür.

Tek kaynak kategorilerde (vinç, kompozit) sıralama yapılmaz, uyarı döner.

Çalıştırma:   python src/mcdm.py      (3 demo senaryoyu yazar)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "src"))
import ahp
import config as cfg
import gen_data
import ml

KRITERLER = ahp.KRITERLER
YON = ahp.YON                      # 1 = küçük iyi (maliyet türü), 0 = büyük iyi (fayda türü)


# ---------------------------------------------------------------------------
# 1) KRİTER TABLOSU
# ---------------------------------------------------------------------------
def sozlesme_uyumu_hesapla():
    """
    Tedarikçinin geçmişte söze uyma oranı (%): gecikmesi eşiğin altında kalan siparişlerin payı.
    Geçmiş sipariş verisinden hesaplanır.
    """
    df = pd.read_csv(ml.VERI_YOLU)
    uyumlu = (df["gecikme_gun"] < cfg.GECIKME_ESIK_GUN)
    return (uyumlu.groupby(df["tedarikci"]).mean() * 100).round(1)


def efektif_maliyet(kat, ted_ad, miktar, yakit_carpani):
    """
    Nakliye dahil birim maliyet (TL / birim).
    yakit_carpani: 1.0 = bugünkü akaryakıt, 1.5 = %50 zam. Sadece kamyonetle gelenleri etkiler.
    """
    ted = cfg.TEDARIKCILER[ted_ad]
    iskonto = gen_data.iskonto_orani(kat, miktar, ted)
    kivirma = kat.get("kivirma_tl_kg", {}).get(ted_ad, 0.0)

    birim = kat["baz_fiyat"] * ted["fiyat_endeksi"] * (1 - iskonto / 100) + kivirma
    nakliye = gen_data.nakliye_maliyeti(ted, yakit_carpani)
    return birim + nakliye / miktar


def beklenen_teslimat(kat, kategori, ted, miktar, ay, acil):
    """Söz verilen süre + o tedarikçinin beklenen gecikmesi (gün)."""
    aralik = gen_data.sac_teslim_araligi(miktar) if kategori == "Sac" else kat["teslim_gun"]
    sozlesme = (aralik[0] + aralik[1]) / 2
    if acil:
        sozlesme = max(1, sozlesme // 2)
    return sozlesme + gen_data.beklenen_gecikme(ted, kat, miktar, ay, acil)


def kriter_tablosu(kategori, miktar, ay, acil=False, yakit_carpani=1.0, model=None):
    """Her tedarikçi için 5 kriter değeri. Satır = tedarikçi, sütun = kriter."""
    kat = cfg.KATEGORILER[kategori]
    model = model or ml.model_yukle()
    risk = ml.risk_yuzdeleri(model, kategori, miktar, ay, acil)
    uyum = sozlesme_uyumu_hesapla()

    satirlar = {}
    for ad in kat["tedarikciler"]:
        ted = cfg.TEDARIKCILER[ad]
        satirlar[ad] = [
            efektif_maliyet(kat, ad, miktar, yakit_carpani),
            gen_data.iskonto_orani(kat, miktar, ted),
            beklenen_teslimat(kat, kategori, ted, miktar, ay, acil),
            uyum[ad],
            risk[ad],
        ]
    return pd.DataFrame(satirlar, index=KRITERLER).T.round(2)


# ---------------------------------------------------------------------------
# 2) TOPSIS
# ---------------------------------------------------------------------------
def topsis(X, w):
    """
    TOPSIS: ideale en yakın, ideal-olmayana en uzak alternatif en iyidir.
    X: alternatifler x kriterler matrisi, w: ağırlıklar.
    Dönüş: her alternatif için yakınlık skoru (0-1, büyük iyi).
    """
    X = np.asarray(X, dtype=float)

    # a) Vektör normalizasyonu (kriterler farklı birimde, karşılaştırılabilir hale getirilir)
    bolen = np.sqrt((X ** 2).sum(axis=0))
    bolen[bolen == 0] = 1.0
    V = (X / bolen) * w

    # b) İdeal (en iyi) ve negatif ideal (en kötü) değerler; yöne göre seçilir
    ideal = np.where(YON == 1, V.min(axis=0), V.max(axis=0))
    negatif = np.where(YON == 1, V.max(axis=0), V.min(axis=0))

    # c) Her alternatifin ideale ve negatif ideale uzaklığı
    d_ideal = np.sqrt(((V - ideal) ** 2).sum(axis=1))
    d_negatif = np.sqrt(((V - negatif) ** 2).sum(axis=1))

    # d) Yakınlık: 1'e yakınsa ideale yakın
    toplam = d_ideal + d_negatif
    return np.where(toplam == 0, 0.5, d_negatif / np.where(toplam == 0, 1, toplam))


# ---------------------------------------------------------------------------
# 3) GRİ İLİŞKİSEL ANALİZ (GİA)
# ---------------------------------------------------------------------------
def gia(X, w, rho=0.5):
    """
    GİA: her alternatifin "ideal alternatife" ne kadar benzediğini ölçer.
    Dönüş: gri ilişkisel derece (0-1, büyük iyi).  rho: ayırt edicilik katsayısı (genelde 0.5).
    """
    X = np.asarray(X, dtype=float)

    # a) Normalizasyon: 0-1 arası, 1 = o kriterde en iyi. Hepsi aynıysa hepsi 1.
    en_az, en_cok = X.min(axis=0), X.max(axis=0)
    aralik = np.where(en_cok - en_az == 0, 1.0, en_cok - en_az)
    N = np.where(YON == 1, (en_cok - X) / aralik, (X - en_az) / aralik)
    N[:, (en_cok - en_az) == 0] = 1.0

    # b) İdeal diziden sapma (ideal = hep 1) ve gri ilişki katsayısı
    delta = np.abs(1 - N)
    d_min, d_max = delta.min(), delta.max()
    katsayi = (d_min + rho * d_max) / (delta + rho * d_max) if d_max > 0 else np.ones_like(delta)

    # c) Ağırlıklı ortalama = gri ilişkisel derece
    return (katsayi * w).sum(axis=1)


# ---------------------------------------------------------------------------
# 4) SIRALAMA, UYUM VE DUYARLILIK
# ---------------------------------------------------------------------------
def siralama_uyumu(skor_a, skor_b):
    """İki yöntemin sıralaması ne kadar aynı? Spearman: 1 = tamamen aynı, 0 = ilişkisiz."""
    if len(skor_a) < 3:
        return float("nan")
    return float(spearmanr(skor_a, skor_b).correlation)


def agirlik_duyarliligi(X, w, tekrar=1000, sapma=0.25, tohum=cfg.SEED):
    """
    Ağırlıklar biraz değişirse (her biri rastgele ±~%25) birinci sıradaki kim?
    Dönüş: tedarikçi sırasıyla "birinci çıkma oranı" (%). Tek ağırlık seti yerine
    karar vericinin belirsizliğine karşı sıralamanın ne kadar sağlam olduğunu gösterir.
    """
    rng = np.random.default_rng(tohum)
    birinci = np.zeros(len(X))
    for _ in range(tekrar):
        yeni = w * rng.lognormal(0, sapma, size=len(w))
        yeni = yeni / yeni.sum()
        birinci[np.argmax(topsis(X, yeni))] += 1
    return birinci / tekrar * 100


# ---------------------------------------------------------------------------
# 5) ANA FONKSİYON: bir sipariş için karar
# ---------------------------------------------------------------------------
def karar_ver(kategori, miktar, ay, persona, acil=False, yakit_carpani=1.0, model=None):
    """
    Dönüş: dict
        uyari   : tek kaynaksa mesaj, değilse None
        tablo   : kriter değerleri + TOPSIS + GİA skorları ve sıraları
        agirlik : kullanılan persona ağırlıkları
        spearman: iki yöntemin sıralama uyumu
        kararlilik: tedarikçi başına "birinci çıkma oranı" (%)
    """
    if cfg.tek_kaynak_mi(kategori):
        tek = cfg.KATEGORILER[kategori]["tedarikciler"][0]
        return dict(uyari=f"'{kategori}' için tek tedarikçi var ({tek}). Karşılaştırma yapılamaz; "
                          f"alternatif tedarikçi araştırılması önerilir.", tablo=None)

    tablo = kriter_tablosu(kategori, miktar, ay, acil, yakit_carpani, model)
    w, cr = ahp.agirlik(ahp.PERSONALAR[persona]["matris"])
    X = tablo[KRITERLER].values

    tablo["TOPSIS"] = topsis(X, w).round(3)
    tablo["GİA"] = gia(X, w).round(3)
    tablo["TOPSIS sıra"] = tablo["TOPSIS"].rank(ascending=False, method="min").astype(int)
    tablo["GİA sıra"] = tablo["GİA"].rank(ascending=False, method="min").astype(int)
    tablo = tablo.sort_values("TOPSIS", ascending=False)

    kararlilik = pd.Series(agirlik_duyarliligi(tablo[KRITERLER].values, w), index=tablo.index)
    return dict(uyari=None, tablo=tablo, agirlik={k: float(v) for k, v in zip(KRITERLER, w.round(3))}, cr=round(cr, 3),
                spearman=siralama_uyumu(tablo["TOPSIS"], tablo["GİA"]), kararlilik=kararlilik)


# ---------------------------------------------------------------------------
# DEMO: 3 senaryo
# ---------------------------------------------------------------------------
def yazdir(baslik, sonuc):
    print("\n" + "=" * 100 + f"\n{baslik}\n" + "=" * 100)
    if sonuc["uyari"]:
        print(sonuc["uyari"])
        return
    print(sonuc["tablo"].to_string())
    print(f"\nSpearman (TOPSIS ~ GİA): {sonuc['spearman']:.2f}   |   AHP CR: {sonuc['cr']}")
    print("Ağırlıklar:", sonuc["agirlik"])
    print("Birinci çıkma oranı (ağırlık değişirse, %):")
    print(sonuc["kararlilik"].round(1).to_string())


if __name__ == "__main__":
    model = ml.model_yukle()

    yazdir("SENARYO 1 - Normal sipariş: Sac 900 kg, Nisan, bütçe odaklı",
           karar_ver("Sac", 900, 4, "Bütçe odaklı (atölye sahibi)", model=model))

    yazdir("SENARYO 2 - Mazot zammı haberi (+%50): küçük sac siparişi, teslimat/risk öne çıkar",
           karar_ver("Sac", 300, 4, "Acil teslimat (mazot zammı / acil iş)", yakit_carpani=1.5, model=model))

    yazdir("SENARYO 3 - Acil iş: Sac 900 kg, acil teslimat odaklı",
           karar_ver("Sac", 900, 4, "Acil teslimat (mazot zammı / acil iş)", acil=True, model=model))

    yazdir("TEK KAYNAK: Vinç", karar_ver("Vinç", 1, 4, "Dengeli", model=model))