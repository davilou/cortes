import pytest

from cortes.render.conversa import (
    Alternancia,
    alternancias,
    alvo_trocas,
    parceira,
    ritmo,
    trilha_conversa,
    trocas_por_10s,
)
from cortes.render.legenda import Grupo
from cortes.render.rosto import Amostra, Face, Pessoa, Plano, Rosto, posicao, trilha_fixa

LARG = 1920


def P(x: float, n: int = 20) -> Pessoa:
    return Pessoa(x, 540.0, 80.0, n, 0.9)


def G(ini: float, *palavras: str) -> Grupo:
    return Grupo(ini, 1.0, palavras, tuple(ini for _ in palavras))


def grupos_a_cada(passo: float, dur: float, ultima: str = "e") -> list[Grupo]:
    n = int(dur / passo)
    return [G(round(i * passo, 2), "fala", ultima) for i in range(n)]


DOIS = Plano(0, 0.0, 30.0, (P(500, 40), P(1500, 30)), 0)


def test_trocas_por_10s_conta_so_dentro_do_short() -> None:
    assert trocas_por_10s([0.0, 5.0, 12.0, 30.0], 30.0) == 0.67
    assert trocas_por_10s([], 20.0) == 0.0
    with pytest.raises(ValueError, match="duração"):
        trocas_por_10s([1.0], 0.0)


@pytest.mark.parametrize("dur, alvo", [(10.0, 0), (20.0, 1), (25.0, 2), (30.0, 2), (40.0, 3),
                                       (50.0, 4), (60.0, 4)])
def test_alvo_mira_0_7_dentro_de_0_6_a_0_8(dur: float, alvo: int) -> None:
    """20 s: a faixa não cabe (2 trocas = 1,0) — fica no maior total ≤ 0,8."""
    assert alvo_trocas(dur) == alvo
    assert trocas_por_10s([float(i + 1) for i in range(alvo)], dur) <= 0.8


def test_parceira_e_a_mais_detectada_longe_da_padrao() -> None:
    p = Plano(0, 0.0, 30.0, (P(754, 200), P(823, 90), P(1851, 60)), 0)
    assert parceira(p, LARG) == 2      # 823 é a mesma pessoa partida em dois grupos
    so_perto = Plano(0, 0.0, 30.0, (P(754, 200), P(823, 90)), 0)
    assert parceira(so_perto, LARG) is None
    assert parceira(Plano(0, 0.0, 30.0, (P(754),), 0), LARG) is None


def test_parceira_nao_e_falso_positivo_do_detector() -> None:
    """Render real (wxCto9WSZcI, plano solo do Henrique): um boneco na estante em x 1851 virou
    "pessoa" com 49 detecções — rosto pequeno (r 55 × 223) e confiança baixa (0,69 × 0,90). Um
    rosto meio cortado na borda (r 73 × 140) também não é a outra pessoa da conversa."""
    boneco = Plano(0, 0.0, 38.0, (Pessoa(720, 251, 223, 130, 0.904), Pessoa(1851, 791, 55, 49, 0.686)), 0)
    assert parceira(boneco, LARG) is None
    pequeno = Plano(0, 0.0, 30.0, (Pessoa(500, 300, 200, 90, 0.9), Pessoa(1500, 300, 110, 80, 0.9)), 0)
    assert parceira(pequeno, LARG) is None
    duvida = Plano(0, 0.0, 30.0, (Pessoa(500, 300, 200, 90, 0.9), Pessoa(1500, 300, 190, 80, 0.74)), 0)
    assert parceira(duvida, LARG) is None
    certa = Plano(0, 0.0, 30.0, (Pessoa(500, 300, 200, 90, 0.9), Pessoa(1500, 300, 130, 80, 0.75)), 0)
    assert parceira(certa, LARG) == 1


def test_alterna_em_inicio_de_grupo_ate_o_alvo() -> None:
    gs = grupos_a_cada(1.0, 30.0)
    alts = alternancias([DOIS], {}, gs, 30.0, LARG)
    assert len(alts) == alvo_trocas(30.0) == 2
    inicios = {g.ini for g in gs}
    assert all(a.t in inicios for a in alts)
    assert [a.j for a in alts] == [1, 0]           # começa na padrão (0): vai para a 1 e volta
    assert alts == [Alternancia(10.0, 0, 1), Alternancia(20.0, 0, 0)]   # igualmente espaçadas


def test_trecho_minimo_de_1_8_s_na_mesma_pessoa() -> None:
    curto = Plano(0, 0.0, 4.0, DOIS.pessoas, 0)
    gs = [G(0.0, "a"), G(1.0, "b"), G(1.7, "c"), G(2.0, "d"), G(2.3, "e")]
    alts = alternancias([curto], {}, gs, 40.0, LARG)
    assert [a.t for a in alts] == [2.0]            # 1,0/1,7 deixam < 1,8 antes; 2,3 deixa < 1,8 depois


def test_plano_curto_nao_alterna() -> None:
    curto = Plano(0, 0.0, 3.4, DOIS.pessoas, 0)
    assert alternancias([curto], {}, [G(1.8, "a")], 40.0, LARG) == []


def test_escolha_manual_desliga_a_alternancia_do_plano() -> None:
    gs = grupos_a_cada(1.0, 30.0)
    assert alternancias([DOIS], {0: 1}, gs, 30.0, LARG) == []
    assert alternancias([DOIS], {0: 0}, gs, 30.0, LARG) == []


def test_trocas_reais_contam_no_alvo() -> None:
    pls = [Plano(0, 0.0, 10.0, DOIS.pessoas, 0), Plano(1, 10.0, 20.0, (P(900),), 0),
           Plano(2, 20.0, 30.0, DOIS.pessoas, 0)]
    gs = grupos_a_cada(1.0, 30.0)
    assert alternancias(pls, {}, gs, 30.0, LARG) == []   # 2 trocas reais já são o alvo de 30 s
    pls40 = [*pls[:2], Plano(2, 20.0, 40.0, DOIS.pessoas, 0)]
    alts = alternancias(pls40, {}, grupos_a_cada(1.0, 40.0), 40.0, LARG)
    assert [(a.t, a.k) for a in alts] == [(30.0, 2)]   # o meio do maior vão


def test_prefere_fim_de_frase() -> None:
    gs = [G(float(i), "fala", "e") for i in range(30)]
    gs[8] = G(8.0, "fala", "fim.")                  # a frase fecha antes do grupo das 9,0 s
    gs[25] = G(25.0, "fala", "fim?")                # longe demais do ideal (20,0): não conta
    alts = alternancias([DOIS], {}, gs, 30.0, LARG)
    assert [a.t for a in alts] == [9.0, 20.0]       # 9,0 (frase) ganha de 10,0 (o ideal exato)


def test_virgula_ganha_de_grupo_fechado_por_tamanho() -> None:
    """Render real (wxCto9WSZcI, "Banco mente…"): sem fim de frase perto do ideal, o corte caiu em
    "com o score lá em | cima" — grupo fechado por ter 5 palavras. Vírgula perto do ideal ganha."""
    gs = [G(float(i), "fala", "e") for i in range(30)]
    gs[10] = G(10.0, "fala", "cima,")               # o grupo das 11,0 s começa depois de vírgula
    gs[8] = G(8.0, "fala", "fim.")                  # fim de frase ainda ganha da vírgula
    assert [a.t for a in alternancias([DOIS], {}, gs, 30.0, LARG)] == [9.0, 20.0]
    gs[8] = G(8.0, "fala", "e")
    assert [a.t for a in alternancias([DOIS], {}, gs, 30.0, LARG)] == [11.0, 20.0]


def test_sem_parceira_nao_alterna() -> None:
    perto = Plano(0, 0.0, 30.0, (P(754, 200), P(823, 90)), 0)
    assert alternancias([perto], {}, grupos_a_cada(1.0, 30.0), 30.0, LARG) == []


def F(x: float) -> Face:
    return Face(x, 540.0, 80.0, 0.9)


R = Rosto(LARG, 1080, tuple(Amostra(i * 0.25, (F(500), F(500), F(1500))) for i in range(120)), ())


def test_trilha_conversa_corta_seco_na_parceira_e_volta() -> None:
    gs = grupos_a_cada(1.0, 30.0)
    tr = trilha_conversa(R, {}, gs, 30.0)
    p0, p1 = posicao(R, P(500)), posicao(R, P(1500))
    assert tr == [[0.0, *p0, 1], [10.0, *p1, 1], [20.0, *p0, 1]]
    assert trilha_conversa(R, {0: 1}, gs, 30.0) == trilha_fixa(R, {0: 1})


def test_ritmo_soma_reais_e_alternancias() -> None:
    rt = ritmo(R, {}, grupos_a_cada(1.0, 30.0), 30.0)
    assert (rt.reais, rt.alternancias, rt.trocas_10s) == (0, 2, 0.67)
    assert ritmo(R, {0: 0}, grupos_a_cada(1.0, 30.0), 30.0).trocas_10s == 0.0
