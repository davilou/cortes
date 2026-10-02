from pathlib import Path

import pytest

from cortes.render.miniatura import args_miniatura, gerar_miniatura
from cortes.render.previa import RUNTIME, com_runtime
from cortes.render.processo import ErroRender
from cortes.render.rosto import Pessoa, Plano


def test_args_recortam_quadrado_em_volta_do_rosto() -> None:
    args = args_miniatura(Path("t.mp4"), Path("m.jpg"), 1.5, Pessoa(960, 540, 80, 3, 0.9), 1920, 1080)
    assert args[args.index("-ss") + 1] == "1.500"
    assert args[args.index("-vf") + 1] == "crop=256:256:832:412,scale=160:160"


def test_quadrado_nao_sai_do_quadro() -> None:
    args = args_miniatura(Path("t.mp4"), Path("m.jpg"), 0.0, Pessoa(20, 1070, 30, 1, 0.9), 1920, 1080)
    assert args[args.index("-vf") + 1] == "crop=160:160:0:920,scale=160:160"


def test_gerar_usa_o_meio_do_plano(tmp_path: Path) -> None:
    vistos: list[list[str]] = []

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        vistos.append(args)
        Path(args[-1]).write_bytes(b"jpg")
        return 0, ""

    destino = tmp_path / "mini" / "p0-0.jpg"
    plano = Plano(0, 1.0, 3.0, (Pessoa(960, 540, 80, 3, 0.9),), 0)
    gerar_miniatura(Path("t.mp4"), destino, plano, 0, 1920, 1080, rodar)
    assert destino.read_bytes() == b"jpg" and vistos[0][vistos[0].index("-ss") + 1] == "2.000"


def test_gerar_pessoa_inexistente_e_erro(tmp_path: Path) -> None:
    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        raise AssertionError("não deveria rodar o ffmpeg")

    plano = Plano(0, 1.0, 3.0, (Pessoa(960, 540, 80, 3, 0.9),), 0)
    with pytest.raises(ErroRender, match="pessoa 1"):
        gerar_miniatura(Path("t.mp4"), tmp_path / "m.jpg", plano, 1, 1920, 1080, rodar)


def test_runtime_entra_logo_depois_do_head() -> None:
    esperado = f'<html>\n  <head>\n<script src="{RUNTIME}"></script>\n<meta>'
    assert com_runtime("<html>\n  <head>\n<meta>") == esperado
    with pytest.raises(ErroRender, match="<head>"):
        com_runtime("<html></html>")
