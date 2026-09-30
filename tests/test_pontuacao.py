import pytest

from cortes.detector.pontuacao import abertura_energetica, converter, nota_ponderada, percentil
from cortes.perfil import CRITERIOS, Perfil
from cortes.tipos import Frase

PERFIL = Perfil("f", "t", {"gancho_3s": .3, "autocontido": .25, "espanto": .2,
                           "historia_ou_virada": .1, "fechamento": .15},
                {"humor": "faz rir", "numero_na_primeira_frase": "número na abertura"},
                {"palestra_ou_palco": "palco"}, 20, 90, [], [])
FRASES = [Frase(0, "Nenhuma força aérea luta contra eles.", 0, 10),
          Frase(1, "Mas isso é outra conversa.", 10, 25),
          Frase(2, "E acabou.", 25, 40),
          Frase(3, "Juro de 0,7% na Europa.", 100, 130),
          Frase(4, "Eu vendi a casa.", 130, 150),
          Frase(5, "Fiquei sem nada.", 150, 170)]
ENERGIA_CONSTANTE = [0.1] * 400   # toda abertura atinge o limiar e ganha +3


def bruto(ini: int, fim: int, notas: int = 4, dentro_do_tema: bool = True,
          bonus: list[str] | None = None, pen: list[str] | None = None,
          abre_com: str | None = None) -> dict:  # type: ignore[type-arg]
    if abre_com is None:
        abre_com = " ".join(FRASES[ini].texto.split()[:4]) if 0 <= ini < len(FRASES) else "x"
    return {"frase_inicio": ini, "frase_fim": fim, "abre_com": abre_com, "justificativa": "j",
            "dentro_do_tema": dentro_do_tema, "notas": dict.fromkeys(CRITERIOS, notas),
            "bonus": bonus or [], "penalidades": pen or [], "titulo": "t"}


def test_nota_ponderada_vai_de_0_a_100() -> None:
    assert nota_ponderada(dict.fromkeys(CRITERIOS, 1), PERFIL.rubrica) == 0.0
    assert nota_ponderada(dict.fromkeys(CRITERIOS, 5), PERFIL.rubrica) == 100.0
    assert nota_ponderada(dict.fromkeys(CRITERIOS, 3), PERFIL.rubrica) == 50.0


def test_percentil_interpola_como_numpy() -> None:
    assert percentil([1, 2, 3, 4], 0.75) == 3.25


def test_percentil_de_lista_vazia_levanta() -> None:
    with pytest.raises(ValueError, match="energia vazia"):
        percentil([], 0.75)


def test_abertura_energetica_olha_os_3_primeiros_segundos() -> None:
    energia = [0.1] * 10 + [0.9] * 6 + [0.1] * 10   # janelas de 0,5 s; pico entre 5 s e 8 s
    assert abertura_energetica(5.0, energia, limiar=0.5) is True
    assert abertura_energetica(0.0, energia, limiar=0.5) is False


def test_abertura_alem_da_energia_levanta() -> None:
    with pytest.raises(ValueError, match="energia mais curta que o episódio"):
        abertura_energetica(100.0, [0.1] * 10, limiar=0.1)


def test_converter_aceita_ordena_e_aplica_bonus_penalidade() -> None:
    aceitos, descartes = converter(
        {"candidatos": [bruto(0, 2), bruto(3, 3, bonus=["humor"]), bruto(0, 0, pen=["palestra_ou_palco"])]},
        FRASES, PERFIL, ENERGIA_CONSTANTE)
    assert [c.frase_inicio for c in aceitos] == [3, 0]           # 75+5+3 antes de 75+3
    assert aceitos[0].nota_final == 83.0 and aceitos[0].inicio == 100 and aceitos[0].fim == 130
    assert descartes == [{**bruto(0, 0, pen=["palestra_ou_palco"]), "motivo": "duração 10s fora de 20-90s"}]


def test_energia_so_premia_abertura_acima_do_limiar() -> None:
    energia = [0.0] * 6 + [1.0] * 394   # silêncio só nos 3 s iniciais do episódio
    aceitos, _ = converter({"candidatos": [bruto(0, 2), bruto(3, 3)]}, FRASES, PERFIL, energia)
    assert {c.frase_inicio: c.nota_final for c in aceitos} == {3: 78.0, 0: 75.0}


def test_bonus_repetido_conta_uma_vez() -> None:
    aceitos, _ = converter({"candidatos": [bruto(3, 3, bonus=["humor", "humor"])]},
                           FRASES, PERFIL, ENERGIA_CONSTANTE)
    assert aceitos[0].nota_final == 83.0 and aceitos[0].bonus == ["humor"]


def test_nota_final_nao_passa_de_100() -> None:
    aceitos, _ = converter({"candidatos": [bruto(3, 3, notas=5, bonus=list(PERFIL.bonus))]},
                           FRASES, PERFIL, ENERGIA_CONSTANTE)
    assert aceitos[0].nota_final == 100.0


def test_nota_final_nao_fica_negativa() -> None:
    aceitos, _ = converter({"candidatos": [bruto(3, 3, notas=1, pen=["palestra_ou_palco"])]},
                           FRASES, PERFIL, [0.0] * 200 + [1.0] * 200)
    assert aceitos[0].nota_final == 0.0


def test_sobreposto_pior_e_descartado() -> None:
    aceitos, descartes = converter({"candidatos": [bruto(3, 4), bruto(3, 5, notas=5)]},
                                   FRASES, PERFIL, ENERGIA_CONSTANTE)
    assert [(c.frase_inicio, c.frase_fim) for c in aceitos] == [(3, 5)]
    assert descartes == [{**bruto(3, 4), "motivo": "sobrepõe F3-F5"}]


def test_sobreposicao_de_ate_metade_do_menor_e_aceita() -> None:
    # F3-F4 = 100-150 s, F4-F5 = 130-170 s: interseção 20 s = 50% do menor (40 s)
    aceitos, descartes = converter({"candidatos": [bruto(3, 4), bruto(4, 5)]},
                                   FRASES, PERFIL, ENERGIA_CONSTANTE)
    assert len(aceitos) == 2 and descartes == []


def test_abre_com_normaliza_caixa_e_pontuacao() -> None:
    aceitos, _ = converter({"candidatos": [bruto(0, 2, abre_com="“nenhuma  força, aérea…")]},
                           FRASES, PERFIL, ENERGIA_CONSTANTE)
    assert len(aceitos) == 1


def test_converter_descarta_com_motivo_visivel() -> None:
    aceitos, descartes = converter({"candidatos": [
        bruto(1, 2),                 # começa com "Mas"
        bruto(0, 2, dentro_do_tema=False),  # fora do tema
        bruto(2, 9),                 # índice inexistente
        bruto(2, 1),                 # fim antes do início
        bruto(0, 3),                 # 130 s, acima do máximo
        bruto(0, 2, abre_com="Juro de 0,7% na"),  # índice não bate com o texto
    ]}, FRASES, PERFIL, ENERGIA_CONSTANTE)
    assert aceitos == []
    assert [d["motivo"] for d in descartes] == [
        "começa no meio: 'Mas isso é outra conversa.'", "fora do tema",
        "índices inválidos 2-9", "índices inválidos 2-1", "duração 130s fora de 20-90s",
        "abre_com não bate com F0: 'Juro de 0,7% na'"]
