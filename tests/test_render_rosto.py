import json
from pathlib import Path

import pytest

from cortes.render.processo import ErroRender
from cortes.render.rosto import (
    ALVO_METADE,
    JANELA_METADE,
    Amostra,
    Face,
    Rosto,
    escala_metade,
    largura_quadro,
    ler_rosto,
    medir_rosto,
    pessoas,
    planos,
    quadro_metade,
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


def test_padrao_entre_pessoas_com_deteccoes_parecidas_e_o_maior_rosto() -> None:
    """Render real do f7 (wxCto9WSZcI, "Gastava 400 em papel de cigarro"): no plano aberto, o rosto
    na TV do estúdio (r 76, 196 detecções) ganhava das pessoas da mesa (r 142 e 105, 189 e 184) por
    poucas detecções. Com detecções parecidas (≥ PARECIDAS × a maior), vale o maior rosto."""
    tv, mesa, henrique = Face(1097, 135, 76, 0.81), Face(1817, 347, 142, 0.88), Face(171, 424, 105, 0.9)
    r = Rosto(1920, 1080, tuple(Amostra(i * 0.25, (tv, mesa, henrique)) for i in range(180))
              + tuple(Amostra(45 + i * 0.25, (tv,)) for i in range(10)), ())
    assert planos(r)[0].padrao == 2   # pessoas da esquerda para a direita: henrique, tv, mesa
    poucas = Rosto(1920, 1080, tuple(Amostra(i * 0.25, (tv,)) for i in range(100))
                   + tuple(Amostra(25 + i * 0.25, (tv, mesa)) for i in range(40)), ())
    assert planos(poucas)[0].padrao == 0   # o maior rosto com poucas detecções não ganha


def test_trilha_fixa_padrao_e_escolha() -> None:
    assert trilha_fixa(R, {}) == [[0.0, -1184.4, 0.0, 1], [1.9, -2333.3, 0.0, 1]]
    assert trilha_fixa(R, {1: 0}) == [[0.0, -1184.4, 0.0, 1], [1.9, -188.9, 0.0, 1]]
    assert largura_quadro(R) == 3413


def _reduzido(r: Rosto, f: float) -> Rosto:
    return Rosto(round(r.largura * f), round(r.altura * f),
                 tuple(Amostra(a.t, tuple(Face(x.x * f, x.y * f, x.r * f, x.conf) for x in a.rostos))
                       for a in r.amostras), r.cortes)


@pytest.mark.parametrize("fator, escala", [(1.0, 1.0), (2 / 3, 1.5)])
def test_trilha_da_metade_de_cima_em_1080p_e_720p(fator: float, escala: float) -> None:
    """f5 (gameplay): quem fala na metade de cima, janela 1080×960, rosto em (540, 380) e a fonte
    a 1080 de altura (escala 1,0 em 1080p, como o protótipo; 1,5 em 720p)."""
    r = _reduzido(R, fator)
    e = escala_metade(r)
    assert e == pytest.approx(escala) and quadro_metade(r) == (1920, 1080)
    assert trilha_fixa(r, {}, JANELA_METADE, ALVO_METADE, e) == [[0.0, -430.0, -120.0, 1],
                                                                 [1.9, -840.0, -120.0, 1]]


def test_escala_metade_cobre_a_largura_da_janela_em_fonte_vertical() -> None:
    """Fonte mais estreita que a janela (ex.: câmera já em 9:16) com a escala antiga (só pela
    altura) dava um quadro mais magro que `JANELA_METADE` — sobrava borda preta nas laterais
    (revisão formatos novos, item 2). Com a escala cobrindo também a largura, não sobra."""
    r = Rosto(1080, 1920, (Amostra(0.0, (F(540, 960),)),), ())
    e = escala_metade(r)
    qw, qh = quadro_metade(r)
    assert qw >= JANELA_METADE[0] and qh >= JANELA_METADE[1]
    [[_, x, y, _]] = trilha_fixa(r, {}, JANELA_METADE, ALVO_METADE, e)
    jw, jh = JANELA_METADE
    assert jw - qw <= x <= 0 and jh - qh <= y <= 0


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
