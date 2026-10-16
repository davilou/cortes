"""Render real do f10 num corte do Sardinha (Sobe no boato, 150,5–196,6 s): o mesmo caminho do painel.

Uso (raiz do repo): python testes/f10/render_real.py [inicio fim]
"""
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path

from cortes.cli import MODELO_ROSTO, PY_VISAO
from cortes.render.corte import Edicoes, novo_corte
from cortes.render.pipeline import DepRender, renderizar_corte

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "episodios" / "xz6MsXxanP8"

ini, fim = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) == 3 else (150.5, 196.55)
c = novo_corte(0, {"inicio": ini, "fim": fim, "titulo": "Sobe no boato, cai no fato"}, "f10")
c = replace(c, edicoes=Edicoes(trilha="A"))
npx = shutil.which("npx")
assert npx, "npx fora do PATH"
t0 = time.time()
renderizar_corte(PASTA, c, RAIZ, DepRender(PY_VISAO, MODELO_ROSTO, npx))
print(f"ok em {time.time() - t0:.0f}s")
