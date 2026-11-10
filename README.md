"Projenin githuba yüklenmesi için readme açıldı".

# 1-projeyi bilgisayarda çalıştırmak için gerekli kütüphane ve dosyaları kurun:
   pip install -r requirements.txt
# 2-generate data dosyası config dosyasındaki koşulları ve gereksinimleere göre csv üretiyor seed=42
   python src/gen_data.py
# 3- machine learning: bu dosya gen datanın varsa çıktısı olan csv'yi okuyor, yoksa kendisi oluşturuyor ve ml pipeline kuruyor

** içerisndeki ml algoritmaları: xgboost, svm, logistic reg., random forrest. 
   python src/ml.py