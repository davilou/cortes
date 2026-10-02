from cortes.render.legenda import Grupo, grupos, legenda_html, palavras_do_corte
from cortes.tipos import Palavra


def P(texto: str, inicio: float) -> Palavra:
    return Palavra(texto, inicio, round(inicio + 0.3, 3))


def test_palavras_do_corte_ficam_relativas_ao_inicio() -> None:
    ws = [P("antes", 9.0), P("Eu", 10.0), P("ganhei.", 10.5), P("depois", 20.5)]
    assert palavras_do_corte(ws, 10.0, 20.0) == [Palavra("Eu", 0.0, 0.3), Palavra("ganhei.", 0.5, 0.8)]


def test_grupo_fecha_na_pontuacao_com_duas_palavras() -> None:
    gs = grupos([P("Eu", 0.0), P("perdi.", 0.6), P("Tudo", 1.2), P("mesmo", 1.8)], 3.0)
    assert gs == [Grupo(0.0, 1.2, ("Eu", "perdi.")), Grupo(1.2, 1.8, ("Tudo", "mesmo"))]


def test_grupo_fecha_em_cinco_palavras_e_dura_no_maximo_2_6s() -> None:
    gs = grupos([P(f"p{i}", i * 0.6) for i in range(7)], 10.0)
    assert [len(g.palavras) for g in gs] == [5, 2] and gs[0].dur == 2.6


def test_grupos_que_comecam_juntos_se_fundem() -> None:
    gs = grupos([P("Ah", 0.0), P("é.", 0.1), P("Foi", 0.3), P("assim.", 0.4), P("Depois", 2.0)], 3.0)
    assert [g.palavras for g in gs] == [("Ah", "é.", "Foi", "assim."), ("Depois",)]


def test_html_escapa_o_texto() -> None:
    html = legenda_html([Grupo(0.0, 1.0, ("<b>", "&"))])
    assert "&lt;b&gt; &amp;" in html and 'data-start="0.0" data-duration="1.0"' in html
