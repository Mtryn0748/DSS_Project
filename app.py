"""
app.py  -  Akıllı Tedarik ve Satın Alma Karar Destek Sistemi (Streamlit arayüzü)

Çalıştırma:   streamlit run app.py

Ön koşul: python src/gen_data.py  ve  python src/ml.py  bir kez çalıştırılmış olmalı
(veri ve eğitilmiş model oluşsun).

Arayüz sadece gösterir; hesaplamaların hepsi src/ klasöründeki dosyalarda:
    ml.py   -> sipariş risk yüzdesi
    ahp.py  -> persona ağırlıkları
    mcdm.py -> TOPSIS, GİA, Spearman, duyarlılık
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

KOK = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "src"))
import ahp
import config as cfg
import mcdm
import ml

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

# Sunumdaki 3 hazır senaryo: tek tıkla form dolar
SENARYOLAR = {
    "1) Normal sipariş": dict(kategori="Sac", miktar=900, ay=4, acil=False, zam=0,
                              persona="Bütçe odaklı (atölye sahibi)"),
    "2) Mazot zammı haberi": dict(kategori="Sac", miktar=300, ay=4, acil=False, zam=50,
                                  persona="Acil teslimat (mazot zammı / acil iş)"),
    "3) Acil iş": dict(kategori="Sac", miktar=900, ay=4, acil=True, zam=0,
                       persona="Acil teslimat (mazot zammı / acil iş)"),
}


# ---------------------------------------------------------------------------
# YARDIMCI
# ---------------------------------------------------------------------------
@st.cache_resource
def model_getir():
    """Eğitilmiş risk modelini bir kez yükler."""
    return ml.model_yukle()


def senaryoyu_uygula(ad):
    """Hazır senaryonun değerlerini forma yazar."""
    s = SENARYOLAR[ad]
    st.session_state.update(kategori=s["kategori"], miktar=float(s["miktar"]), ay=AYLAR[s["ay"] - 1],
                            acil=s["acil"], zam=s["zam"], persona=s["persona"])


def varsayilan_formu_kur():
    """Sayfa ilk açıldığında form değerlerini bir kez doldurur."""
    if "kategori" not in st.session_state:
        senaryoyu_uygula("1) Normal sipariş")


# ---------------------------------------------------------------------------
# SAYFA
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Tedarik Karar Destek Sistemi", layout="wide")
varsayilan_formu_kur()

if not ml.MODEL_YOLU.exists():
    st.error("Eğitilmiş model bulunamadı. Önce terminalde şunları çalıştır:\n\n"
             "`python src/gen_data.py` ve `python src/ml.py`")
    st.stop()

model = model_getir()

# --- Üst başlık + sağ üstte yakıt fiyatı ---
sol, sag = st.columns([4, 1])
with sol:
    st.title("Akıllı Tedarik ve Satın Alma Karar Destek Sistemi")
    st.caption("Korkuteli karoser atölyesi senaryosu  |  ML risk tahmini + AHP + TOPSIS + Gri İlişkisel Analiz")

# --- Kenar çubuğu: sipariş formu ---
with st.sidebar:
    st.header("Sipariş")

    st.caption("Hazır senaryolar")
    for ad in SENARYOLAR:
        st.button(ad, on_click=senaryoyu_uygula, args=(ad,), use_container_width=True)

    st.divider()
    kategori = st.selectbox("Ürün kategorisi", list(cfg.KATEGORILER), key="kategori")
    kat = cfg.KATEGORILER[kategori]
    en_az, tipik, en_cok = kat["miktar"]
    miktar = st.number_input(f"Miktar ({kat['birim']})", min_value=float(en_az), max_value=float(en_cok),
                             step=1.0 if kat["birim"] != "litre" else 0.5, key="miktar")
    ay_adi = st.selectbox("Sipariş ayı", AYLAR, key="ay")
    ay = AYLAR.index(ay_adi) + 1
    acil = st.checkbox("Acil sipariş", key="acil")

    st.divider()
    persona = st.selectbox("Karar verici profili (persona)", list(ahp.PERSONALAR), key="persona")
    st.caption(ahp.PERSONALAR[persona]["aciklama"])
    zam = st.slider("Akaryakıt zammı (%)", 0, 100, key="zam")

# --- Sağ üst: yakıt fiyatı (config'teki referans fiyat + senaryodaki zam) ---
yakit_carpani = 1 + zam / 100
with sag:
    yeni_fiyat = cfg.MOTORIN_TL_LITRE * yakit_carpani
    st.metric("Motorin (Antalya)", f"{yeni_fiyat:.2f} TL/L",
              delta=f"+%{zam}" if zam else None, delta_color="inverse")

# ---------------------------------------------------------------------------
# SONUÇ
# ---------------------------------------------------------------------------
sekme_karar, sekme_yontem = st.tabs(["Karar", "Yöntem ve veri"])

with sekme_karar:
    sonuc = mcdm.karar_ver(kategori, miktar, ay, persona, acil=acil, yakit_carpani=yakit_carpani, model=model)

    if sonuc["uyari"]:
        st.warning(sonuc["uyari"])
        st.stop()

    tablo = sonuc["tablo"]
    kazanan = tablo.index[0]
    ted = cfg.TEDARIKCILER[kazanan]

    st.success(f"**Önerilen tedarikçi: {kazanan}**  ({ted['sehir']}, {ted['km']} km, "
               f"{cfg.YONTEMLER[ted['yontem']].split(':')[0]})")

    a, b, c, d = st.columns(4)
    a.metric("Efektif maliyet", f"{tablo.loc[kazanan, 'Efektif maliyet']:.2f} TL/{kat['birim']}")
    b.metric("Beklenen teslimat", f"{tablo.loc[kazanan, 'Teslimat süresi']:.1f} gün")
    c.metric("Sipariş riski (ML)", f"%{tablo.loc[kazanan, 'Sipariş riski']:.1f}")
    d.metric("Ağırlık değişirse birinci kalma", f"%{sonuc['kararlilik'][kazanan]:.0f}")

    st.subheader("Tedarikçi karşılaştırması")
    goster = tablo.copy()
    goster.index.name = "Tedarikçi"
    st.dataframe(goster, use_container_width=True)

    g1, g2 = st.columns(2)
    with g1:
        st.caption("Yöntem skorları (büyük iyi)")
        st.bar_chart(tablo[["TOPSIS", "GİA"]])
    with g2:
        st.caption("ML sipariş riski (%)  -  küçük iyi")
        st.bar_chart(tablo[["Sipariş riski"]])

    st.subheader("Kriter ağırlıkları (AHP)")
    agirlik = pd.Series(sonuc["agirlik"], name="Ağırlık")
    st.bar_chart(agirlik)
    st.caption(f"Tutarlılık oranı CR = {sonuc['cr']}  (0,10'un altı tutarlı)")

    st.subheader("Yöntemler ne kadar uyumlu?")
    st.metric("Spearman (TOPSIS ~ GİA sıralaması)", f"{sonuc['spearman']:.2f}")
    st.caption("1'e yakınsa iki yöntem aynı sırayı veriyor. Düşükse yöntem seçimi sonucu etkiliyor; "
               "bu durumda TOPSIS'i ana, GİA'yı kontrol olarak okuyun.")

    st.subheader("Ağırlıklar biraz değişirse kim birinci çıkar?")
    st.bar_chart(sonuc["kararlilik"].rename("Birinci çıkma oranı (%)"))

with sekme_yontem:
    st.subheader("Verinin kaynağı")
    st.write(
        "Bu sistemdeki sipariş geçmişi **gerçek firmalara ait değildir**. `config.py` dosyasındaki varsayımlardan, "
        "`gen_data.py` ile üretilmiş **sentetik** veridir (3000 sipariş, 2024-01 / 2026-09). "
        "Fiyatlar güncel liste fiyatlarından, geçmiş fiyatlar TCMB aylık TÜFE değişimlerinden türetilmiştir. "
        "Sonuçlar gerçek tedarikçi performansı değil, **yöntemin gösterimidir**.")

    st.subheader("ML model karşılaştırması")
    if ml.SONUC_YOLU.exists():
        st.dataframe(pd.read_csv(ml.SONUC_YOLU), use_container_width=True, hide_index=True)
        st.caption("AUC: modelin riskli ve risksiz siparişi ayırt etme gücü (0,5 = şans, 1 = kusursuz). "
                   "Baz çizgisi sadece tedarikçi adını bilen modeldir.")
    else:
        st.info("Sonuç tablosu için `python src/ml.py` çalıştırın.")

    st.subheader("Kriterler")
    st.table(pd.DataFrame({"Kriter": ahp.KRITERLER,
                           "Yön": ["küçük iyi" if y else "büyük iyi" for y in ahp.YON]}))