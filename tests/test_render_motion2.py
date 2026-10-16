from cortes.render.motion import Cena
from cortes.render.motion2 import SFX, Plano, estados_json, plano, sfx, sfx_html
from cortes.render.motion_params import Capa, Contador, Destaque, Respiro

CAPA = Cena(1, "capa", 0.0, 2.0, Capa("MERCADO", "Sobe no boato", "boato"), ())


def _painel(k: int, ini: float, fim: float, batidas: tuple[float, ...] = ()) -> Cena:
    return Cena(k, "destaque", ini, fim, Destaque("sobe no boato", "boato"), batidas)


def test_paineis_revezam_comecando_pelo_escuro() -> None:
    cenas = [CAPA, _painel(2, 2.0, 5.0), _painel(3, 5.0, 8.0), _painel(4, 8.0, 11.0)]
    p = plano(cenas, 11.0)
    assert p.estados == [(0.0, "gancho"), (2.0, "escuro"), (5.0, "claro"), (8.0, "escuro")]
    assert p.solo == frozenset({2, 4})


def test_vao_entre_cenas_e_o_fim_ficam_claros() -> None:
    p = plano([CAPA, _painel(2, 3.0, 5.0), _painel(3, 9.0, 11.0)], 14.0)
    assert p.estados == [(0.0, "gancho"), (2.0, "claro"), (3.0, "escuro"), (5.0, "claro")]
    assert p.solo == frozenset({2})


def test_respiro_nao_conta_no_revezamento() -> None:
    cenas = [CAPA, _painel(2, 2.0, 4.0), Cena(3, "respiro", 4.0, 6.0, Respiro(), ()), _painel(4, 6.0, 9.0)]
    p = plano(cenas, 9.0)
    assert p.estados == [(0.0, "gancho"), (2.0, "escuro"), (4.0, "respiro"), (6.0, "claro")]


def test_sem_capa_o_gancho_dura_o_padrao_e_fresta_minima_nao_pisca() -> None:
    p = plano([_painel(2, 2.03, 4.0), _painel(3, 4.02, 6.0)], 6.0)
    assert p.estados == [(0.0, "gancho"), (2.03, "escuro"), (4.02, "claro")]


def test_cena_que_invade_a_anterior_comeca_no_fim_dela() -> None:
    p = plano([CAPA, _painel(2, 1.5, 4.0)], 4.0)
    assert p.estados == [(0.0, "gancho"), (2.0, "escuro")]


def test_estados_viram_json_para_o_template() -> None:
    assert estados_json(Plano([(0.0, "gancho"), (2.0, "escuro")], frozenset())) == \
        '[[0.0, "gancho"], [2.0, "escuro"]]'


def test_whoosh_nas_trocas_e_pop_nas_entradas_e_batidas() -> None:
    cenas = [CAPA, _painel(2, 2.0, 5.0, (3.1, 4.0)), _painel(3, 5.0, 8.0)]
    p = plano(cenas, 8.0)
    assert sfx(cenas, p, 8.0) == [(1.88, "whoosh"), (2.05, "pop"), (3.1, "pop"), (4.0, "pop"),
                                  (4.88, "whoosh"), (5.05, "pop")]


def test_efeitos_colados_viram_um_e_nada_passa_do_fim() -> None:
    cenas = [CAPA, Cena(2, "contador", 2.0, 4.0, Contador("X", 10, "", "", ()), (2.1, 2.4, 3.95))]
    p = plano(cenas, 4.0)
    sons = sfx(cenas, p, 4.0)
    # 2,1 cola no 2,05; 3,95 + 0,11 passa de 4
    assert sons == [(1.88, "whoosh"), (2.05, "pop"), (2.4, "pop")]
    assert all(t + SFX[n] <= 4.0 for t, n in sons)


def test_sfx_html_tem_id_duracao_do_arquivo_e_trilhas_alternadas() -> None:
    html = sfx_html([(1.88, "whoosh"), (2.1, "pop")])
    assert 'id="sfx-0" src="assets/sfx-whoosh.wav" data-start="1.88" data-duration="0.55"' in html
    assert 'id="sfx-1" src="assets/sfx-pop.wav" data-start="2.1" data-duration="0.11"' in html
    assert 'data-track-index="11"' in html and 'data-track-index="12"' in html
    assert sfx_html([]) == ""
