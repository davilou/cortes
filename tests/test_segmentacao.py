from cortes.segmentacao import frases
from cortes.tipos import Frase, Palavra


def p(t: str, i: float, f: float) -> Palavra:
    return Palavra(t, i, f)


def test_corta_na_pontuacao_final() -> None:
    ws = [p("Eu", 0, .2), p("avisei.", .2, .5), p("Ele", .6, .8), p("bateu?", .8, 1.0)]
    assert frases(ws) == [Frase(0, "Eu avisei.", 0, .5), Frase(1, "Ele bateu?", .6, 1.0)]


def test_corta_na_pausa_longa_sem_pontuacao() -> None:
    ws = [p("tanto", 0, .3), p("de", .3, .4), p("carro", 1.5, 1.8)]
    assert [f.texto for f in frases(ws, pausa_s=0.8)] == ["tanto de", "carro"]


def test_virgula_nao_corta() -> None:
    ws = [p("Eu", 0, .1), p("avisei,", .1, .3), p("tiozão.", .35, .6)]
    assert len(frases(ws)) == 1


def test_ultima_frase_sem_pontuacao_fecha() -> None:
    assert frases([p("fim", 0, .2)]) == [Frase(0, "fim", 0, .2)]
