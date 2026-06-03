import pandas as pd

df = pd.read_excel("fundamentus.xlsx")
df.columns = df.columns.str.replace("?", "", regex=False)

df_analise = df[[
    "Ticker", "Empresa", "Cotação", "Setor",
    "P/L", "ROE", "Div. Yield", "P/VP",
    "Marg. Líquida", "Dív. Bruta", "Lucro Líquido"
]].copy()

df_analise["ROE_num"] = df_analise["ROE"].str.replace("%","").str.replace(",",".").astype(float)
df_analise["DY_num"] = df_analise["Div. Yield"].str.replace("%","").str.replace(",",".").astype(float)
df_analise["PL_num"] = df_analise["P/L"].str.replace(",",".").astype(float)

df_analise["Score"] = (
    df_analise["ROE_num"] * 0.4 +
    df_analise["DY_num"] * 0.4 -
    df_analise["PL_num"] * 0.2
)

df_ranking = df_analise[["Ticker", "Empresa", "Setor", "ROE", "Div. Yield", "P/L", "Score"]]\
    .sort_values("Score", ascending=False)\
    .reset_index(drop=True)

df_ranking.index += 1
print(df_ranking.to_string())

df_ranking.to_excel("ranking_acoes.xlsx", index=True)
print("\n✅ Ranking salvo em ranking_acoes.xlsx")