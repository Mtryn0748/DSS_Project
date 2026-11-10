"""AHP: ikili karsilastirma matrislerinden kriter agirliklari ve tutarlilik orani (CR)."""
import numpy as np

KRITERLER = ["Efektif maliyet", "İndirim", "Teslimat süresi", "Sözleşme uyumu", "Sipariş riski"]
YON = np.array([1, 0, 1, 0, 1])  # 1: maliyet yonlu (kucuk iyi), 0: fayda yonlu (buyuk iyi)
RI = {1: 0, 2: 0, 3: .58, 4: .90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45}  # Saaty rastgele tutarlilik indeksi

def matris(ustu):
    """ustu: {(i,j): deger} i<j icin Saaty degeri; alt ucgen karsiliklidir."""
    n = len(KRITERLER); A = np.ones((n, n))
    for (i, j), v in ustu.items():
        A[i, j] = v; A[j, i] = 1.0 / v
    return A

def agirlik(A):
    vals, vecs = np.linalg.eig(A); k = np.argmax(vals.real)
    w = np.abs(vecs[:, k].real); w = w / w.sum()
    n = A.shape[0]; ci = (vals[k].real - n) / (n - 1)
    return w, (ci / RI[n] if RI[n] else 0.0)

# Kriter sirasi: 0 maliyet, 1 indirim, 2 teslimat, 3 uyum, 4 risk
PERSONALAR = {
 "Maliyet odaklı (CFO)": matris({(0,1):3,(0,2):4,(0,3):6,(0,4):5,(1,2):1,(1,3):2,(1,4):1,(2,3):2,(2,4):1,(3,4):1/2}),
 "Kalite odaklı (Kalite müdürü)": matris({(0,1):2,(0,2):1,(0,3):1/4,(0,4):1/4,(1,2):1/2,(1,3):1/6,(1,4):1/6,(2,3):1/4,(2,4):1/4,(3,4):1}),
 "Acil teslimat (mazot zammı)": matris({(0,1):3,(0,2):1/5,(0,3):1,(0,4):1/3,(1,2):1/7,(1,3):1/2,(1,4):1/5,(2,3):5,(2,4):2,(3,4):1/3}),
 "Dengeli": matris({}),
}

if __name__ == "__main__":
    for ad, A in PERSONALAR.items():
        w, cr = agirlik(A)
        print(f"{ad:32s} CR={cr:.3f} {'OK' if cr < .10 else 'TUTARSIZ'}  ", dict(zip(KRITERLER, w.round(3))))