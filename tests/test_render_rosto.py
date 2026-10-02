import json
from pathlib import Path

import pytest

from cortes.render.processo import ErroRender
from cortes.render.rosto import (
    Amostra,
    Face,
    Rosto,
    largura_quadro,
    ler_rosto,
    medir_rosto,
    pessoas,
    planos,
    trilha_fixa,
)


def F(x: float, y: float) -> Face:
    return Face(x, y, 80.0, 0.9)


R = Rosto(1920, 1080, (
    Amostra(0.0, (F(960, 540),)), Amostra(0.25, (F(980, 540),)), Amostra(1.9, ()),
    Amostra(2.0, (F(1800, 500), F(400, 520))), Amostra(2.25, (F(1800, 520), F(420, 500))),
    Amostra(2.5, (F(1790, 510),)),
), (1.9,))


def test_pessoas_separam_pela_posicao_x() -> None:
    ps = pessoas([F(1800, 500), F(400, 520), F(1800, 520), F(420, 500), F(1790, 510)], 1920)
    assert [(p.x, p.n) for p in ps] == [(410.0, 2), (1800.0, 3)]


def test_pessoa_com_poucas_deteccoes_e_ruido() -> None:
    ps = pessoas([F(900, 500)] * 10 + [F(100, 500)], 1920)
    assert [p.x for p in ps] == [900.0]


def test_pessoas_nao_encadeiam_por_deteccoes_intermediarias() -> None:
    """Vão medido contra o PRIMEIRO rosto do grupo, não o último (single-linkage emendava duas
    pessoas através de uma cadeia de detecções intermediárias). largura 1920, SEPARA 0.08 → 153,6px.
    400→550: 150 ≤ 153,6 (mesmo grupo, ancorado em 400); 550→700: 300 > 153,6 (grupo novo, ancorado
    em 700); 700→850: 150 ≤ 153,6 (mesmo grupo); 850→1000: 300 > 153,6 (grupo novo, ancorado em
    1000). Os 3 grupos resultantes têm n=6 (mediana 400), n=2 (mediana 775) e n=5 (mediana 1000);
    o do meio (n=2) não cai no filtro de ruído porque 2 ≥ 0,2×6=1,2 — as 3 pessoas sobrevivem."""
    faces = [F(400, 500)] * 5 + [F(550, 500), F(700, 500), F(850, 500)] + [F(1000, 500)] * 5
    ps = pessoas(faces, 1920)
    assert [(p.x, p.n) for p in ps] == [(400.0, 6), (775.0, 2), (1000.0, 5)]


def test_planos_e_padrao() -> None:
    pl = planos(R)
    assert [(p.k, p.ini, len(p.pessoas), p.padrao) for p in pl] == [(0, 0.0, 1, 0), (1, 1.9, 2, 1)]
    assert pl[1].fim == 2.75


def test_trilha_fixa_padrao_e_escolha() -> None:
    assert trilha_fixa(R, {}) == [[0.0, -1184.4, 0.0, 1], [1.9, -2333.3, 0.0, 1]]
    assert trilha_fixa(R, {1: 0}) == [[0.0, -1184.4, 0.0, 1], [1.9, -188.9, 0.0, 1]]
    assert largura_quadro(R) == 3413


def test_escolha_inexistente_e_erro() -> None:
    with pytest.raises(ErroRender, match="pessoa 5"):
        trilha_fixa(R, {1: 5})


def test_escolha_de_plano_sem_pessoa_e_erro() -> None:
    with pytest.raises(ErroRender, match="plano 2"):
        trilha_fixa(R, {2: 0})


def test_plano_sem_rosto_herda_o_anterior() -> None:
    r = Rosto(1920, 1080, (Amostra(0.0, (F(960, 540),)), Amostra(1.5, ()), Amostra(2.2, (F(1800, 500),))),
              (1.0, 2.0))
    assert [t[1] for t in trilha_fixa(r, {})] == [-1166.7, -1166.7, -2333.3]


def test_ler_rosto_formato_2(tmp_path: Path) -> None:
    arq = tmp_path / "rosto.json"
    dados = {"formato": 2, "largura": 1920, "altura": 1080, "cortes": [1.9],
             "amostras": [{"t": 0.0, "rostos": [{"x": 960, "y": 540, "r": 80, "conf": 0.9}]},
                          {"t": 2.0, "rostos": []}]}
    arq.write_text(json.dumps(dados), encoding="utf-8")
    esperado = Rosto(1920, 1080, (Amostra(0.0, (Face(960, 540, 80, 0.9),)), Amostra(2.0, ())), (1.9,))
    assert ler_rosto(arq) == esperado


@pytest.mark.parametrize("dados, erro", [
    ({"largura": 1920, "altura": 1080, "pontos": [], "cortes": []}, "formato"),
    ({"formato": 2, "largura": 1920, "altura": 1080, "cortes": [], "amostras": [{"t": 0.0, "rostos": []}]},
     "nenhuma amostra"),
    ({"formato": 2, "largura": 1920, "altura": 1080, "cortes": [2.0, 1.0], "amostras": []}, "cortes"),
])
def test_ler_rosto_invalido(tmp_path: Path, dados: dict[str, object], erro: str) -> None:
    arq = tmp_path / "rosto.json"
    arq.write_text(json.dumps(dados), encoding="utf-8")
    with pytest.raises(ErroRender, match=erro):
        ler_rosto(arq)


def test_medir_rosto_chama_o_python_da_visao() -> None:
    vistos: list[list[str]] = []

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        vistos.append(args)
        return 0, ""

    medir_rosto(Path("t.mp4"), Path("r.json"), Path("rosto.py"), Path("py.exe"), Path("m.onnx"), rodar)
    assert vistos == [["py.exe", "rosto.py", "t.mp4", "m.onnx", "r.json"]]
