# -*- coding: utf-8 -*-
"""
atualizar_ranking_diario.py — rotina diária (agendada) que:
  1) raspa o ranking do Investidor10 e grava na tabela ranking_acoes do
     financeiro.db (financeiro/ranking_investidor10.py --banco);
  2) copia os bancos para site/data/ (site/atualizar_dados.py).

Escreve um log em <raiz>/logs/ranking_AAAA-MM-DD.log. Feito para rodar no
Agendador de Tarefas do Windows, em silêncio. Nunca lança exceção pro chamador
(registra o erro no log e sai com código != 0).
"""
import datetime
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable  # o mesmo Python que está rodando este script
LOG_DIR = os.path.join(RAIZ, "logs")


def _log(f, msg):
    linha = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(linha)
    f.write(linha + "\n")
    f.flush()


def _rodar(f, descricao, *args):
    _log(f, f">>> {descricao}")
    r = subprocess.run([PY, *args], cwd=RAIZ, capture_output=True, text=True)
    if r.stdout:
        f.write(r.stdout + "\n")
    if r.stderr:
        f.write(r.stderr + "\n")
    f.flush()
    if r.returncode != 0:
        _log(f, f"!!! FALHA em '{descricao}' (código {r.returncode})")
    return r.returncode == 0


def _shell(f, descricao, cmd):
    """Roda um comando de shell (lista) e loga a saída. Retorna True se ok."""
    _log(f, f">>> {descricao}")
    r = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True)
    if r.stdout:
        f.write(r.stdout + "\n")
    if r.stderr:
        f.write(r.stderr + "\n")
    f.flush()
    if r.returncode != 0:
        _log(f, f"!!! FALHA em '{descricao}' (código {r.returncode})")
    return r.returncode == 0


def publicar_nuvem(f):
    """Copia os bancos leves para site/dados_nuvem/ e dá push pro GitHub,
    para o site online (Streamlit Cloud) refletir os dados do dia.
    Só sobe os leves (financeiro.db ~3MB, bolao.db). O fundos reduzido (~70MB)
    muda pouco e não é re-enviado aqui."""
    import shutil
    nuvem = os.path.join(RAIZ, "site", "dados_nuvem")
    data = os.path.join(RAIZ, "site", "data")
    os.makedirs(nuvem, exist_ok=True)
    for nome in ("financeiro.db",):
        src = os.path.join(data, nome)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(nuvem, nome))
    # bolao.db (resultados da copa) vem da pasta bolao_copa
    bolao = os.path.join(RAIZ, "bolao_copa", "bolao.db")
    if os.path.exists(bolao):
        shutil.copy2(bolao, os.path.join(nuvem, "bolao.db"))
    _log(f, "Bancos leves copiados para dados_nuvem.")

    git = "git"
    _shell(f, "git add (dados_nuvem)", [git, "add",
            "site/dados_nuvem/financeiro.db", "site/dados_nuvem/bolao.db"])
    # commit só se houver mudança (git commit falha se nada mudou — tudo bem)
    msg = f"Dados diários {datetime.date.today():%Y-%m-%d}"
    commitou = _shell(f, "git commit", [git, "commit", "-m", msg])
    if commitou:
        _shell(f, "git push", [git, "push", "origin", "HEAD:main"])
    else:
        _log(f, "Nada a commitar (dados sem mudança) — sem push.")


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    hoje = datetime.date.today().isoformat()
    log_path = os.path.join(LOG_DIR, f"ranking_{hoje}.log")
    with open(log_path, "a", encoding="utf-8") as f:
        _log(f, "=" * 50)
        _log(f, "Iniciando atualização diária do ranking")

        # 1) preços BR (fechamento) — atualiza preco_atual (P/L, market cap...)
        _rodar(f, "Coletar fechamento das ações BR",
               os.path.join("financeiro", "br", "coletor_fechamento.py"))

        # 2) ranking BR (Investidor10) — tabela ranking_acoes
        ok = _rodar(f, "Raspar Investidor10 + gravar no banco",
                    os.path.join("financeiro", "ranking_investidor10.py"),
                    "--banco", "--sem-excel")
        if not ok:
            _log(f, "Aviso: scraping BR falhou (seguindo mesmo assim).")

        # 3) ranking US (S&P 500, yfinance) — tabela ranking_acoes_us
        _rodar(f, "Coletar ranking US (S&P 500)",
               os.path.join("financeiro", "ranking_us.py"), "--banco", "--sem-excel")

        # 4) copia os bancos atualizados para o site
        ok2 = _rodar(f, "Copiar bancos para o site",
                     os.path.join("site", "atualizar_dados.py"))
        if not ok2:
            _log(f, "Aviso: cópia para o site falhou.")
            sys.exit(2)

        # 5) publica no site online (push dos bancos leves pro GitHub)
        try:
            publicar_nuvem(f)
        except Exception as e:
            _log(f, f"Aviso: publicação na nuvem falhou: {e}")

        _log(f, "Concluído com sucesso.")


if __name__ == "__main__":
    main()
