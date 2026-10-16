import json
import re
from pathlib import Path

import pytest

from cortes.render.legenda import Grupo
from cortes.render.montagem import caminho_template, montar_html, valores
from cortes.render.motion import Cena
from cortes.render.motion_animacao import animacoes
from cortes.render.motion_cache import Motion
from cortes.render.motion_componentes import cena_html, cenas_html, estados
from cortes.render.motion_params import (
    Capa,
    Chat,
    Check,
    Coluna,
    Comodo,
    Comparacao,
    Contador,
    Destaque,
    Fluxo,
    Grade,
    Grafico,
    Ilustracao,
    Lista,
    Passo,
    Planta,
    Ponto,
    Respiro,
    Rota,
    Timer,
    Valor,
)
from cortes.render.rosto import Amostra, Face, Rosto

REPO = Path(__file__).resolve().parents[1]
R = Rosto(1920, 1080, (Amostra(0.0, (Face(960, 540, 80, 0.9),)),), ())
G = [Grupo(0.0, 1.0, ("Oi",), (0.0,))]
MAL = '<script>alert("x")</script> & "aspas"'

CENAS = [
    Cena(1, "capa", 0.0, 2.0, Capa("MAURÍCIO", "Ele perdeu dinheiro com um apê", "dinheiro"), ()),
    Cena(2, "contador", 2.0, 5.0, Contador("PAGOU", 400, "R$", "mil", ("ANO 0", "ANO 10")), (4.45,)),
    Cena(3, "valor", 5.0, 8.0, Valor("VALIA", 550, 400, "R$", "mil", "550"), (6.4,)),
    Cena(4, "chat", 8.0, 10.5, Chat("CHATGPT", MAL), ()),
    Cena(
        5,
        "comparacao",
        10.5,
        13.0,
        Comparacao(
            (Coluna("IMÓVEL", "R$ 550 mil", 0.6), Coluna("RENDA FIXA", "mais", 1.0)), "PERDI DINHEIRO"
        ),
        (10.7,),
    ),
    Cena(6, "respiro", 13.0, 15.0, Respiro(), ()),
    Cena(7, "lista", 15.0, 18.0, Lista("Pra comprar:", ("Oportunidade", "Localização")), (15.2, 17.0)),
    Cena(8, "rota", 18.0, 21.0, Rota("Rio", "Saquarema", "sem saco"), (18.5, 19.5)),
    Cena(9, "grafico", 21.0, 24.0, Grafico("EFEITO", (Ponto("dia 1", 0), Ponto("dia 3", 80)), 1), (22.5,)),
    Cena(
        10,
        "fluxo",
        24.0,
        27.0,
        Fluxo((Passo("microfone", "você fala"), Passo("lampada", MAL)), 1),
        (24.2, 25.5),
    ),
    Cena(11, "timer", 27.0, 30.0, Timer("LUZ", 8, "min"), ()),
    Cena(12, "check", 30.0, 32.0, Check("A IA faz", "sim"), (30.6,)),
    Cena(
        13, "grade", 32.0, 35.0, Grade((Passo("pessoa", "Corretora"), Passo("saude", "Médica"))), (32.2, 33.0)
    ),
    Cena(14, "destaque", 35.0, 38.0, Destaque("Isso é conteúdo 2.0", "conteúdo"), (36.0,)),
    Cena(15, "planta", 38.0, 41.0, Planta((Comodo("Sala", 30), Comodo("Quarto", None)), 72), (38.3, 39.5)),
    Cena(16, "ilustracao", 41.0, 44.0, Ilustracao("rosto", "TESTA", "pessoa"), (42.0,)),
]
SVG = '<svg viewBox="0 0 1000 700" xmlns="http://www.w3.org/2000/svg"><circle cx="1" cy="1" r="1"/></svg>'


def test_estados_cheio_no_gancho_e_nos_respiros_div_no_resto() -> None:
    assert json.loads(estados(CENAS)) == [[0, "cheio"], [2.0, "div"], [13.0, "cheio"], [15.0, "div"]]
    assert json.loads(estados(CENAS[1:5])) == [[0, "cheio"], [2.0, "div"]]  # sem capa: o gancho é de 2 s


def test_cada_cena_vira_um_clipe_e_o_respiro_nao() -> None:
    assert cena_html(CENAS[1], {}).startswith(
        '      <div id="m2" data-start="2.0" data-duration="3.0" class="clip faixa" data-track-index="2">'
        '<div class="painel contador-p">'
    )
    assert 'class="clip capa" data-track-index="4"' in cena_html(CENAS[0], {})
    assert "<b>dinheiro</b>" in cena_html(CENAS[0], {})
    assert cena_html(CENAS[5], {}) == "" and 'id="m6"' not in cenas_html(CENAS, {})


@pytest.mark.parametrize("cena", CENAS, ids=lambda c: c.componente)
def test_todo_componente_monta_e_escapa_o_texto(cena: Cena) -> None:
    h = cena_html(cena, {})
    assert "<script>" not in h and ("alert" not in h or "&lt;script&gt;alert(&quot;x&quot;)" in h)


def test_texto_do_llm_nunca_vai_para_o_javascript() -> None:
    js = animacoes(CENAS)
    for texto in ("alert", "CHATGPT", "Saquarema", "você fala", "Corretora", "conteúdo", "Sala", "TESTA"):
        assert texto not in js


def test_ilustracao_com_svg_ou_com_o_icone() -> None:
    assert SVG in cena_html(CENAS[15], {16: SVG})
    sem = cena_html(CENAS[15], {})
    assert 'class="ilus-icone"' in sem and ">TESTA<" in sem


def test_componentes_novos_tem_o_que_a_tela_mostra() -> None:
    h = cenas_html(CENAS, {})
    assert 'class="passo ativo" id="m10-p1"' in h and 'class="w on" id="m14-w2">conteúdo<' in h
    assert "8 minutos" in h and 'class="check sim"' in h and "72 m²" in h and 'id="m15-c0"' in h
    assert 'class="gvalor" id="m9-valor"' in h and ">80<" in h


def test_animacoes_nos_tempos_das_cenas_e_das_batidas() -> None:
    js = animacoes(CENAS)
    assert 'contar("#m2-n", 0.0, 400, 0, 2.05, 1.7);' in js
    assert 'contar("#m3-n", 400, 550, 0, 5.1, 1.7);' in js
    assert re.search(r'tl.fromTo\("#m2-prog", .*?, 4.45\);', js)
    assert re.search(r'tl.fromTo\("#m7-i1", .*?, 17.0\);', js)
    assert re.search(r'tl.fromTo\("#m9-dest", .*?, 22.5\);', js)
    assert 'relogio("#m11-rel", 8, 1, 27.1, 1.8);' in js
    assert re.search(r'tl.fromTo\("#m13-b1", .*?, 33.0\);', js)
    assert re.search(r'tl.fromTo\("#m15-c1", .*?, 39.5\);', js)
    assert "#m6" not in js and "scale: 1.04" not in js and "flash" not in js


def test_template_f3_monta_sem_sobra_com_tema_card_e_faixa_base() -> None:
    tpl = caminho_template(REPO, "f3").read_text(encoding="utf-8")
    html = montar_html(tpl, valores(tpl, 45.0, R, G, {}, "f3", "T", motion=Motion(CENAS, "noite", {16: SVG})))
    assert "{{" not in html and "--brand: #d9b46a" in html and 'id="m16"' in html and SVG in html
    assert 'posicionar("#q-div", [[0.0, ' in html and ">Oi<" in html
    assert '<div id="faixa-base"' in html and "MAURÍCIO" in html


def test_faixa_base_escapa_o_rotulo() -> None:
    tpl = caminho_template(REPO, "f3").read_text(encoding="utf-8")
    capa = Cena(1, "capa", 0.0, 2.0, Capa(MAL, "Título", "Título"), ())
    html = montar_html(
        tpl, valores(tpl, 10.0, R, G, {}, "f3", "T", motion=Motion([capa, CENAS[1]], "escuro"))
    )
    assert "<script>alert" not in html


def test_contagem_nao_deixa_o_gsap_ler_o_texto_como_numero() -> None:
    """Sem o espaço de largura zero, o GSAP escrevia "1.500" como "1.5" (teste cego, plano E)."""
    tpl = caminho_template(REPO, "f3").read_text(encoding="utf-8")
    assert 'const SEM_NUMERO = "​";' in tpl and "textContent: SEM_NUMERO + fmt(" in tpl


def test_palavra_destacada_e_a_palavra_inteira() -> None:
    h = cena_html(Cena(1, "destaque", 2.0, 4.0, Destaque("A taxação mata a taxa", "taxa"), (2.5,)), {})
    assert 'class="w" id="m1-w1">taxação<' in h and 'class="w on" id="m1-w4">taxa<' in h
    capa = cena_html(Cena(1, "capa", 0.0, 2.0, Capa("R", "A taxação e a taxa", "taxa"), ()), {})
    assert "taxação" in capa and "<b>taxa</b>" in capa and "<b>taxação</b>" not in capa


def test_faixa_base_sem_capa_usa_o_titulo_do_corte() -> None:
    tpl = caminho_template(REPO, "f3").read_text(encoding="utf-8")
    html = montar_html(
        tpl, valores(tpl, 10.0, R, G, {}, "f3", "430 mil normas", motion=Motion(CENAS[1:3], "dados"))
    )
    assert '<div id="faixa-base"><span>430 mil normas</span>' in html


def test_painel_entra_sem_esmaecer_por_cima_da_faixa_base() -> None:
    js = animacoes(CENAS[1:2])
    assert (
        'tl.fromTo("#m2 .painel", { y: -24 }' in js
        and "opacity: 0 }, { y: 0, opacity: 1" not in js.split("\n")[0]
    )
