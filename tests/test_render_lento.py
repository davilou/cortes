"""Render de verdade (ffmpeg + rosto no ComfyUI + HyperFrames): 1–4 min. Fora do check padrão."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from cortes.cli import MODELO_ROSTO, PY_VISAO
from cortes.render.corte import novo_corte
from cortes.render.miniatura import gerar_miniatura
from cortes.render.pipeline import DepRender, renderizar_corte
from cortes.render.processo import rodar_processo
from cortes.render.rosto import ler_rosto, planos

REPO = Path(__file__).resolve().parents[1]
EP = Path(os.environ.get("CORTES_EP_REF", str(REPO / "episodios" / "c5xqNNWFT9w")))
GAMEPLAY_REF = Path(os.environ.get("CORTES_GAMEPLAY_REF", str(REPO / "biblioteca" / "gameplay")))


def _gameplay_ref_videos() -> list[Path]:
    return sorted(GAMEPLAY_REF.glob("*.mp4")) if GAMEPLAY_REF.is_dir() else []


@pytest.mark.lento
@pytest.mark.skipif(not (EP / "candidatos.json").exists(), reason="episódio de referência não baixado")
@pytest.mark.parametrize("formato", ["f7", "f1", "f6", "f5", "f8"])
def test_render_real_do_comediante(tmp_path: Path, formato: str) -> None:
    if formato == "f5" and not _gameplay_ref_videos():
        pytest.skip(f"sem gameplay de referência em {GAMEPLAY_REF} (CORTES_GAMEPLAY_REF)")
    pasta = tmp_path / "episodios" / "c5xqNNWFT9w"
    pasta.mkdir(parents=True)
    for arq in ("video.mp4", "audio.wav", "palavras.json"):
        try:
            os.link(EP / arq, pasta / arq)
        except OSError:
            shutil.copy2(EP / arq, pasta / arq)
    shutil.copytree(REPO / "render", tmp_path / "render")
    if formato == "f5":
        destino_lib = tmp_path / "biblioteca" / "gameplay"
        destino_lib.mkdir(parents=True)
        for video in _gameplay_ref_videos():
            try:
                os.link(video, destino_lib / video.name)
            except OSError:
                shutil.copy2(video, destino_lib / video.name)
    cand = next(c for c in json.loads((EP / "candidatos.json").read_text(encoding="utf-8"))
                if c["titulo"] == "O comediante que mais vende")
    npx = shutil.which("npx")
    assert npx
    renderizar_corte(pasta, novo_corte(0, cand, formato), tmp_path, DepRender(PY_VISAO, MODELO_ROSTO, npx))
    d = pasta / "cortes" / "0"
    mp4 = d / "short-v1.mp4"
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)]
    dur = float(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    segs = json.loads((d / "recorte.json").read_text(encoding="utf-8"))["segmentos"]
    assert abs(dur - sum(b - a for a, b in segs)) < 0.5

    # ler_rosto recusa qualquer coisa que não seja o formato 2 (ErroRender); chegar aqui já confirma.
    rosto = ler_rosto(d / "rosto.json")
    pls = planos(rosto)
    assert pls
    trecho = d / "projeto" / "assets" / "trecho.mp4"
    for p in pls:
        for j in range(len(p.pessoas)):
            mini = d / "miniaturas" / f"p{p.k}-{j}.jpg"
            gerar_miniatura(trecho, mini, p, j, rosto.largura, rosto.altura, rodar_processo)
            assert mini.exists() and mini.stat().st_size > 0

    print(f"planos: {len(pls)}")
    for p in pls:
        pessoas_str = ", ".join(f"x={s.x:.0f} n={s.n}" for s in p.pessoas)
        print(f"  plano {p.k} [{p.ini:.2f}-{p.fim:.2f}]: {len(p.pessoas)} pessoa(s) ({pessoas_str})")
    print(f"duração do mp4: {dur:.2f}s")

    # Para assistir o resultado: CORTES_LENTO_DESTINO=<pasta> copia o MP4 (<formato>.mp4) e as
    # miniaturas para lá, uma subpasta por formato — cada parametrização não sobrescreve a outra.
    if "CORTES_LENTO_DESTINO" not in os.environ:
        return
    destino = Path(os.environ["CORTES_LENTO_DESTINO"])
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mp4, destino / f"{formato}.mp4")
    if (d / "miniaturas").exists():
        shutil.copytree(d / "miniaturas", destino / f"{formato}-miniaturas", dirs_exist_ok=True)
