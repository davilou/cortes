from cortes.detector.pontuacao import abertura_energetica, converter, nota_ponderada, percentil
from cortes.perfil import CRITERIOS, Perfil
from cortes.tipos import Frase

PERFIL = Perfil("f", "t", {"gancho_3s": .3, "autocontido": .25, "espanto": .2,
                           "historia_ou_virada": .1, "fechamento": .15},
                ["humor"], ["palestra_ou_palco"], 20, 90, [], [])
FRASES = [Frase(0, "Nenhuma força aérea luta contra eles.", 0, 10),
          Frase(1, "Mas isso é outra conversa.", 10, 25),
          Frase(2, "E acabou.", 25, 40),
          Frase(3, "Juro de 0,7% na Europa.", 100, 130)]


def bruto(ini: int, fim: int, notas: int = 4, dentro_do_tema: bool = True,
          bonus: list[str] | None = None, pen: list[str] | None = None) -> dict:  # type: ignore[type-arg]
    return {"frase_inicio": ini, "frase_fim": fim, "notas": dict.fromkeys(CRITERIOS, notas),
            "dentro_do_tema": dentro_do_tema, "bonus": bonus or [], "penalidades": pen or [],
            "justificativa": "j", "titulo": "t"}


def test_nota_ponderada_vai_de_0_a_100() -> None:
    assert nota_ponderada(dict.fromkeys(CRITERIOS, 1), PERFIL.rubrica) == 0.0
    assert nota_ponderada(dict.fromkeys(CRITERIOS, 5), PERFIL.rubrica) == 100.0
    assert nota_ponderada(dict.fromkeys(CRITERIOS, 3), PERFIL.rubrica) == 50.0


def test_percentil() -> None:
    assert percentil([1, 2, 3, 4], 0.75) == 4


def test_abertura_energetica_olha_os_3_primeiros_segundos() -> None:
    energia = [0.1] * 10 + [0.9] * 6 + [0.1] * 10   # janelas de 0,5 s; pico entre 5 s e 8 s
    assert abertura_energetica(5.0, energia, limiar=0.5) is True
    assert abertura_energetica(0.0, energia, limiar=0.5) is False


def test_converter_aceita_ordena_e_aplica_bonus_penalidade() -> None:
    energia = [0.1] * 400   # constante: toda abertura atinge o limiar e ganha +3; a ordem não muda
    aceitos, descartes = converter(
        {"candidatos": [bruto(0, 2), bruto(3, 3, bonus=["humor"]), bruto(0, 0, pen=["palestra_ou_palco"])]},
        FRASES, PERFIL, energia)
    assert [c.frase_inicio for c in aceitos] == [3, 0]           # 75+5+3 antes de 75+3
    assert aceitos[0].nota_final == 83.0 and aceitos[0].inicio == 100 and aceitos[0].fim == 130
    assert descartes == [{"frase_inicio": 0, "frase_fim": 0, "motivo": "duração 10s fora de 20-90s"}]


def test_converter_descarta_com_motivo_visivel() -> None:
    aceitos, descartes = converter({"candidatos": [
        bruto(1, 2),                 # começa com "Mas"
        bruto(0, 2, dentro_do_tema=False),  # fora do tema
        bruto(2, 9),                 # índice inexistente
        bruto(2, 1),                 # fim antes do início
    ]}, FRASES, PERFIL, [0.1] * 400)
    assert aceitos == []
    assert [d["motivo"] for d in descartes] == [
        "começa no meio: 'Mas isso é outra conversa.'", "fora do tema",
        "índices inválidos 2-9", "índices inválidos 2-1"]
