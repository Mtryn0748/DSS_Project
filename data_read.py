import numpy as np
import pandas as  pd

df = pd.read_csv(r"data/sentetik_siparisler.csv")

print(df.describe())
print(df.info())

print(df["Urun_Kategorisi"].unique())