"""
config.py  -  Projenin TÜM senaryo ayarları burada.

Bir rakamı değiştirmek istersen SADECE bu dosyayı düzenle; diğer dosyalar buradan okur.

İşaretler:
    # VARSAYIM  -> Tahmini değer. Gerçeğini biliyorsan düzelt.
    # SORU      -> Cevabını senden bekleyen yer.
    (işaretsiz) -> Senin anlattığına dayanıyor.

Senaryo: Korkuteli'de karoser (kamyon kasası) atölyesinin satın alma süreci.
"""

# ---------------------------------------------------------------------------
# 1) GENEL
# ---------------------------------------------------------------------------
SIPARIS_SAYISI = 3000          # Üretilecek geçmiş sipariş sayısı
SEED = 42                      # Aynı sayı = her çalıştırmada aynı veri (random seed)
TARIH_BASLANGIC = "2024-01-01"
TARIH_BITIS = "2026-09-30"

# Fiyatlar Eylül 2026 (veri bitişi) fiyatıdır. Geçmiş aylarda fiyat, TCMB TÜFE aylık
# değişimleriyle geriye indirgenir. Kaynak: TCMB Tüketici Fiyatları tablosu.
TUFE_AYLIK = {   # "yıl-ay": o ayın TÜFE aylık değişimi (%)
    "2024-01": 6.70, "2024-02": 4.53, "2024-03": 3.16, "2024-04": 3.18, "2024-05": 3.37, "2024-06": 1.64,
    "2024-07": 3.23, "2024-08": 2.47, "2024-09": 2.97, "2024-10": 2.88, "2024-11": 2.24, "2024-12": 1.03,
    "2025-01": 5.03, "2025-02": 2.27, "2025-03": 2.46, "2025-04": 3.00, "2025-05": 1.53, "2025-06": 1.37,
    "2025-07": 2.06, "2025-08": 2.04, "2025-09": 3.23, "2025-10": 2.55, "2025-11": 0.87, "2025-12": 0.89,
    "2026-01": 4.84, "2026-02": 2.96, "2026-03": 1.94, "2026-04": 4.18, "2026-05": 1.71, "2026-06": 0.99,
    "2026-07": 1.78, "2026-08": 1.84, "2026-09": 1.84,
}
ACIL_SIPARIS_ORANI = 0.15      # VARSAYIM: siparişlerin %15'i acil


# ---------------------------------------------------------------------------
# 2) TESLİMAT YÖNTEMLERİ  (parayı ve süreyi kimin taşıdığı)
# ---------------------------------------------------------------------------
YONTEMLER = {
    "kamyonet": "Biz gidip alırız: yol masrafı bizde, akaryakıt zammından etkilenir",
    "tedarikci_araci": "Tedarikçi kendi aracıyla getirir: yol masrafı yok, süre kargo gibi",
    "kargo": "Kargo/ambar: sabit gönderi ücreti, 2-5 gün, hasar riski",
}

# Kamyonetle gidince bir sefer maliyeti = 2 x km x (yakıt + diğer)
MOTORIN_TL_LITRE = 99.3        # Antalya motorin, 30 Ekim 2026 (Petrol Ofisi listesi). İleride API ile çekilebilir.
KAMYONET_TUKETIM_L_100KM = 10  # VARSAYIM: kamyonet ortalama tüketim (litre / 100 km)
KAMYONET_YAKIT_TL_KM = MOTORIN_TL_LITRE * KAMYONET_TUKETIM_L_100KM / 100   # ~9,9 TL/km (akaryakıt zammıyla artar)
KAMYONET_DIGER_TL_KM = 8       # VARSAYIM: şoför, yıpranma, zaman
KARGO_SABIT_TL = 350           # VARSAYIM: kargo/ambar gönderi ücreti


# ---------------------------------------------------------------------------
# 3) SEZON  (iş yoğunluğu ve hava)
# ---------------------------------------------------------------------------
YOGUN_AYLAR = [3, 4, 8, 9]     # Mart-Nisan, Ağustos-Eylül
YOGUNLUK_GECIKME_CARPANI = 2.0 # VARSAYIM: yoğun aylarda tedarikçi gecikmesi x2
SOGUK_AYLAR = [12, 1, 2]       # Kış: soğuk yüzünden işler geç biter
SOGUK_EK_GECIKME_GUN = 0.8     # VARSAYIM


# ---------------------------------------------------------------------------
# 4) TEDARİKÇİLER
#    fiyat_endeksi : 1.00 = Korkuteli fiyatı. Senin örneğin: 55 / 51 / 59
#                    -> Korkuteli 1.00, Bucak 0.93, Antalya 1.07
#    sorun_egilimi : 1.0 = ortalama. 2.0 = ortalamanın 2 katı sorunlu ürün.
#    hiz           : 1.0 = normal. Küçük = hızlı, büyük = yavaş.
#    iskonto_carpani : (isteğe bağlı, varsayılan 1.0) toplu alım iskontosunu tedarikçiye göre ölçekler.
#    km            : Korkuteli'ne TEK YÖN karayolu uzaklığı (git-gel maliyeti kodda 2 ile çarpılır:
#                    Antalya 63 -> git-gel ~126 km, Bucak 55 -> ~110 km).
# ---------------------------------------------------------------------------
TEDARIKCILER = {
    # --- Demirciler (sac ve profil aynı demircilerden) ---
    "Korkuteli Demirci":     dict(sehir="Korkuteli", km=5,   yontem="kamyonet",
                                  fiyat_endeksi=1.00, sorun_egilimi=1.0, hiz=0.8, iskonto_carpani=0.6),   # VARSAYIM
    "Bucak Demirci":         dict(sehir="Bucak",     km=55, yontem="kamyonet",
                                  fiyat_endeksi=0.93, sorun_egilimi=1.3, hiz=1.0, iskonto_carpani=1.3),   # VARSAYIM (km: SORU)
    "Burdur Demirci":        dict(sehir="Burdur",    km=105, yontem="kamyonet",
                                  fiyat_endeksi=0.96, sorun_egilimi=1.0, hiz=1.0, iskonto_carpani=1.1),   # VARSAYIM (km: SORU)
    "Antalya Demirci-1":     dict(sehir="Antalya",   km=63,  yontem="kamyonet",
                                  fiyat_endeksi=1.07, sorun_egilimi=0.6, hiz=0.8, iskonto_carpani=0.9),   # VARSAYIM
    "Antalya Demirci-2":     dict(sehir="Antalya",   km=63,  yontem="kamyonet",
                                  fiyat_endeksi=1.03, sorun_egilimi=1.1, hiz=0.9, iskonto_carpani=1.0),   # VARSAYIM

    # --- Boyacılar (boyayı kendileri gönderiyor) ---
    "İzmir Boya-1":          dict(sehir="İzmir",     km=450, yontem="tedarikci_araci",
                                  fiyat_endeksi=0.95, sorun_egilimi=2.2, hiz=1.2, iskonto_carpani=1.2),   # renk tutmama/kuruma sorunu
    "İzmir Boya-2":          dict(sehir="İzmir",     km=450, yontem="tedarikci_araci",
                                  fiyat_endeksi=1.05, sorun_egilimi=0.7, hiz=1.1, iskonto_carpani=0.9),
    "Denizli Boya":          dict(sehir="Denizli",   km=210, yontem="tedarikci_araci",
                                  fiyat_endeksi=1.00, sorun_egilimi=1.0, hiz=1.0, iskonto_carpani=1.0),
    "Konya Boya":            dict(sehir="Konya",     km=350, yontem="tedarikci_araci",
                                  fiyat_endeksi=0.97, sorun_egilimi=1.2, hiz=1.3, iskonto_carpani=1.1),
    "Antalya Boya":          dict(sehir="Antalya",   km=63,  yontem="tedarikci_araci",
                                  fiyat_endeksi=1.08, sorun_egilimi=0.8, hiz=0.8, iskonto_carpani=0.8),

    # --- Aksesuar ve krom (kargo)  SORU: kaç tedarikçi, hangi şehirler? ---
    "İstanbul Aksesuar-1":   dict(sehir="İstanbul",  km=700, yontem="kargo",
                                  fiyat_endeksi=0.95, sorun_egilimi=1.2, hiz=1.0, iskonto_carpani=1.2),   # VARSAYIM
    "İstanbul Aksesuar-2":   dict(sehir="İstanbul",  km=700, yontem="kargo",
                                  fiyat_endeksi=1.05, sorun_egilimi=0.7, hiz=1.0, iskonto_carpani=0.9),   # VARSAYIM
    "Denizli Aksesuar":      dict(sehir="Denizli",   km=210, yontem="kargo",
                                  fiyat_endeksi=1.00, sorun_egilimi=1.0, hiz=0.9, iskonto_carpani=1.0),   # VARSAYIM

    # --- Aydınlatma / elektrik (İstanbul, kargo): 2 tedarikçi ---
    "İstanbul Aydınlatma-1": dict(sehir="İstanbul",  km=700, yontem="kargo",
                                  fiyat_endeksi=0.95, sorun_egilimi=1.3, hiz=1.0, iskonto_carpani=1.2),   # VARSAYIM
    "İstanbul Aydınlatma-2": dict(sehir="İstanbul",  km=700, yontem="kargo",
                                  fiyat_endeksi=1.08, sorun_egilimi=0.7, hiz=1.1, iskonto_carpani=0.9),   # VARSAYIM

    # --- Bağlantı elemanları ve kasa donanımı: baba erkeği, sikke, somun, menteşe (kargo) ---
    #     km: yaklaşık karayolu uzaklığı, Korkuteli'nden (arama sonuçlarından tahmin)
    "Konya Bağlantı":        dict(sehir="Konya",     km=390, yontem="kargo",
                                  fiyat_endeksi=0.96, sorun_egilimi=1.3, hiz=1.0, iskonto_carpani=1.0),   # VARSAYIM (km: yaklaşık)
    "Nevşehir Bağlantı":     dict(sehir="Nevşehir",  km=570, yontem="kargo",
                                  fiyat_endeksi=0.92, sorun_egilimi=1.6, hiz=1.2, iskonto_carpani=1.3),   # VARSAYIM (km: yaklaşık)
    "Ankara Bağlantı":       dict(sehir="Ankara",    km=520, yontem="kargo",
                                  fiyat_endeksi=1.06, sorun_egilimi=0.7, hiz=0.9, iskonto_carpani=0.8),   # VARSAYIM (km: yaklaşık)

    # --- Tek kaynaklar (alternatif yok) ---
    "İstanbul Vinç":         dict(sehir="İstanbul",  km=700, yontem="kargo",
                                  fiyat_endeksi=1.00, sorun_egilimi=1.0, hiz=1.0),
    "Antalya Kompozit":      dict(sehir="Antalya",   km=63,  yontem="kargo",
                                  fiyat_endeksi=1.00, sorun_egilimi=1.0, hiz=1.0),
}


# ---------------------------------------------------------------------------
# 5) KATEGORİLER
#    baz_fiyat       : Referans fiyat, KDV hariç (TL / birim). Sac ve profil: web sitesi listesi
#    miktar          : (en az, tipik, en çok)
#    iskonto         : [(miktar eşiği, iskonto %)]  toplu alım indirimi
#    teslim_gun      : (en az, en çok) söz verilen süre; sacda miktara bağlı (aşağıda)
#    sorun_taban     : ortalama sorunlu ürün oranı (tedarikçi eğilimiyle çarpılır)
#    kivirma_tl_kg   : (sadece sac) demircinin kıvırma ücreti, efektif maliyete eklenir
#    sorun_tanimi    : bu kategoride "sorun" ne demek
# ---------------------------------------------------------------------------
KATEGORILER = {
    "Sac": dict(
        birim="kg", baz_fiyat=35.4,                                 # düz siyah sac 2 mm ST37, KDV hariç (yakupyilmazboru.com, 06.11.2026)
        miktar=(100, 900, 6000),                                    # tek kasa 600-900 kg
        iskonto=[(600, 2), (1500, 4), (4000, 6)],                 # VARSAYIM: tek kasa (~750 kg) bile %2
        teslim_gun=(1, 2), sorun_taban=0.025,                        # VARSAYIM
        # Düz sac alınır, kıvırtılır; demirci kıvırma ücretini fiyatın üstüne ekler (TL / kg).
        kivirma_tl_kg={"Korkuteli Demirci": 4.0, "Bucak Demirci": 3.5, "Burdur Demirci": 3.8,
                       "Antalya Demirci-1": 4.5, "Antalya Demirci-2": 4.0},   # VARSAYIM
        sorun_tanimi="Ölçü tutarsızlığı, hatalı kesim, fazla fire",
        tedarikciler=["Korkuteli Demirci", "Bucak Demirci", "Burdur Demirci",
                      "Antalya Demirci-1", "Antalya Demirci-2"],
    ),
    "Profil": dict(
        birim="adet", baz_fiyat=521,                                # 6 m kutu profil 40x40x2 mm, KDV hariç (yakupyilmazboru.com, 09.11.2026)
        miktar=(1, 20, 300),
        iskonto=[(100, 12)],                                        # 100'lü bant: büyük indirim
        teslim_gun=(1, 3), sorun_taban=0.008,                        # VARSAYIM
        sorun_tanimi="Ölçü hatası, eğrilik",
        tedarikciler=["Korkuteli Demirci", "Bucak Demirci", "Burdur Demirci",
                      "Antalya Demirci-1", "Antalya Demirci-2"],
    ),
    "Boya ve sarf": dict(
        birim="litre", baz_fiyat=350,                               # VARSAYIM
        miktar=(0.3, 5, 60),                                        # 300 ml ... 20 litre
        iskonto=[(3, 10), (20, 15)],                                # 300ml->3L yaklaşık %10
        teslim_gun=(2, 6), sorun_taban=0.018,                        # VARSAYIM
        sorun_tanimi="Renk tutmaması, kuruma olmaması",
        tedarikciler=["İzmir Boya-1", "İzmir Boya-2", "Denizli Boya",
                      "Konya Boya", "Antalya Boya"],
    ),
    "Aksesuar ve krom": dict(
        birim="adet", baz_fiyat=600,                                # VARSAYIM
        miktar=(1, 10, 80),
        iskonto=[(20, 5)],                                          # VARSAYIM
        teslim_gun=(3, 7), sorun_taban=0.012,                        # VARSAYIM
        sorun_tanimi="Kaplama kalitesi, hasarlı gelme",
        tedarikciler=["İstanbul Aksesuar-1", "İstanbul Aksesuar-2", "Denizli Aksesuar"],
    ),
    "Aydınlatma": dict(
        birim="adet", baz_fiyat=350,                                # VARSAYIM
        miktar=(2, 12, 60),
        iskonto=[(20, 6)],                                          # VARSAYIM
        teslim_gun=(3, 8), sorun_taban=0.015,                        # VARSAYIM
        sorun_tanimi="Arızalı veya çalışmayan ürün",
        tedarikciler=["İstanbul Aydınlatma-1", "İstanbul Aydınlatma-2"],
    ),
    "Bağlantı elemanları": dict(
        # Baba erkeği (kasa başı ~40), menteşe (~15), sikke, somun, bağlantı parçaları. Her kasada şart.
        birim="adet", baz_fiyat=30,                                 # VARSAYIM (ortalama parça fiyatı)
        miktar=(20, 100, 600),                                      # çuval = 100 adet
        iskonto=[(200, 5), (500, 10)],                              # VARSAYIM
        teslim_gun=(2, 5), sorun_taban=0.006,                        # VARSAYIM: nadiren sorunlu
        sorun_tanimi="Eksik adet (100 yerine 98), ince parça, menteşe açılmama, sikkede renk farkı (nadir)",
        tedarikciler=["Konya Bağlantı", "Nevşehir Bağlantı", "Ankara Bağlantı"],
    ),
    "Vinç": dict(
        birim="adet", baz_fiyat=85000,                              # VARSAYIM
        miktar=(1, 1, 1), iskonto=[],
        teslim_gun=(7, 20), sorun_taban=0.004,
        sorun_tanimi="Arıza, eksik parça",
        tedarikciler=["İstanbul Vinç"],
    ),
    "Kompozit panel": dict(
        birim="m2", baz_fiyat=900,                                  # VARSAYIM
        miktar=(1, 8, 60),
        iskonto=[(20, 8)],                                          # VARSAYIM
        teslim_gun=(3, 10), sorun_taban=0.008,
        sorun_tanimi="Hasarlı veya ölçüsüz gelme",
        tedarikciler=["Antalya Kompozit"],
    ),
}

# Sac işleme süresi sipariş büyüklüğüne bağlı (senin anlattığın gibi):
# tek kasa 1-2 gün, ~5 kasa 3-4 gün, çok büyük iş 10-30 gün.
# kasa_esdegeri = kg / KASA_KG
KASA_KG = 750
SAC_TESLIM_KADEMELERI = [        # (en çok kaç kasa, (en az gün, en çok gün))
    (1,   (1, 2)),
    (5,   (2, 4)),
    (10,  (5, 10)),
    (999, (10, 30)),
]


# ---------------------------------------------------------------------------
# 6) "RİSKLİ SİPARİŞ" TANIMI  (ML'in tahmin ettiği şey)
#    SORU: Bu eşikler senin için doğru mu?
# ---------------------------------------------------------------------------
GECIKME_ESIK_GUN = 2           # Söz verilen günden 2+ gün geç = riskli
SORUN_ORANI_ESIK = 0.05        # Ürünlerin %5'inden fazlası sorunluysa = riskli
# Ayrıca: iptal edilen veya kısmi teslim edilen sipariş de riskli sayılır.


# ---------------------------------------------------------------------------
# YARDIMCI FONKSİYONLAR
# ---------------------------------------------------------------------------
def tedarikci_sayisi(kategori):
    return len(KATEGORILER[kategori]["tedarikciler"])


def tek_kaynak_mi(kategori):
    """Tek tedarikçi varsa seçim yoktur: sistem uyarı verir."""
    return tedarikci_sayisi(kategori) == 1


def siralanabilir_mi(kategori):
    """En az 2 tedarikçi varsa karşılaştırma yapılabilir."""
    return tedarikci_sayisi(kategori) >= 2


# ---------------------------------------------------------------------------
# Çalıştırınca senaryonun özetini yazar:  python config.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("SENARYO ÖZETİ\n")
    for kategori, ayar in KATEGORILER.items():
        durum = "TEK KAYNAK (sıralama yok)" if tek_kaynak_mi(kategori) else f"{tedarikci_sayisi(kategori)} tedarikçi"
        print(f"{kategori:18s} [{ayar['birim']}]  {durum}")
        for ad in ayar["tedarikciler"]:
            t = TEDARIKCILER[ad]
            print(f"    - {ad:24s} {t['sehir']:10s} {t['km']:4d} km  {t['yontem']:16s} fiyat x{t['fiyat_endeksi']:.2f}")
    print("\nToplam tedarikçi:", len(TEDARIKCILER))
    print("Sıralanabilir kategori:", sum(siralanabilir_mi(k) for k in KATEGORILER), "/", len(KATEGORILER))