"""
atualizar_dados.py — copia os bancos ORIGINAIS para site/data/.

O site NUNCA lê os bancos originais. Ele lê uma cópia aqui em site/data/.
Assim, o que já funciona (coletores, scripts) nunca é impactado pelo site.

Fluxo seguro:
  1. Você roda seus coletores normalmente (carga_cvm_cda.py, run_all.py...).
  2. Quando quiser que o site mostre os dados novos, roda ESTE script.
  3. Ele copia fundos_cvm.db e financeiro.db para site/data/.

Uso:
    python site/atualizar_dados.py
"""
import os
import shutil
from datetime import datetime

# raiz do projeto = pasta acima de site/
SITE_DIR = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(SITE_DIR)
DATA_DIR = os.path.join(SITE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# (origem, nome de destino) — sempre só LEITURA da origem
BANCOS = [
    (os.path.join(RAIZ, "fundos_cvm", "fundos_cvm.db"), "fundos_cvm.db"),
    (os.path.join(RAIZ, "financeiro", "financeiro.db"), "financeiro.db"),
]


def copiar():
    print("Atualizando dados do site (cópia dos bancos originais)\n")
    ok = 0
    for origem, destino_nome in BANCOS:
        destino = os.path.join(DATA_DIR, destino_nome)
        if not os.path.exists(origem):
            print(f"  ! origem não encontrada (pulando): {origem}")
            continue
        tam = os.path.getsize(origem) / 1024 / 1024
        shutil.copy2(origem, destino)  # copy2 preserva data de modificação
        mod = datetime.fromtimestamp(os.path.getmtime(origem))
        print(f"  ok  {destino_nome:18} {tam:8.1f} MB  (orig. modificado em {mod:%d/%m/%Y %H:%M})")
        ok += 1
    print(f"\n{ok} banco(s) copiado(s) para {DATA_DIR}")


if __name__ == "__main__":
    copiar()
