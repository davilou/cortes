from cortes.render.motion_cobertura import Vao, cobertura, feedback, mostravel, precisa_segunda, vaos
from cortes.render.motion_params import Chat, Contador
from cortes.render.motion_ritmo import Bruta, Descartada
from cortes.tipos import Palavra

FALA = ("Eu tive um apartamento que comprei por 400 mil reais e passou um tempo e aí eu vi que "
        "não tenho saco pra ficar indo em saco arema ver se funciona entendeu").split()
PALAVRAS = [Palavra(t, round(0.5 * i, 2), round(0.5 * i + 0.4, 2)) for i, t in enumerate(FALA)]
DUR = 0.5 * len(FALA)   # 16 s


def _b(ini: float, fim: float, comp: str = "chat") -> Bruta:
    return Bruta(comp, ini, fim, Chat("APP", "pergunta"), ())


def test_cobertura_e_a_fracao_do_short_com_painel() -> None:
    assert cobertura([_b(0.0, 2.2, "capa"), _b(4.0, 7.0)], 20.0) == 0.26
    assert cobertura([], 20.0) == 0.0


def test_vaos_sao_os_trechos_de_rosto_depois_do_gancho_com_o_texto() -> None:
    vs = vaos([_b(0.0, 2.2, "capa"), _b(4.0, 7.0)], PALAVRAS, DUR)
    assert [(v.inicio, v.fim, v.i, v.j) for v in vs] == [(7.0, 16.0, 14, 31)]
    assert vs[0].texto.startswith("e aí eu vi") and vs[0].texto.endswith("funciona entendeu")


def test_vao_curto_demais_para_uma_cena_nao_conta() -> None:
    # 2,2–4,0 s (1,8 s) e 7,0–9,5 s (2,5 s) não cabem uma cena com rosto dos dois lados
    vs = vaos([_b(0.0, 2.2, "capa"), _b(4.0, 7.0), _b(9.5, 16.0)], PALAVRAS, DUR)
    assert vs == []


def test_sem_cena_o_vao_e_do_fim_do_gancho_ao_fim() -> None:
    (v,) = vaos([], PALAVRAS, DUR)
    assert (v.inicio, v.fim, v.i, v.j) == (1.0, 16.0, 2, 31)


def test_mostravel_numero_comparacao_lista_ou_lugar() -> None:
    assert mostravel("comprei por 400 mil reais")
    assert mostravel("aí você fala, perdi um dinheiro")
    assert mostravel("rendeu mais do que o imóvel")
    assert mostravel("primeiro a oportunidade, segundo a localização")
    assert mostravel("fui pra Saquarema ver")
    assert mostravel("ficar indo em saco arema ver se funciona")
    assert not mostravel("é eu não saber fazer isso, entendeu?")


def test_segunda_chamada_com_cobertura_baixa_ou_vao_longo_mostravel() -> None:
    longo = Vao(5.0, 12.0, 0, 3, "aí eu perdi dinheiro")
    curto = Vao(5.0, 9.0, 0, 3, "aí eu perdi dinheiro")
    sem_nada = Vao(5.0, 12.0, 0, 3, "é eu não saber fazer isso")
    cheia = [_b(0.0, 2.2, "capa"), _b(2.5, 6.5), _b(12.0, 16.0)]   # 10,2 s de 20 s = 51%
    assert precisa_segunda([_b(3.0, 6.0)], [], 20.0)                 # 15%
    assert precisa_segunda(cheia, [longo], 20.0)
    assert not precisa_segunda(cheia, [curto, sem_nada], 20.0)


def test_feedback_lista_aceitas_recusadas_e_vaos_com_as_palavras() -> None:
    aceitas = [Bruta("contador", 3.0, 6.0, Contador("PAGOU", 400, "R$", "mil"), (4.0,))]
    recusadas = [Descartada("valor_cheio", 6.5, 9.0, {"valor": 550}, "número que a fala não disse: 37,5%")]
    vs = [Vao(7.0, 15.0, 14, 29, "e aí eu vi")]
    f = feedback(aceitas, recusadas, vs, 20.0)
    assert "A cobertura ficou em 15%" in f and "de 50% a 70%" in f
    assert '- [3.00–6.00 s] contador: {"rotulo": "PAGOU", "valor": 400' in f
    assert "- [6.50–9.00 s] valor_cheio: número que a fala não disse: 37,5%" in f
    assert '- [7.00–15.00 s] palavras [14] a [29]: "e aí eu vi"' in f
    assert "Devolva SÓ as cenas novas" in f


def test_feedback_insiste_nos_vaos_e_lembra_da_capa_que_falta() -> None:
    vs = [Vao(7.0, 15.0, 14, 29, "indo em saco arema")]
    f = feedback([_b(3.0, 6.0)], [], vs, 20.0)
    assert "ponha uma cena em cada trecho" in f and "nome deformado pela transcrição também é lugar" in f
    assert "Sem capa: se o começo da fala promete algo" in f
    assert "Sem capa" not in feedback([_b(0.0, 2.2, "capa")], [], vs, 20.0)
