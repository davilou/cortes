import json
from pathlib import Path

import pytest

from cortes.render.processo import ErroRender
from cortes.render.rosto import Ponto, Rosto, largura_quadro, ler_rosto, medir_rosto, planos, trilha_fixa

R = Rosto(1920, 1080, (Ponto(0.0, 960, 540, False), Ponto(0.25, 980, 540, False),
                       Ponto(2.0, 1800, 500, True), Ponto(2.25, 1800, 520, False)))


def test_planos_separam_na_troca_de_camera() -> None:
    assert [len(p) for p in planos(R.pontos)] == [2, 2]


def test_trilha_fixa_usa_a_mediana_e_nao_mostra_borda() -> None:
    assert trilha_fixa(R) == [[0.0, -1184.4, 0.0, 1], [2.0, -2333.3, 0.0, 1]]
    assert largura_quadro(R) == 3413


def test_ler_rosto(tmp_path: Path) -> None:
    arq = tmp_path / "rosto.json"
    arq.write_text(json.dumps({"largura": 1920, "altura": 1080,
                               "pontos": [{"t": 0.0, "x": 960, "y": 540, "corte": False}]}), encoding="utf-8")
    assert ler_rosto(arq) == Rosto(1920, 1080, (Ponto(0.0, 960, 540, False),))
    arq.write_text(json.dumps({"largura": 1920, "altura": 1080, "pontos": []}), encoding="utf-8")
    with pytest.raises(ErroRender, match="rosto.json"):
        ler_rosto(arq)


def test_medir_rosto_chama_o_python_da_visao(tmp_path: Path) -> None:
    vistos: list[list[str]] = []

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        vistos.append(args)
        return 0, ""

    medir_rosto(Path("t.mp4"), Path("r.json"), Path("rosto.py"), Path("py.exe"), Path("m.onnx"), rodar)
    assert vistos == [["py.exe", "rosto.py", "t.mp4", "m.onnx", "r.json"]]
