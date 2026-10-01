from datetime import date

import pytest

from cortes.painel.metodo import Medida, views_7d

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
