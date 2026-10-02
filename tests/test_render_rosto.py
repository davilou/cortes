import json
from pathlib import Path

import pytest

from cortes.render.processo import ErroRender
from cortes.render.rosto import Ponto, Rosto, largura_quadro, ler_rosto, medir_rosto, trilha_fixa

R = Rosto(1920, 1080, (Ponto(0.0, 960, 540, False), Ponto(0.25, 980, 540, False),
                       Ponto(2.0, 1800, 500, True), Ponto(2.25, 1800, 520, False)), (2.0,))


def test_trilha_fixa_um_plano_por_intervalo_entre_trocas_reais() -> None:
    assert trilha_fixa(R) == [[0.0, -1184.4, 0.0, 1], [2.0, -2333.3, 0.0, 1]]
    assert largura_quadro(R) == 3413


def test_trilha_fixa_usa_o_instante_real_do_corte_mesmo_sem_ponto_exato() -> None:
    # troca real em t=1.9, mas o primeiro ponto do plano novo só chega em t=2.0
    r = Rosto(1920, 1080, (Ponto(0.0, 960, 540, False), Ponto(2.0, 1800, 500, True)), (1.9,))
    assert [p[0] for p in trilha_fixa(r)] == [0.0, 1.9]


def test_plano_sem_ponto_herda_do_anterior() -> None:
    # corte em 1.0 e 2.0; só o primeiro plano tem ponto (em t=0.0)
    r = Rosto(1920, 1080, (Ponto(0.0, 960, 540, False),), (1.0, 2.0))
    planos = trilha_fixa(r)
    assert len(planos) == 3 and planos[0][1:3] == planos[1][1:3] == planos[2][1:3]


def test_primeiro_plano_sem_ponto_herda_do_proximo_que_tiver() -> None:
    # corte em 1.0; só o segundo plano (a partir de t=1.0) tem ponto
    r = Rosto(1920, 1080, (Ponto(1.5, 1800, 500, True),), (1.0,))
    planos = trilha_fixa(r)
    assert len(planos) == 2 and planos[0][1:3] == planos[1][1:3]


def test_nenhum_plano_com_ponto_e_erro() -> None:
    r = Rosto(1920, 1080, (), ())
    with pytest.raises(ErroRender, match="nenhum plano"):
        trilha_fixa(r)


def test_ler_rosto(tmp_path: Path) -> None:
    arq = tmp_path / "rosto.json"
    arq.write_text(json.dumps({"largura": 1920, "altura": 1080, "cortes": [2.0],
                               "pontos": [{"t": 0.0, "x": 960, "y": 540, "corte": False}]}), encoding="utf-8")
    assert ler_rosto(arq) == Rosto(1920, 1080, (Ponto(0.0, 960, 540, False),), (2.0,))
    arq.write_text(json.dumps({"largura": 1920, "altura": 1080, "pontos": []}), encoding="utf-8")
    with pytest.raises(ErroRender, match="rosto.json"):
        ler_rosto(arq)


def test_ler_rosto_recusa_cortes_nao_crescente(tmp_path: Path) -> None:
    arq = tmp_path / "rosto.json"
    arq.write_text(json.dumps({"largura": 1920, "altura": 1080, "cortes": [2.0, 1.0],
                               "pontos": [{"t": 0.0, "x": 960, "y": 540, "corte": False}]}), encoding="utf-8")
    with pytest.raises(ErroRender, match="rosto.json"):
        ler_rosto(arq)


def test_medir_rosto_chama_o_python_da_visao(tmp_path: Path) -> None:
    vistos: list[list[str]] = []

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        vistos.append(args)
        return 0, ""

    medir_rosto(Path("t.mp4"), Path("r.json"), Path("rosto.py"), Path("py.exe"), Path("m.onnx"), rodar)
    assert vistos == [["py.exe", "rosto.py", "t.mp4", "m.onnx", "r.json"]]
