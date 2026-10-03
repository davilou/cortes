"""f9 Ilustrado de verdade: `claude -p` pela assinatura (deixas e conferência), busca ddgs real,
ffmpeg, rosto no ComfyUI e HyperFrames — minutos por corte. Fora do check padrão.

Precisa de CORTES_EP_REF apontando para o episódio wxCto9WSZcI ("Como se estabilizar com 3 mil de
salário"), que fala de camisa, boné, bota e tênis. O episódio é só lido: vídeo, áudio e palavras
entram por hardlink (ou cópia) numa raiz temporária, e o render grava só lá.
"""
import json
import os
import shutil
import subprocess
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from cortes.cli import MODELO_ROSTO, PY_VISAO
from cortes.render.corte import novo_corte
from cortes.render.ilustracao_cache import ler_ilustracoes
from cortes.render.pipeline import DepRender, renderizar_corte

REPO = Path(__file__).resolve().parents[1]
EP = Path(os.environ.get("CORTES_EP_REF", str(REPO / "episodios" / "wxCto9WSZcI")))
TITULOS = ["Camisa de 700 reais, sério?", "Bota boa por 250, não 600"]


def _cronometrar(f: Callable[..., Any], gasto: dict[str, float], chave: str) -> Callable[..., Any]:
    def medido(*args: Any, **kwargs: Any) -> Any:
        t = time.monotonic()
        try:
            return f(*args, **kwargs)
        finally:
            gasto[chave] += time.monotonic() - t
    return medido


class _BuscaMedida:
    def __init__(self, real: Any, gasto: dict[str, float]) -> None:
        self.images = _cronometrar(real.images, gasto, "busca")


def _dep_medida(gasto: dict[str, float]) -> DepRender:
    npx = shutil.which("npx")
    assert npx
    base = DepRender(PY_VISAO, MODELO_ROSTO, npx)
    return replace(
        base,
        chamar_llm=_cronometrar(base.chamar_llm, gasto, "deixas"),
        chamar_llm_com_read=_cronometrar(base.chamar_llm_com_read, gasto, "conferencia"),
        ddgs=lambda: _BuscaMedida(base.ddgs(), gasto),
        rodar_download=_cronometrar(base.rodar_download, gasto, "download"),
    )


def _preparar_raiz(tmp_path: Path) -> Path:
    pasta = tmp_path / "episodios" / EP.name
    pasta.mkdir(parents=True)
    for arq in ("video.mp4", "audio.wav", "palavras.json"):
        try:
            os.link(EP / arq, pasta / arq)
        except OSError:
            shutil.copy2(EP / arq, pasta / arq)
    shutil.copytree(REPO / "render", tmp_path / "render")
    return pasta


@pytest.mark.lento
@pytest.mark.skipif(not (EP / "candidatos.json").exists(), reason="episódio de referência não baixado")
@pytest.mark.parametrize("titulo", TITULOS)
def test_render_real_ilustrado(tmp_path: Path, titulo: str) -> None:
    pasta = _preparar_raiz(tmp_path)
    cand = next(c for c in json.loads((EP / "candidatos.json").read_text(encoding="utf-8"))
                if c["titulo"] == titulo)
    gasto: dict[str, float] = defaultdict(float)
    t0 = time.monotonic()
    renderizar_corte(pasta, novo_corte(0, cand, "f9"), tmp_path, _dep_medida(gasto))
    total = time.monotonic() - t0

    d = pasta / "cortes" / "0"
    mp4 = d / "short-v1.mp4"
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)]
    dur = float(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    segs = json.loads((d / "recorte.json").read_text(encoding="utf-8"))["segmentos"]
    assert abs(dur - sum(b - a for a, b in segs)) < 0.5

    lido = ler_ilustracoes(d)
    assert lido is not None
    ilus = lido.ilustracoes
    com = [i for i in ilus if i.imagem is not None]
    assert com, "f9 renderizado sem nenhuma imagem"
    assets = d / "projeto" / "assets"
    for i in com:
        assert (assets / f"ilus-{i.k}.jpg").exists()
    html = (d / "projeto" / "index.html").read_text(encoding="utf-8")
    assert html.count('class="clip ilus"') == len(com)

    print(f"\n{titulo}: {len(ilus)} deixa(s), {len(com)} com imagem; mp4 {dur:.2f}s")
    for i in ilus:
        img = i.imagem.name if i.imagem else "SEM IMAGEM"
        print(f"  D{i.k} [{i.deixa.inicio:.2f}-{i.deixa.fim:.2f}] {i.deixa.coisa!r} "
              f"(busca: {i.deixa.busca}) -> {img}: {i.motivo}")
    partes = ", ".join(f"{k} {v:.0f}s" for k, v in sorted(gasto.items()))
    print(f"  tempo: total {total:.0f}s ({partes}; resto = trecho, rosto, folha e render)")

    # CORTES_LENTO_DESTINO=<pasta> copia MP4, folhas e ilustracao.json para <pasta>/<corte>/.
    if "CORTES_LENTO_DESTINO" not in os.environ:
        return
    destino = Path(os.environ["CORTES_LENTO_DESTINO"]) / titulo.split()[0].lower()
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mp4, destino / "f9.mp4")
    shutil.copytree(d / "ilustracao", destino / "ilustracao", dirs_exist_ok=True)
