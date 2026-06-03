# ============================================================
# DEBUG - Coleta de dados do TradingView (UKOIL e outros)
# ============================================================
# 1. Instale as dependências antes de rodar:
#    pip install tvDatafeed pandas openpyxl
# 2. Rode: python tradingview_debug.py
# ============================================================
 
from tvDatafeed import TvDatafeed, Interval
import pandas as pd
from datetime import datetime
 
print("=" * 50)
print("TradingView Data Collector - DEBUG")
print("=" * 50)
 
# ── Conexão (sem login = dados gratuitos, com login = mais histórico)
print("\n[1] Conectando ao TradingView...")
try:
    tv = TvDatafeed()  # sem login - dados públicos
    # tv = TvDatafeed(username="seu@email.com", password="suasenha")  # com login
    print("    ✓ Conectado!")
except Exception as e:
    print(f"    ✗ Erro de conexão: {e}")
    exit()
 
# ── Símbolos que você quer monitorar
SIMBOLOS = [
    {"symbol": "UKOIL",  "exchange": "TVC",   "nome": "Petróleo Brent (UKOIL)"},
    {"symbol": "GOLD",   "exchange": "TVC",   "nome": "Ouro (GOLD)"},
    {"symbol": "USDBRL", "exchange": "FX_IDC","nome": "Dólar/Real (USDBRL)"},
]
 
resultados = []
 
print("\n[2] Buscando cotações...")
for s in SIMBOLOS:
    try:
        df = tv.get_hist(
            symbol=s["symbol"],
            exchange=s["exchange"],
            interval=Interval.in_daily,  # diário
            n_bars=5                      # últimos 5 dias
        )
 
        if df is not None and not df.empty:
            ultimo = df.iloc[-1]
            anterior = df.iloc[-2]
            variacao = ((ultimo["close"] - anterior["close"]) / anterior["close"]) * 100
 
            print(f"\n    {s['nome']}")
            print(f"      Preço atual : {ultimo['close']:.4f}")
            print(f"      Abertura    : {ultimo['open']:.4f}")
            print(f"      Máxima      : {ultimo['high']:.4f}")
            print(f"      Mínima      : {ultimo['low']:.4f}")
            print(f"      Variação    : {variacao:+.2f}%")
 
            resultados.append({
                "Símbolo"   : s["symbol"],
                "Nome"      : s["nome"],
                "Preço"     : ultimo["close"],
                "Abertura"  : ultimo["open"],
                "Máxima"    : ultimo["high"],
                "Mínima"    : ultimo["low"],
                "Variação%" : round(variacao, 2),
                "Data"      : df.index[-1].strftime("%d/%m/%Y %H:%M"),
            })
        else:
            print(f"\n    {s['nome']}: sem dados retornados")
 
    except Exception as e:
        print(f"\n    {s['nome']}: erro → {e}")
 
# ── Salvar em Excel
if resultados:
    print("\n[3] Salvando Excel...")
    try:
        df_out = pd.DataFrame(resultados)
        nome_arquivo = f"cotacoes_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        df_out.to_excel(nome_arquivo, index=False)
        print(f"    ✓ Salvo: {nome_arquivo}")
        print("\n", df_out.to_string(index=False))
    except Exception as e:
        print(f"    ✗ Erro ao salvar: {e}")
else:
    print("\n    Nenhum dado para salvar.")
 
print("\n" + "=" * 50)
print("Fim do debug.")
print("=" * 50)