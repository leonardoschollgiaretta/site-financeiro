# Rock Phosphate — coleta de dados de mercado

Foco: importações BR e exportações do Egito de **rocha fosfática (HS 2510)**.

## Estrutura

```
rock_phosphate/
├── comex_brasil.py      # Comexstat: importações BR de HS 2510 por país de origem
├── comtrade_egito.py    # UN Comtrade: exportações Egito de HS 2510 por destino
├── precos_worldbank.py  # World Bank Pinkbook: preço internacional série histórica
├── producao_usgs.py     # USGS: produção/reservas por país (snapshot anual)
├── data/                # outputs CSV/Excel
└── README.md
```

## Código HS

- **HS 2510**: Natural calcium phosphates (rocha fosfática)
  - 2510.10: não moídas
  - 2510.20: moídas
- No Brasil: **NCM 2510.10.10 / 2510.20.10**

## Como rodar

Pré-requisitos: `requests`, `pandas`, `openpyxl` (já tem no Anaconda).

```powershell
cd "rock_phosphate"
python comex_brasil.py   # importações BR — gera data/comex_br_2510.csv
python comtrade_egito.py # exportações Egito — gera data/comtrade_eg_2510.csv
python precos_worldbank.py
python producao_usgs.py
```

## Fontes oficiais

- **Comexstat**: https://comexstat.mdic.gov.br/ (Ministério Desenvolvimento, BR)
- **UN Comtrade**: https://comtradeplus.un.org/
- **World Bank Pinkbook**: https://www.worldbank.org/en/research/commodity-markets
- **USGS Mineral Commodities**: https://www.usgs.gov/centers/national-minerals-information-center/phosphate-rock-statistics-and-information
