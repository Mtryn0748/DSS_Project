"""
gen_data.py  -  Karoser atölyesi için SENTETİK geçmiş sipariş verisi üretir.

Girdi : config.py  (tüm rakamlar oradan okunur)
Çıktı : data/siparisler.csv

Çalıştırma:   python src/gen_data.py

Mantık (kısaca):
    1) Bir sipariş "sipariş anında bilinen" özelliklerle doğar
       (kategori, tedarikçi, miktar, tarih, acil mi, yakıt endeksi ...).
    2) Sonuç (gecikme, sorunlu ürün, kısmi teslim, iptal) bu özelliklerden
       ve RASTGELELİKTEN oluşur. Yani sonuç kuralla belirlenmez, olasılıkla çıkar.
    3) ML'in işi: sipariş anındaki bilgilerden "riskli mi?" tahmin etmek.

Bu veri gerçek firmaların verisi DEĞİLDİR; raporda "varsayımlara dayalı
sentetik veri" olarak belirtilmelidir.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# config.py bir üst klasörde
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as cfg


# ---------------------------------------------------------------------------
# Kategorilerin sipariş sıklığı (toplamı 1 olacak şekilde normalize edilir)
# ---------------------------------------------------------------------------
KATEGORI_AGIRLIK = {
    "Sac": 0.22, "Profil": 0.18, "Boya ve sarf": 0.20, "Aksesuar ve krom": 0.08,
    "Aydınlatma": 0.07, "Bağlantı elemanları": 0.15, "Vinç": 0.02, "Kompozit panel": 0.08,
}


# ---------------------------------------------------------------------------
# 1) YARDIMCI HESAPLAR
# ---------------------------------------------------------------------------
def tarih_agirliklari(gunler):
    """Yoğun aylarda daha çok sipariş gelir."""
    return np.array([1.5 if g.month in cfg.YOGUN_AYLAR else 1.0 for g in gunler])


def yakit_endeksi_uret(gunler, rng):
    """
    Günlük akaryakıt endeksi (başlangıç = 1.0).
    Yavaş yükselen bir trend + rastgele dalgalanma. Gerçek veri için ileride API bağlanabilir.
    """
    n = len(gunler)
    adimlar = rng.normal(0.0004, 0.006, n)          # günlük küçük değişim
    endeks = np.exp(np.cumsum(adimlar))
    return pd.Series(endeks, index=gunler)


def fiyat_katsayilari_hazirla():
    """
    TCMB aylık TÜFE değişimlerinden, her ay için fiyat katsayısı üretir.
    Veri bitişi ayı = 1.0 (config'teki fiyatlar o günün fiyatı). Geçmiş aylar daha ucuzdur.
    """
    aylar = sorted(cfg.TUFE_AYLIK)
    katsayi = {}
    seviye = 1.0
    for ay in reversed(aylar):                   # sondan başa doğru
        katsayi[ay] = seviye
        seviye /= 1 + cfg.TUFE_AYLIK[ay] / 100   # bir önceki ay daha ucuz
    return katsayi


FIYAT_KATSAYI = fiyat_katsayilari_hazirla()


def fiyat_katsayisi(tarih):
    return FIYAT_KATSAYI[tarih.strftime("%Y-%m")]


def miktar_uret(kat, rng):
    """Tipik miktar etrafında, en az/en çok sınırları içinde miktar."""
    en_az, tipik, en_cok = kat["miktar"]
    if en_az == en_cok:
        return en_az
    miktar = rng.lognormal(np.log(tipik), 0.7)
    miktar = float(np.clip(miktar, en_az, en_cok))
    return round(miktar, 1) if kat["birim"] == "litre" else int(round(miktar))


def iskonto_orani(kat, miktar):
    """Toplu alım indirimi (%). En yüksek geçerli kademe uygulanır."""
    oran = 0
    for esik, yuzde in kat["iskonto"]:
        if miktar >= esik:
            oran = yuzde
    return oran


def sac_teslim_araligi(miktar_kg):
    """Sac işleme süresi iş büyüklüğüne bağlı (kasa eşdeğeri)."""
    kasa = miktar_kg / cfg.KASA_KG
    for en_cok_kasa, aralik in cfg.SAC_TESLIM_KADEMELERI:
        if kasa <= en_cok_kasa:
            return aralik
    return cfg.SAC_TESLIM_KADEMELERI[-1][1]


def nakliye_maliyeti(ted, yakit_endeksi):
    """Bir seferlik taşıma maliyeti (TL)."""
    if ted["yontem"] == "kamyonet":
        km_maliyeti = cfg.KAMYONET_YAKIT_TL_KM * yakit_endeksi + cfg.KAMYONET_DIGER_TL_KM
        return 2 * ted["km"] * km_maliyeti
    if ted["yontem"] == "kargo":
        return cfg.KARGO_SABIT_TL
    return 0.0                                      # tedarikçi aracı: yol masrafı yok


# ---------------------------------------------------------------------------
# 2) SONUÇ ÜRETİMİ (gecikme ve sorun rastgele ama nedenlere bağlı)
# ---------------------------------------------------------------------------
def beklenen_gecikme(ted, kat, miktar, ay, acil):
    """Ortalama gecikme (gün). Gerçekleşen gecikme bunun etrafında rastgele çıkar."""
    ort = 0.33 * ted["hiz"] * (1 + ted["km"] / 600)     # uzak ve yavaş tedarikçi geç kalır
    if ay in cfg.YOGUN_AYLAR:
        ort *= cfg.YOGUNLUK_GECIKME_CARPANI            # tedarikçi yoğun
    if ay in cfg.SOGUK_AYLAR:
        ort += cfg.SOGUK_EK_GECIKME_GUN                # kış
    if kat is cfg.KATEGORILER["Sac"] and miktar / cfg.KASA_KG > 5:
        ort += 1.0                                     # büyük sac işi kapasiteyi zorlar
    if acil:
        ort *= 2.0                                     # acil işte aksama olur
    return ort


def sorun_olasiligi(ted, kat, miktar, ay):
    """Bir kalemin sorunlu çıkma olasılığı."""
    p = kat["sorun_taban"] * ted["sorun_egilimi"]
    if ay in cfg.YOGUN_AYLAR:
        p *= 1.8                                       # yoğunlukta hata artar
    if kat is cfg.KATEGORILER["Sac"] and miktar / cfg.KASA_KG > 5:
        p *= 1.3
    return min(p, 0.9)


def sonuc_uret(ted, kat, miktar, ay, acil, rng):
    """Siparişin gerçekleşen sonucu: gecikme, sorun oranı, kısmi teslim, iptal."""
    gecikme = int(round(rng.gamma(4.0, beklenen_gecikme(ted, kat, miktar, ay, acil) / 4.0)))

    kalem = int(np.clip(round(miktar), 1, 60))         # sorun için kalem sayısı
    sorunlu = rng.binomial(kalem, sorun_olasiligi(ted, kat, miktar, ay))
    sorun_orani = sorunlu / kalem

    kismi = rng.random() < 0.015 + 0.01 * ted["sorun_egilimi"]
    iptal = rng.random() < 0.008 + 0.004 * ted["sorun_egilimi"]
    return gecikme, sorun_orani, kismi, iptal


# ---------------------------------------------------------------------------
# 3) ANA ÜRETİM
# ---------------------------------------------------------------------------
def uret():
    rng = np.random.default_rng(cfg.SEED)

    gunler = pd.date_range(cfg.TARIH_BASLANGIC, cfg.TARIH_BITIS, freq="D")
    yakit = yakit_endeksi_uret(gunler, rng)

    w = tarih_agirliklari(gunler)
    siparis_gunleri = rng.choice(gunler, size=cfg.SIPARIS_SAYISI, p=w / w.sum())
    siparis_gunleri = np.sort(siparis_gunleri)

    kat_adlari = list(KATEGORI_AGIRLIK)
    kat_p = np.array([KATEGORI_AGIRLIK[k] for k in kat_adlari])
    kat_p = kat_p / kat_p.sum()

    satirlar = []
    for gun in siparis_gunleri:
        tarih = pd.Timestamp(gun)
        ay = tarih.month

        kat_ad = rng.choice(kat_adlari, p=kat_p)
        kat = cfg.KATEGORILER[kat_ad]
        ted_ad = rng.choice(kat["tedarikciler"])
        ted = cfg.TEDARIKCILER[ted_ad]

        miktar = miktar_uret(kat, rng)
        acil = bool(rng.random() < cfg.ACIL_SIPARIS_ORANI)
        yakit_end = float(yakit[tarih])

        # --- Fiyat ---
        birim_fiyat = kat["baz_fiyat"] * ted["fiyat_endeksi"] * fiyat_katsayisi(tarih)
        birim_fiyat *= rng.normal(1.0, 0.03)                    # piyasa dalgalanması
        iskonto = iskonto_orani(kat, miktar)
        kivirma = kat.get("kivirma_tl_kg", {}).get(ted_ad, 0.0) * fiyat_katsayisi(tarih)

        mal_bedeli = miktar * (birim_fiyat * (1 - iskonto / 100) + kivirma)
        nakliye = nakliye_maliyeti(ted, yakit_end)
        efektif_birim = (mal_bedeli + nakliye) / miktar          # nakliye dahil birim maliyet

        # --- Söz verilen süre ---
        if kat_ad == "Sac":
            aralik = sac_teslim_araligi(miktar)
        else:
            aralik = kat["teslim_gun"]
        sozlesme_gun = int(rng.integers(aralik[0], aralik[1] + 1))
        if acil:
            sozlesme_gun = max(1, sozlesme_gun // 2)

        # --- Sonuç ---
        gecikme, sorun_orani, kismi, iptal = sonuc_uret(ted, kat, miktar, ay, acil, rng)
        riskli = (gecikme >= cfg.GECIKME_ESIK_GUN
                  or sorun_orani > cfg.SORUN_ORANI_ESIK
                  or kismi or iptal)

        satirlar.append(dict(
            tarih=tarih.date(), ay=ay, kategori=kat_ad, tedarikci=ted_ad,
            sehir=ted["sehir"], km=ted["km"], yontem=ted["yontem"],
            miktar=miktar, birim=kat["birim"], acil=int(acil),
            yakit_endeksi=round(yakit_end, 3),
            birim_fiyat=round(birim_fiyat, 2), iskonto_yuzde=iskonto,
            kivirma_tl_birim=round(kivirma, 2),
            mal_bedeli=round(mal_bedeli, 2), nakliye=round(nakliye, 2),
            efektif_birim_maliyet=round(efektif_birim, 2),
            sozlesme_gun=sozlesme_gun,
            # --- Aşağıdakiler SİPARİŞTEN SONRA bilinir (ML'e girdi olarak verilmez) ---
            gecikme_gun=gecikme, gerceklesen_gun=sozlesme_gun + gecikme,
            sorun_orani=round(sorun_orani, 3),
            kismi_teslim=int(kismi), iptal=int(iptal), riskli=int(riskli),
        ))

    return pd.DataFrame(satirlar)


if __name__ == "__main__":
    df = uret()
    cikti = Path(__file__).resolve().parent.parent / "data" / "siparisler.csv"
    cikti.parent.mkdir(exist_ok=True)
    df.to_csv(cikti, index=False, encoding="utf-8-sig")

    print(f"{len(df)} sipariş üretildi -> {cikti}")
    print(f"Riskli sipariş oranı: {df['riskli'].mean():.3f}")
    print("\nKategori bazında riskli oranı:")
    print(df.groupby("kategori")["riskli"].agg(["count", "mean"]).round(3).to_string())
    print("\nTedarikçi bazında riskli oranı:")
    print(df.groupby("tedarikci")["riskli"].agg(["count", "mean"]).round(3).to_string())