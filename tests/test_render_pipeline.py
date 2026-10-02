import json
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np

from cortes.render.corte import concluir, novo_corte
from cortes.render.pipeline import DepRender, janela, renderizar_corte

REPO = Path(__file__).resolve().parents[1]
ROSTO = {"largura": 1920, "altura": 1080, "cortes": [],
        "pontos": [{"t": 0.0, "x": 960, "y": 540, "corte": False}]}


class Falso:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def rodar(self, args: list[str], cwd: Path | None) -> tuple[int, str]:
        self.chamadas.append(args[0])
        if args[0] == "ffmpeg" or args[0] == "npx":
            Path(args[-1]).write_bytes(b"mp4")
        elif args[0] == "py-visao":
            Path(args[4]).write_text(json.dumps(ROSTO), encoding="utf-8")
        return 0, "ok"

    def dep(self) -> DepRender:
        def tom(audio: Path, ini: float, dur: float) -> np.ndarray:
            t = np.arange(int(dur * 16000)) / 16000
            return (0.5 * np.sin(2 * np.pi * 50 * t)).astype(np.float32)

        return DepRender(Path("py-visao"), Path("m.onnx"), "npx", self.rodar, tom)


def episodio(tmp: Path) -> Path:
    shutil.copytree(REPO / "render", tmp / "render")
    pasta = tmp / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    palavras = [{"texto": "Eu", "inicio": 10.1, "fim": 10.5},
                {"texto": "ganhei.", "inicio": 10.5, "fim": 11.0}]
    (pasta / "palavras.json").write_text(json.dumps(palavras), encoding="utf-8")
    return pasta


C = novo_corte(0, {"inicio": 10.3, "fim": 14.0, "titulo": "T"}, "f7")


def test_janela_da_folga_no_inicio() -> None:
    assert janela(C) == (10.0, 14.0)
    assert janela(replace(C, inicio=0.1)) == (0.0, 14.0)


def test_renderiza_o_corte_ponta_a_ponta(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, C, tmp_path, f.dep())
    d = pasta / "cortes" / "0"
    assert (d / "short-v1.mp4").exists() and f.chamadas == ["ffmpeg", "py-visao", "npx"]
    html = (d / "projeto" / "index.html").read_text(encoding="utf-8")
    assert "{{" not in html and "<span>Eu ganhei.</span>" in html and 'data-duration="4.0"' in html


def test_segunda_versao_reaproveita_trecho_e_rosto(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, C, tmp_path, f.dep())
    renderizar_corte(pasta, concluir(C), tmp_path, f.dep())
    assert f.chamadas == ["ffmpeg", "py-visao", "npx", "npx"]
    assert (pasta / "cortes" / "0" / "short-v2.mp4").exists()


def test_novo_inicio_refaz_trecho_e_rosto(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, C, tmp_path, f.dep())
    renderizar_corte(pasta, replace(concluir(C), inicio=11.0), tmp_path, f.dep())
    assert f.chamadas == ["ffmpeg", "py-visao", "npx", "ffmpeg", "py-visao", "npx"]


def test_rosto_json_apagado_refaz_trecho_mesmo_com_marcador(tmp_path: Path) -> None:
    """O marcador `recorte.json` não basta: se `rosto.json` (ou `trecho.mp4`) não existir mais,
    o cache não pode ser reaproveitado — senão o render seguinte usaria um rosto.json ausente."""
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, C, tmp_path, f.dep())
    (pasta / "cortes" / "0" / "rosto.json").unlink()
    renderizar_corte(pasta, concluir(C), tmp_path, f.dep())
    assert f.chamadas == ["ffmpeg", "py-visao", "npx", "ffmpeg", "py-visao", "npx"]
