"""Render de verdade (ffmpeg + rosto no ComfyUI + HyperFrames): 1–4 min. Fora do check padrão."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from cortes.cli import MODELO_ROSTO, PY_VISAO
from cortes.render.corte import novo_corte
from cortes.render.pipeline import DepRender, renderizar_corte

REPO = Path(__file__).resolve().parents[1]
EP = Path(os.environ.get("CORTES_EP_REF", str(REPO / "episodios" / "c5xqNNWFT9w")))


@pytest.mark.lento
@pytest.mark.skipif(not (EP / "candidatos.json").exists(), reason="episódio de referência não baixado")
def test_render_real_do_comediante(tmp_path: Path) -> None:
    pasta = tmp_path / "episodios" / "c5xqNNWFT9w"
    pasta.mkdir(parents=True)
    for arq in ("video.mp4", "audio.wav", "palavras.json"):
        try:
            os.link(EP / arq, pasta / arq)
        except OSError:
            shutil.copy2(EP / arq, pasta / arq)
    shutil.copytree(REPO / "render", tmp_path / "render")
    cand = next(c for c in json.loads((EP / "candidatos.json").read_text(encoding="utf-8"))
                if c["titulo"] == "O comediante que mais vende")
    npx = shutil.which("npx")
    assert npx
    renderizar_corte(pasta, novo_corte(0, cand, "f7"), tmp_path, DepRender(PY_VISAO, MODELO_ROSTO, npx))
    mp4 = pasta / "cortes" / "0" / "short-v1.mp4"
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)]
    dur = float(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    segs = json.loads((pasta / "cortes" / "0" / "recorte.json").read_text(encoding="utf-8"))["segmentos"]
    assert abs(dur - sum(b - a for a, b in segs)) < 0.5
