from pathlib import Path

import pytest

from cortes.render.assets import apagar_assets
from cortes.render.processo import ErroRender
from cortes.render.recorte_fundo import RECORTE, SCRIPT, args_recorte_fundo, preparar_recorte

PY = Path("py.exe")


class Grava:
    def __init__(self) -> None:
        self.args: list[list[str]] = []

    def rodar(self, args: list[str], cwd: Path | None) -> tuple[int, str]:
        self.args.append(args)
        Path(args[-1]).write_bytes(b"webm")
        return 0, ""


def _assets(tmp_path: Path) -> tuple[Path, Path]:
    assets = tmp_path / "projeto" / "assets"
    assets.mkdir(parents=True)
    (assets / "trecho.mp4").write_bytes(b"x")
    modelo = tmp_path / "u2net.onnx"
    modelo.write_bytes(b"m")
    return assets, modelo


def test_args_chamam_o_script_no_python_do_comfyui() -> None:
    a = args_recorte_fundo(PY, Path("r/s.py"), Path("t.mp4"), Path("m.onnx"), Path("recorte.parcial.webm"))
    assert a == ["py.exe", str(Path("r/s.py")), "t.mp4", "m.onnx", "recorte.parcial.webm"]


def test_recorte_gerado_uma_vez_por_parcial_e_some_com_o_trecho(tmp_path: Path) -> None:
    g, (assets, modelo) = Grava(), _assets(tmp_path)
    for _ in range(2):
        preparar_recorte(assets, tmp_path, PY, modelo, g.rodar)
    assert len(g.args) == 1 and g.args[0][1] == str(tmp_path / SCRIPT)
    assert g.args[0][-1].endswith("recorte.parcial.webm")
    assert (assets / RECORTE).exists() and not list(assets.glob("*.parcial.*"))
    apagar_assets(assets)
    assert not (assets / RECORTE).exists()


def test_sem_modelo_e_erro_claro(tmp_path: Path) -> None:
    assets, _ = _assets(tmp_path)
    with pytest.raises(ErroRender, match="u2net_human_seg"):
        preparar_recorte(assets, tmp_path, PY, tmp_path / "falta.onnx", Grava().rodar)


def test_recorte_que_falha_nao_fica_pela_metade(tmp_path: Path) -> None:
    assets, modelo = _assets(tmp_path)

    def falha(args: list[str], cwd: Path | None) -> tuple[int, str]:
        Path(args[-1]).write_bytes(b"meio")
        return 1, "recorte sem CUDA"

    with pytest.raises(ErroRender, match="recorte da cabeça.*CUDA"):
        preparar_recorte(assets, tmp_path, PY, modelo, falha)
    assert sorted(p.name for p in assets.iterdir()) == ["trecho.mp4"]
