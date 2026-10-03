import json
import re
from pathlib import Path

from cortes.render.legenda import Grupo
from cortes.render.montagem import caminho_template, montar_html, valores
from cortes.render.motion import Cena
from cortes.render.motion_animacao import animacoes
from cortes.render.motion_componentes import cena_html, estados
from cortes.render.motion_params import Capa, Chat, Coluna, Comparacao, Contador, Lista, Rota, ValorCheio
from cortes.render.rosto import Amostra, Face, Rosto

REPO = Path(__file__).resolve().parents[1]
R = Rosto(1920, 1080, (Amostra(0.0, (Face(960, 540, 80, 0.9),)),), ())
G = [Grupo(0.0, 1.0, ("Oi",), (0.0,))]
MAL = '<script>alert("x")</script> & "aspas"'

CENAS = [
    Cena(1, "capa", 0.0, 2.2, Capa("MAURÍCIO", "Ele perdeu dinheiro com um apê", "dinheiro"), ()),
    Cena(2, "contador", 3.6, 6.25, Contador("PAGOU", 400, "R$", "mil", ("ANO 0", "ANO 10")), (5.45,)),
    Cena(3, "valor_cheio", 7.5, 10.0, ValorCheio("VALIA", 550, 400, "R$", "mil", "550"), (8.4,)),
    Cena(4, "chat", 11.0, 13.6, Chat("CHATGPT", MAL), ()),
    Cena(5, "comparacao", 14.6, 16.2,
         Comparacao((Coluna("IMÓVEL", "R$ 550 mil", 0.6), Coluna("RENDA FIXA", "mais", 1.0)),
                    "PERDI DINHEIRO"),
         (14.7,)),
    Cena(6, "lista", 17.4, 20.4, Lista("Pra comprar:", ("Oportunidade", "Localização")), (17.6, 19.4)),
    Cena(7, "rota", 21.5, 24.0, Rota("Rio", "Saquarema", "sem saco"), (22.0, 23.0)),
]


def test_estados_trocam_em_corte_seco_so_nas_cenas_div() -> None:
    assert json.loads(estados(CENAS)) == [[0, "cheio"], [3.6, "div"], [6.25, "cheio"], [11.0, "div"],
                                          [13.6, "cheio"], [17.4, "div"], [20.4, "cheio"], [21.5, "div"],
                                          [24.0, "cheio"]]


def test_cada_cena_vira_um_clipe_no_tempo_dela() -> None:
    assert cena_html(CENAS[1]).startswith('      <div id="m2" data-start="3.6" data-duration="2.65" '
                                          'class="clip faixa" data-track-index="2">')
    assert 'class="clip cartao" data-track-index="5"' in cena_html(CENAS[2])
    assert 'class="clip capa" data-track-index="4"' in cena_html(CENAS[0])
    assert "<b>dinheiro</b>" in cena_html(CENAS[0])


def test_texto_do_llm_e_escapado_e_nunca_vai_para_o_javascript() -> None:
    h = cena_html(CENAS[3])
    assert "<script>" not in h and "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp;" in h
    js = animacoes(CENAS)
    assert "alert" not in js and "CHATGPT" not in js and "Saquarema" not in js


def test_animacoes_nos_tempos_das_cenas_e_das_batidas() -> None:
    js = animacoes(CENAS)
    assert 'contar("#m2-n", 0.0, 400, 0, 3.65, 1.7);' in js
    assert 'contar("#m3-n", 400, 550, 0, 7.6, 1.7);' in js
    assert re.search(r'tl.fromTo\("#m2-prog", .*?, 5.45\);', js)
    assert re.search(r'tl.fromTo\("#m6-i1", .*?, 19.4\);', js)
    assert re.search(r'tl.fromTo\("#m7-p2", .*?, 22.0\);', js)
    # sem zoom lento nem flash (Davi, 2026-10-02)
    assert "scale: 1.04" not in js and "flash" not in js


def test_template_f3_monta_sem_sobra_com_as_duas_janelas() -> None:
    tpl = caminho_template(REPO, "f3").read_text(encoding="utf-8")
    html = montar_html(tpl, valores(tpl, 25.0, R, G, {}, "f3", "T", cenas=CENAS))
    assert "width: 3413px" in html and "width: 2304px; height: 1296px" in html
    assert 'id="m7"' in html and 'contar("#m2-n"' in html and ">Oi<" in html
    assert "const TRILHA" not in html and 'posicionar("#q-div", [[0.0, ' in html
