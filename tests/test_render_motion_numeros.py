import pytest

from cortes.render.motion_numeros import foi_dito, nao_ditos, numeros, numeros_da_fala


def _valores(texto: str) -> list[float]:
    return [n.valor for n in numeros(texto)]


@pytest.mark.parametrize("texto, esperado", [
    ("por 400 mil reais, passou 10 anos", [400_000, 10]),
    ("R$ 400 mil", [400_000]),
    ("R$7.500", [7_500]),
    ("+37,5%", [37.5]),
    ("tava valendo 550, sabe assim?", [550]),
    ("quatrocentos mil", [400_000]),
    ("mil e duzentos, mil e quinhentos por mês", [1_200, 1_500]),
    ("3 pau e meio", [3_500]),
    ("três pau e meio", [3_500]),
    ("quatro pau e meio", [4_500]),
    ("nem a pau quitar", []),
    ("entre 3 e 4 mil", [3, 4_000]),
    ("trinta e sete e meio por cento", [37.5]),
    ("cento e vinte e cinco mil", [125_000]),
    ("dois milhões e trezentos mil", [2_300_000]),
    ("um milhão e meio", [1_500_000]),
    ("6 milhões", [6_000_000]),
    ("mil reais", [1_000]),
    ("das seis à meia -noite", [6]),
    ("o equivalente a oito meses", [8]),
    ("12 mil", [12_000]),
    ("1,5 milhão", [1_500_000]),
    ("Oportunidade e localização", []),
])
def test_le_numeros_da_fala_e_da_tela(texto: str, esperado: list[float]) -> None:
    assert _valores(texto) == pytest.approx(esperado)


def test_base_e_o_que_vem_antes_do_multiplicador() -> None:
    assert [(n.valor, n.base) for n in numeros("550 mil, 3 pau e meio")] == [(550_000, 550), (3_500, 3.5)]
    assert numeros("mil e duzentos")[0].base == 1_200   # nada de multiplicador no fim


def test_numero_da_tela_tem_que_ter_sido_dito() -> None:
    fala = numeros_da_fala("comprei por 400 mil reais, passou 10 anos, tava valendo 550".split())
    assert nao_ditos(["R$ 400 mil", "ANO 0", "ANO 10", "R$ 550 mil"], fala) == []
    assert nao_ditos(["+37,5%", "R$ 600 mil"], fala) == ["+37,5%", "600 mil"]


def test_base_dita_nao_sustenta_numero_sem_multiplicador() -> None:
    fala = numeros_da_fala(["400", "mil"])
    assert nao_ditos(["R$ 400"], fala) == ["400"]   # disse 400 mil: "R$ 400" seria outro valor


def test_zero_sempre_passa() -> None:
    assert foi_dito(numeros("0")[0], [])
