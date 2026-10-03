from pathlib import Path

import pytest

from cortes.render.assets import (
    apagar_assets,
    args_fundo,
    args_gameplay,
    escolher_gameplay,
    preparar_assets,
)
from cortes.render.processo import ErroRender


def test_args_do_fundo_desfocado() -> None:
    args = args_fundo(Path("trecho.mp4"), Path("fundo.parcial.mp4"))
    assert args[:6] == ["ffmpeg", "-v", "error", "-y", "-i", "trecho.mp4"]
    vf = args[args.index("-vf") + 1]
    assert vf == "scale=540:960:force_original_aspect_ratio=increase,crop=540:960,boxblur=20:2"
    assert "-an" in args and args[-1] == "fundo.parcial.mp4"


def test_args_do_gameplay_repetem_ate_a_duracao_do_short() -> None:
    args = args_gameplay(Path("orbital.mp4"), Path("g.parcial.mp4"), 47.25)
    assert args[args.index("-stream_loop") + 1] == "-1"
    assert args.index("-stream_loop") < args.index("-i") and args[args.index("-i") + 1] == "orbital.mp4"
    assert args[args.index("-t") + 1] == "47.250"
    assert args[args.index("-vf") + 1] == "scale=1708:960:force_original_aspect_ratio=increase,crop=1708:960"
    assert "-an" in args and args[-1] == "g.parcial.mp4"


def test_escolha_do_gameplay_e_deterministica(tmp_path: Path) -> None:
    for nome in ("b.mp4", "a.mp4", "c.mp4"):
        (tmp_path / nome).write_bytes(b"x")
    (tmp_path / "leia.txt").write_text("não é vídeo", encoding="utf-8")
    assert [escolher_gameplay(tmp_path, i).name for i in range(4)] == ["a.mp4", "b.mp4", "c.mp4", "a.mp4"]


@pytest.mark.parametrize("criar", [False, True])
def test_sem_gameplay_e_erro_claro(tmp_path: Path, criar: bool) -> None:
    pasta = tmp_path / "gameplay"
    if criar:
        pasta.mkdir()
    with pytest.raises(ErroRender, match="sem gameplay em biblioteca/gameplay: ponha um .mp4 lá"):
        escolher_gameplay(pasta, 0)


class Grava:
    def __init__(self) -> None:
        self.args: list[list[str]] = []

    def rodar(self, args: list[str], cwd: Path | None) -> tuple[int, str]:
        self.args.append(args)
        Path(args[-1]).write_bytes(b"mp4")
        return 0, "ok"


def test_f7_e_f1_nao_tem_asset_extra(tmp_path: Path) -> None:
    g = Grava()
    for formato in ("f7", "f1", "f6"):
        preparar_assets(tmp_path / "assets", formato, 0, 10.0, tmp_path, g.rodar)
    assert g.args == []


def test_asset_so_e_gerado_se_faltar_e_some_com_o_trecho(tmp_path: Path) -> None:
    g, assets = Grava(), tmp_path / "projeto" / "assets"
    assets.mkdir(parents=True)
    (tmp_path / "biblioteca" / "gameplay").mkdir(parents=True)
    (tmp_path / "biblioteca" / "gameplay" / "orbital.mp4").write_bytes(b"x")
    for _ in range(2):
        preparar_assets(assets, "f8", 3, 10.0, tmp_path, g.rodar)
        preparar_assets(assets, "f5", 3, 10.0, tmp_path, g.rodar)
    assert len(g.args) == 2 and (assets / "fundo.mp4").exists() and (assets / "gameplay.mp4").exists()
    assert not list(assets.glob("*.parcial.mp4"))
    apagar_assets(assets)
    assert not (assets / "fundo.mp4").exists() and not (assets / "gameplay.mp4").exists()


def test_asset_que_falha_nao_fica_pela_metade(tmp_path: Path) -> None:
    def falha(args: list[str], cwd: Path | None) -> tuple[int, str]:
        Path(args[-1]).write_bytes(b"meio")
        return 1, "ruim"

    with pytest.raises(ErroRender, match="fundo desfocado"):
        preparar_assets(tmp_path, "f8", 0, 10.0, tmp_path, falha)
    assert list(tmp_path.iterdir()) == []
