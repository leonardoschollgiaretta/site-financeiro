# Site (Painel Financeiro)

Site interno em **Streamlit** para visualizar os dados de **Fundos CVM** e **Ações**.
Roda **localmente** no seu PC. Os scripts e bancos originais **não são tocados**:
o site lê apenas uma **cópia** dos bancos (em `site/data/`), em modo somente leitura.

## Como rodar

1. **Atualizar os dados** (copia os bancos originais para `site/data/`):
   ```
   python site/atualizar_dados.py
   ```
   Rode isso sempre que quiser que o site mostre dados mais novos
   (depois de rodar seus coletores normalmente).

2. **Subir o site** (uma das opções):
   - Duplo-clique em `site/rodar_site.bat`, **ou**
   - No terminal:
     ```
     python -m streamlit run site/Home.py
     ```

3. Abre sozinho no navegador em **http://localhost:8501**.
   Para parar: feche o terminal ou aperte `Ctrl+C` nele.

## Estrutura

```
site/
├── Home.py              página inicial
├── pages/
│   └── 1_Fundos_CVM.py  consulta de fundos (por ação, ranking, evolução)
├── lib/
│   ├── db.py            conexão SOMENTE LEITURA com os bancos
│   └── fundos.py        queries dos fundos (retornam tabelas)
├── data/                CÓPIAS dos bancos (não versionado no git)
├── atualizar_dados.py   copia os bancos originais -> data/
└── requirements.txt     dependências (streamlit, pandas, openpyxl)
```

## Segurança

- O site **nunca** escreve nos bancos. A conexão é `mode=ro` (read-only do SQLite).
- Se você apagar a pasta `site/`, nada do que já funciona é afetado.
- A pasta `site/data/` está no `.gitignore` (bancos não vão para o git).
