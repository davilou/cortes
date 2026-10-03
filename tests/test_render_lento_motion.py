"""f3 Motion de verdade: `claude -p` pela assinatura (cenas), ffmpeg, rosto e HyperFrames — minutos
por corte. Fora do check padrão. É o teste cego do plano E (2026-10-03-motion).

Precisa de CORTES_EPISODIOS apontando para a pasta com os episódios c5xqNNWFT9w (o corte "400 mil
reais em 10 anos" do protótipo feito à mão) e wxCto9WSZcI (um tema fora do protótipo). Os episódios
são só lidos: vídeo, áudio e palavras entram por hardlink (ou cópia) numa raiz temporária, e o
render grava só lá. CORTES_LENTO_DESTINO=<pasta> copia o MP4 (f3-<nome>.mp4) e o cenas.json.
"""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from cortes.cli import MODELO_ROSTO, PY_VISAO
from cortes.render.corte import novo_corte
from cortes.render.motion_cache import ler_cenas
from cortes.render.pipeline import DepRender, renderizar_corte

REPO = Path(__file__).resolve().parents[1]
EPISODIOS = Path(os.environ.get("CORTES_EPISODIOS", str(REPO / "episodios")))
CORTES = [("c5xqNNWFT9w", "400 mil reais em 10 anos", "400mil"),
          ("wxCto9WSZcI", "Uber à noite pagou a dívida", "uber")]


def _preparar_raiz(tmp_path: Path, ep: str) -> Path:
    pasta = tmp_path / "episodios" / ep
    pasta.mkdir(parents=True)
    for arq in ("video.mp4", "audio.wav", "palavras.json"):
        try:
            os.link(EPISODIOS / ep / arq, pasta / arq)
        except OSError:
            shutil.copy2(EPISODIOS / ep / arq, pasta / arq)
    shutil.copytree(REPO / "render", tmp_path / "render")
    return pasta


def _duracao(mp4: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)]
    return float(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)


@pytest.mark.lento
@pytest.mark.parametrize("ep, titulo, nome", CORTES)
def test_render_real_motion(tmp_path: Path, ep: str, titulo: str, nome: str) -> None:
    if not (EPISODIOS / ep / "candidatos.json").exists():
        pytest.skip(f"episódio {ep} não baixado em {EPISODIOS} (CORTES_EPISODIOS)")
    pasta = _preparar_raiz(tmp_path, ep)
    cand = next(c for c in json.loads((EPISODIOS / ep / "candidatos.json").read_text(encoding="utf-8"))
                if c["titulo"] == titulo)
    npx = shutil.which("npx")
    assert npx
    t0 = time.monotonic()
    renderizar_corte(pasta, novo_corte(0, cand, "f3"), tmp_path, DepRender(PY_VISAO, MODELO_ROSTO, npx))
    total = time.monotonic() - t0

    d = pasta / "cortes" / "0"
    mp4 = d / "short-v1.mp4"
    segs = json.loads((d / "recorte.json").read_text(encoding="utf-8"))["segmentos"]
    dur = _duracao(mp4)
    assert abs(dur - sum(b - a for a, b in segs)) < 0.5
    lido = ler_cenas(d)
    assert lido is not None and lido.resultado.cenas
    html = (d / "projeto" / "index.html").read_text(encoding="utf-8")
    assert all(f'id="m{c.k}"' in html for c in lido.resultado.cenas)

    print(f"\n{titulo}: {len(lido.resultado.cenas)} cena(s); mp4 {dur:.2f}s; total {total:.0f}s")
    for c in lido.resultado.cenas:
        print(f"  C{c.k} [{c.inicio:.2f}-{c.fim:.2f}] {c.componente}: {c.params} batidas {c.batidas}")
    for x in lido.resultado.descartadas:
        print(f"  FORA [{x.inicio:.2f}-{x.fim:.2f}] {x.componente}: {x.motivo} ({x.params})")

    if "CORTES_LENTO_DESTINO" not in os.environ:
        return
    destino = Path(os.environ["CORTES_LENTO_DESTINO"])
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mp4, destino / f"f3-{nome}.mp4")
    shutil.copy2(d / "motion" / "cenas.json", destino / f"cenas-{nome}.json")
    shutil.copy2(d / "projeto" / "index.html", destino / f"index-{nome}.html")
