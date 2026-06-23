"""
Home.py — página inicial do site.

Rodar com:
    streamlit run site/Home.py
"""
import os
import sys

# garante que 'lib' seja importável quando o streamlit roda deste arquivo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

from lib import db

st.set_page_config(page_title="Painel Financeiro", page_icon="📊", layout="wide")

st.title("📊 Painel Financeiro")
st.caption("Site interno — dados de Fundos CVM e Ações. Uso local.")

st.markdown(
    """
    Bem-vindo. Use o menu à esquerda para navegar. O site tem duas áreas:

    - **🏦 Fundos CVM** — analisar as *posições dos fundos*: quem detém cada
      ação, ranking e evolução mês a mês.
    - **📈 Ações** — analisar os *fundamentos das ações*: indicadores,
      comparação, triagem e dividendos.
    """
)

st.divider()
st.subheader("Status dos dados")

col1, col2 = st.columns(2)
for col, (nome, caminho) in zip(
    (col1, col2),
    [("Fundos CVM", db.FUNDOS_DB), ("Financeiro", db.FINANCEIRO_DB)],
):
    with col:
        info = db.info_atualizacao(caminho)
        if info:
            st.metric(nome, "Carregado", f"atualizado em {info:%d/%m/%Y %H:%M}")
        else:
            st.metric(nome, "Sem dados", "rode atualizar_dados.py")

st.info(
    "Os dados aqui são uma **cópia** dos bancos originais (somente leitura). "
    "Para atualizar, rode no terminal:  `python site/atualizar_dados.py`",
    icon="🔒",
)

# redeploy: forcar reload do cache do Streamlit Cloud
