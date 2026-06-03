# Currency Analysis

Análise quantitativa de séries históricas de câmbio com foco em estatística descritiva e projeções.

## Estrutura

```
currency-analysis/
├── data/
│   ├── raw/         # dados brutos da API (não editar)
│   ├── processed/   # dados limpos
│   └── cache/       # cache local pra evitar refetch
├── notebooks/       # análises em Jupyter
├── src/
│   ├── fetchers/    # coleta de dados das APIs
│   ├── analysis/    # funções estatísticas
│   └── utils/       # helpers
└── tests/
```

## Setup

```bash
# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependências
pip install -r requirements.txt

# Copiar arquivo de variáveis
cp .env.example .env
```

## Uso rápido

```python
from src.fetchers.yahoo_fetcher import fetch_currency_history

# Baixa histórico USD/BRL dos últimos 5 anos
df = fetch_currency_history("USDBRL=X", period="5y")
```

## Fontes de dados

- **Yahoo Finance** (yfinance): histórico longo, gratuito, sem chave
- **exchangerate.host**: API REST simples, gratuita
- **BCB SGS**: cotações oficiais do Banco Central do Brasil (PTAX)

## Notebooks

1. `01_exploratory.ipynb` — visão geral dos dados
2. `02_statistics.ipynb` — estatística descritiva e volatilidade
3. `03_forecasting.ipynb` — projeções (a fazer)
