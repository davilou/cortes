from cortes.render.motion_cobertura import cobertura, feedback, precisa_segunda, vaos
from cortes.render.motion_params import Chat, Respiro
from cortes.render.motion_ritmo import Bruta, Descartada
from cortes.tipos import Palavra

P = Chat("APP", "pergunta")
PALAVRAS = [Palavra(f"p{i}", i * 0.5, i * 0.5 + 0.4) for i in range(40)]   # 20 s


def _b(ini: float, fim: float, comp: str = "chat") -> Bruta:
    return Bruta(comp, ini, fim, Respiro() if comp == "respiro" else P, ())


def test_cobertura_conta_so_paineis_fora_do_gancho_e_dos_respiros() -> None:
    cenas = [_b(0.0, 2.0, "capa"), _b(2.0, 10.0), _b(10.0, 12.0, "respiro"), _b(12.0, 15.0)]
    assert cobertura(cenas, 20.0) == round(11 / 16, 3)


def test_vaos_sao_os_trechos_sem_nada_depois_do_gancho() -> None:
    vs = vaos([_b(2.0, 6.0), _b(9.0, 12.0, "respiro")], PALAVRAS, 20.0)
    assert [(v.inicio, v.fim, v.i, v.j) for v in vs] == [(6.0, 9.0, 12, 17), (12.0, 20.0, 24, 39)]


def test_vao_menor_que_uma_cena_nao_conta() -> None:
    assert vaos([_b(2.0, 6.0), _b(7.5, 20.0)], PALAVRAS, 20.0) == []


def test_segunda_chamada_com_cobertura_baixa_ou_vao_de_mais_de_3_s() -> None:
    cheia = [_b(2.0, 6.0), _b(6.0, 10.0), _b(10.0, 14.0), _b(14.0, 17.5)]
    assert not precisa_segunda(cheia, vaos(cheia, PALAVRAS, 20.0), 20.0)
    furada = [_b(2.0, 6.0), _b(9.5, 13.5), _b(13.5, 17.5), _b(17.5, 20.0)]
    assert precisa_segunda(furada, vaos(furada, PALAVRAS, 20.0), 20.0)


def test_feedback_lista_aceitas_recusadas_vaos_e_pede_destaque_em_opiniao() -> None:
    f = feedback([_b(2.0, 6.0)], [Descartada("valor", 7.0, 9.0, {}, "número que a fala não disse: 9")],
                 vaos([_b(2.0, 6.0)], PALAVRAS, 20.0), 20.0)
    assert "[2.00–6.00 s] chat" in f and "número que a fala não disse: 9" in f
    assert "palavras [12] a [39]" in f and '"destaque"' in f and "85%" in f
    assert "Sem capa" in f
