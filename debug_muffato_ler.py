"""
DEBUG isolado — destrava (senha vazia / owner password) e extrai texto do
demonstrativo financeiro Muffato. Não toca em fundos_cvm.

Uso:
    python debug_muffato_ler.py 2025      # destrava e extrai o ano informado
"""
import os, sys, pikepdf, pdfplumber

BASE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(BASE, "muffato_dem")

ano = sys.argv[1] if len(sys.argv) > 1 else "2025"
src = os.path.join(DIR, f"dfs_finais-muffato-31-12-{ano}.pdf")
dst = os.path.join(DIR, f"muffato-{ano}-LIBERADO.pdf")
txt = os.path.join(DIR, f"muffato-{ano}-texto.txt")

print(f">>> Abrindo {os.path.basename(src)} (senha vazia)")
# pikepdf abre com user-password vazia e regrava sem proteção de permissões
with pikepdf.open(src, password="") as pdf:
    n = len(pdf.pages)
    pdf.save(dst)
print(f"    OK — {n} páginas. Cópia liberada: {os.path.basename(dst)}")

print(">>> Extraindo texto...")
partes = []
with pdfplumber.open(dst) as pdf:
    for i, page in enumerate(pdf.pages, 1):
        t = page.extract_text() or ""
        partes.append(f"\n===== PÁGINA {i} =====\n{t}")
full = "".join(partes)
with open(txt, "w", encoding="utf-8") as f:
    f.write(full)
print(f"    Texto salvo: {os.path.basename(txt)} ({len(full):,} chars)")
