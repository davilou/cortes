from datetime import date, datetime

import pytest

from cortes.painel.metodo import Medida, montar_linhas, views_7d
from cortes.painel.publicados import Etiquetas, Publicado
from cortes.painel.retratos import Retrato, VideoRetrato

PUB = date(2026, 10, 1)   # dia 7 = 2026-10-08


def d(dia: int) -> date:
    return date(2026, 10, dia)


def test_interpola_entre_retratos() -> None:
    assert views_7d(PUB, [(d(5), 100), (d(9), 300)]) == Medida("medido", 250.0)


def test_retrato_no_proprio_dia_7() -> None:
    assert views_7d(PUB, [(d(5), 100), (d(8), 420), (d(20), 900)]) == Medida("medido", 420.0)


def test_parte_de_zero_na_publicacao() -> None:
    assert views_7d(PUB, [(d(11), 1000)]) == Medida("medido", pytest.approx(700.0))


def test_lacuna_maior_que_3_dias_e_estimado() -> None:
    assert views_7d(PUB, [(d(12), 1100)]) == Medida("estimado", pytest.approx(700.0))


def test_sem_retrato_depois_do_dia_7_esta_maturando() -> None:
    assert views_7d(PUB, [(d(5), 100)]) == Medida("maturando", None)


def test_ignora_retrato_anterior_a_publicacao_e_usa_o_do_dia_do_lancamento() -> None:
    assert views_7d(PUB, [(date(2026, 9, 28), 999), (d(1), 50), (d(9), 450)]) == \
        Medida("medido", pytest.approx(50 + 400 * 7 / 8))


def retrato(conta: str, dia: int, videos: list[tuple[str, int, int]]) -> Retrato:
    """videos = (id, dia de publicação em outubro, views acumuladas)."""
    return Retrato(conta, datetime(2026, 10, dia, 9), tuple(
        VideoRetrato(vid, f"T {vid}", d(pub), 30.0, views, 80.0, 24.0, 1) for vid, pub, views in videos))


def test_relativo_e_views_7d_sobre_a_mediana_da_conta() -> None:
    rs = {"grana": [retrato("grana", 20, [("a", 1, 100), ("b", 1, 200), ("c", 1, 400)])]}
    linhas = {ln.video_id: ln for ln in montar_linhas(rs, [])}
    assert linhas["c"].rel == pytest.approx(2.0) and linhas["a"].rel == pytest.approx(0.5)


def test_conta_com_menos_de_3_medidos_fica_sem_base() -> None:
    rs = {"grana": [retrato("grana", 20, [("a", 1, 100), ("b", 1, 200), ("m", 18, 50)])]}
    linhas = {ln.video_id: ln for ln in montar_linhas(rs, [])}
    assert linhas["a"].rel is None and linhas["m"].medida.estado == "maturando"


def test_ligado_traz_etiquetas_e_sem_ligacao_vem_vazio() -> None:
    rs = {"grana": [retrato("grana", 20, [("a", 1, 100), ("b", 1, 200), ("c", 1, 400)])]}
    p = Publicado("a", "grana", d(1), "testes/f7-x", Etiquetas("f7", ("humor",), "PrimoCast"))
    linhas = {ln.video_id: ln for ln in montar_linhas(rs, [p])}
    assert linhas["a"].etiquetas == p.etiquetas and linhas["a"].corte == "testes/f7-x"
    assert linhas["b"].etiquetas is None and linhas["b"].corte is None


def test_usa_o_ultimo_retrato_para_totais() -> None:
    rs = {"grana": [retrato("grana", 5, [("a", 1, 100)]), retrato("grana", 9, [("a", 1, 300)])]}
    (linha,) = montar_linhas(rs, [])
    assert linha.views == 300 and linha.medida == Medida("medido", 250.0)
