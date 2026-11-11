"""
ahp.py  -  AHP: kriter ağırlıklarını hesaplar.

AHP'nin fikri:
    Karar verici kriterleri ikişer ikişer kıyaslar ("maliyet, teslimattan ne kadar önemli?"),
    Saaty ölçeğinde bir sayı verir. Bu kıyaslardan kriter ağırlıkları çıkar.

Saaty ölçeği (satır kriteri, sütun kriterinden ...):
    1 = eşit önemli      3 = biraz daha önemli     5 = belirgin daha önemli
    7 = çok daha önemli  9 = aşırı derecede önemli
    1/3, 1/5 ... = tersi (sütun kriteri daha önemli)

Tutarlılık oranı (CR): Karar verici kendi kıyaslarıyla çelişiyor mu?
    ("A, B'den; B, C'den önemli ama C, A'dan önemli" gibi). CR < 0.10 ise tutarlıdır.

Bu dosya tek başına çalıştırılırsa personaların ağırlıklarını ve CR'lerini yazar.
"""

import numpy as np

# ---------------------------------------------------------------------------
# KRİTERLER
# ---------------------------------------------------------------------------
KRITERLER = ["Efektif maliyet", "İndirim", "Teslimat süresi", "Sözleşme uyumu", "Sipariş riski"]

# Yön: 1 = maliyet türü (küçük olan iyi), 0 = fayda türü (büyük olan iyi)
#   Efektif maliyet : nakliye dahil birim maliyet (TL)         -> küçük iyi
#   İndirim         : bu miktarda verilen toplu alım iskontosu -> büyük iyi
#   Teslimat süresi : söz verilen / beklenen gün               -> küçük iyi
#   Sözleşme uyumu  : geçmişte süreye uyma oranı (%)           -> büyük iyi
#   Sipariş riski   : ML'in tahmin ettiği risk yüzdesi         -> küçük iyi
YON = np.array([1, 0, 1, 0, 1])

# Saaty'nin rastgele tutarlılık indeksi (matris boyutuna göre sabit değerler)
RI = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45}


# ---------------------------------------------------------------------------
# HESAPLAMA
# ---------------------------------------------------------------------------
def matris(ustu):
    """
    İkili karşılaştırma matrisi kurar.
    ustu: {(i, j): değer}  ->  i. kriter, j. kriterden kaç kat önemli (i < j).
    Alt üçgen otomatik doldurulur (karşılıklı = 1 / değer). Verilmeyen çiftler 1 (eşit).
    """
    n = len(KRITERLER)
    A = np.ones((n, n))
    for (i, j), deger in ustu.items():
        A[i, j] = deger
        A[j, i] = 1.0 / deger
    return A


def agirlik(A):
    """
    Matristen ağırlıkları ve tutarlılık oranını (CR) hesaplar.
    Ağırlık = matrisin en büyük özdeğerine karşılık gelen özvektör (toplamı 1 olacak şekilde).
    """
    degerler, vektorler = np.linalg.eig(A)
    en_buyuk = np.argmax(degerler.real)

    w = np.abs(vektorler[:, en_buyuk].real)
    w = w / w.sum()

    n = A.shape[0]
    ci = (degerler[en_buyuk].real - n) / (n - 1)       # tutarlılık indeksi
    cr = ci / RI[n] if RI[n] else 0.0                  # tutarlılık oranı
    return w, cr


# ---------------------------------------------------------------------------
# PERSONALAR  (karar vericinin önceliklerine göre farklı matris)
# Kriter sırası: 0 maliyet, 1 indirim, 2 teslimat, 3 uyum, 4 risk
# ---------------------------------------------------------------------------
PERSONALAR = {
    "Bütçe odaklı (atölye sahibi)": {
        "aciklama": "Nakit sıkışık. Ucuz olması, teslimat ve riskten daha önemli.",
        "matris": matris({
            (0, 1): 3, (0, 2): 4, (0, 3): 6, (0, 4): 5,
            (1, 2): 1, (1, 3): 2, (1, 4): 1,
            (2, 3): 2, (2, 4): 1,
            (3, 4): 1 / 2,
        }),
    },
    "Kalite odaklı (usta başı)": {
        "aciklama": "Hatalı ürün ve geç teslim işi durdurur. Güvenilirlik fiyattan önemli.",
        "matris": matris({
            (0, 1): 2, (0, 2): 1, (0, 3): 1 / 4, (0, 4): 1 / 4,
            (1, 2): 1 / 2, (1, 3): 1 / 6, (1, 4): 1 / 6,
            (2, 3): 1 / 4, (2, 4): 1 / 4,
            (3, 4): 1,
        }),
    },
    "Acil teslimat (mazot zammı / acil iş)": {
        "aciklama": "Zam geliyor ya da müşteri acele ediyor. Hızlı teslimat her şeyin önünde.",
        "matris": matris({
            (0, 1): 3, (0, 2): 1 / 5, (0, 3): 1, (0, 4): 1 / 3,
            (1, 2): 1 / 7, (1, 3): 1 / 2, (1, 4): 1 / 5,
            (2, 3): 5, (2, 4): 2,
            (3, 4): 1 / 3,
        }),
    },
    "Dengeli": {
        "aciklama": "Tüm kriterler eşit önemde.",
        "matris": matris({}),
    },
}


def persona_agirliklari():
    """Her persona için {ad: (ağırlıklar, CR)} döndürür."""
    return {ad: agirlik(p["matris"]) for ad, p in PERSONALAR.items()}


# ---------------------------------------------------------------------------
# Çalıştırınca ağırlıkları yazar:  python src/ahp.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    for ad, p in PERSONALAR.items():
        w, cr = agirlik(p["matris"])
        durum = "tutarlı" if cr < 0.10 else "TUTARSIZ"
        print(f"\n{ad}   (CR = {cr:.3f}, {durum})")
        for kriter, agirlik_degeri in zip(KRITERLER, w):
            print(f"    {kriter:18s} {agirlik_degeri:.3f}")