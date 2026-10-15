import json
import re
from pathlib import Path

import pytest

from cortes.producao.estado import ErroProducao
from cortes.render.conversa import trilha_conversa
from cortes.render.ilustracao import Deixa
from cortes.render.ilustracao_cache import Fonte, Ilustracao, Midia
from cortes.render.legenda import Grupo
from cortes.render.montagem import (
    F9_SAIU,
    FORMATOS,
    broll_html,
    caminho_template,
    montar_html,
    validar_formato,
    valores,
)
from cortes.render.motion_cache import Motion
from cortes.render.processo import ErroRender
from cortes.render.rosto import Amostra, Face, Rosto, trilha_fixa

REPO = Path(__file__).resolve().parents[1]
R = Rosto(1920, 1080, (Amostra(0.0, (Face(960, 540, 80, 0.9),)),), ())


def test_placeholder_sobrando_e_erro() -> None:
    with pytest.raises(ErroRender, match=r"\{\{QW\}\}"):
        montar_html("<p>{{DUR}} {{QW}}</p>", {"DUR": "3"})


def test_valor_com_placeholder_literal_nao_e_reprocessado() -> None:
    html = montar_html("<p>{{LEGENDAS}} {{CORTES}}</p>", {"LEGENDAS": "{{CORTES}}", "CORTES": "[1]"})
    assert html == "<p>{{CORTES}} [1]</p>"


def test_formato_sem_template_e_erro() -> None:
    with pytest.raises(ErroRender, match="formato 'f2'"):
        caminho_template(REPO, "f2")


def test_f9_virou_f4_com_erro_claro() -> None:
    with pytest.raises(ErroRender, match="o formato f9 virou o f4 B-roll; renderize de novo em f4"):
        caminho_template(REPO, "f9")
    assert "f9" in F9_SAIU and not (REPO / "render" / "formatos" / "ilustrado.tpl").exists()


@pytest.mark.parametrize("formato, erro", [("f9", F9_SAIU), ("f2", "formato 'f2' ainda não renderiza")])
def test_validar_formato_diz_que_o_f9_saiu(formato: str, erro: str) -> None:
    with pytest.raises(ErroProducao, match=re.escape(erro)):
        validar_formato(formato)
    validar_formato("f4")


G = [Grupo(0.0, 1.0, ("Oi",), (0.0,))]


def test_formatos_do_app() -> None:
    assert FORMATOS == ("f7", "f1", "f6", "f5", "f8", "f4", "f3")


@pytest.mark.parametrize("formato", FORMATOS)
def test_templates_reais_montam_sem_sobra(formato: str) -> None:
    tpl = caminho_template(REPO, formato).read_text(encoding="utf-8")
    motion = Motion([], "escuro") if formato == "f3" else None   # o f3 exige as cenas (test_render_motion_*)
    html = montar_html(tpl, valores(tpl, 12.5, R, G, {}, formato, "Título", motion=motion))
    assert 'data-duration="12.5"' in html and ">Oi<" in html
    cheio = formato in ("f7", "f1", "f6", "f4", "f3")
    assert ("3413px" in html) == cheio   # quadro cheio: fonte a 1920 de altura
    # corte seco, sem efeito nenhum: nem flash, nem zoom nas emendas ou nas frases (Davi, 2026-10-02)
    assert 'id="flash"' not in html and "scale: k % 2" not in html and "scale: n % 2" not in html
    assert 'id="zoom"' not in html and "? 1.08" not in html


def test_hormozi_acende_palavra_a_palavra() -> None:
    tpl = caminho_template(REPO, "f6").read_text(encoding="utf-8")
    html = montar_html(tpl, valores(tpl, 12.5, R, G, {}, "f6", "T"))
    assert '<span><i data-t="0.0">Oi</i></span>' in html and "3413px" in html


def test_gameplay_usa_o_quadro_da_metade() -> None:
    tpl = caminho_template(REPO, "f5").read_text(encoding="utf-8")
    html = montar_html(tpl, valores(tpl, 12.5, R, G, {}, "f5", "T"))
    assert "width: 1920px; height: 1080px" in html and "assets/gameplay.mp4" in html


def test_desfoque_escapa_o_titulo() -> None:
    tpl = caminho_template(REPO, "f8").read_text(encoding="utf-8")
    html = montar_html(tpl, valores(tpl, 12.5, R, G, {}, "f8", "Lucro <&> risco"))
    assert ">Lucro &lt;&amp;&gt; risco<" in html and "assets/fundo.mp4" in html


SEM_ROSTO = Rosto(1920, 1080, (Amostra(0.0, ()),), ())


def test_desfoque_nao_depende_de_rosto() -> None:
    """f8 não usa câmera nem metade (desfoque.tpl só tem DUR/TITULO/LEGENDAS): um `Rosto` sem
    nenhum rosto detectado não impede montar o HTML (revisão formatos novos, item 1)."""
    tpl = caminho_template(REPO, "f8").read_text(encoding="utf-8")
    html = montar_html(tpl, valores(tpl, 12.5, SEM_ROSTO, G, {}, "f8", "T"))
    assert 'data-duration="12.5"' in html


def test_falante_com_rosto_vazio_continua_com_erro_claro() -> None:
    """O mesmo `Rosto` sem detecção, mas num formato que usa câmera (f1), continua falhando —
    só f8 fica isento."""
    tpl = caminho_template(REPO, "f1").read_text(encoding="utf-8")
    with pytest.raises(ErroRender, match="nenhum plano de câmera tem rosto"):
        valores(tpl, 12.5, SEM_ROSTO, G, {}, "f1", "T")


def _ilus(k: int, coisa: str, midia: Midia | None = "video") -> Ilustracao:
    arq = Path(f"D{k}-v1.mp4" if midia == "video" else f"D{k}-c1-cheia.jpg") if midia else None
    deixa = Deixa(2.0 * k, 2.0 * k + 1.5, coisa, coisa, "literal")
    return Ilustracao(k, deixa, midia, arq, Fonte("http://x") if midia else None, "ok", (), False)


def test_broll_poe_um_clipe_em_tela_cheia_por_deixa_com_visual() -> None:
    tpl = caminho_template(REPO, "f4").read_text(encoding="utf-8")
    ilus = [_ilus(1, "tênis"), _ilus(2, 'bota "boa" <&>', "foto"), _ilus(3, "x", None)]
    html = montar_html(tpl, valores(tpl, 7.0, R, G, {}, "f4", "T", ilustracoes=ilus))
    assert ('<video class="clip broll" id="broll-1" data-start="2.0" data-duration="1.5" '
            'data-track-index="15" data-media-start="0" src="assets/broll-1.mp4" muted playsinline>'
            '</video>') in html
    assert ('<div class="clip broll" id="broll-2" data-start="4.0" data-duration="1.5" data-track-index="15">'
            '<img src="assets/broll-2.jpg" alt="bota &quot;boa&quot; &lt;&amp;&gt;"></div>') in html
    assert "broll-3" not in html   # deixa sem visual não vira clipe
    # aparece e some seco, por cima do rosto e por baixo da legenda (que vem depois no DOM)
    assert html.index('id="broll-2"') < html.index('id="leg-0"')


def test_broll_nao_tem_efeito_nenhum() -> None:
    """Sem Ken Burns, flash, zoom nem fade: o runtime liga e desliga o clipe na janela dele."""
    tpl = caminho_template(REPO, "f4").read_text(encoding="utf-8")
    script = tpl[tpl.index("<script>"):]
    assert ".broll" not in script and "scale: 1.08" not in script
    assert "{ opacity: 0 }, { opacity: 1, d" not in script
    assert "transition" not in tpl and "animation" not in tpl


def test_broll_vazio_fora_do_f4() -> None:
    tpl = caminho_template(REPO, "f7").read_text(encoding="utf-8")
    assert "BROLL" not in valores(tpl, 6.0, R, G, {}, "f7", "T", ilustracoes=[_ilus(1, "x")])


def test_clipe_que_passa_do_fim_do_short_e_cortado_e_o_que_sobra_pouco_sai() -> None:
    assert 'data-start="2.0" data-duration="1.0"' in broll_html([_ilus(1, "x")], 3.0)
    assert broll_html([_ilus(1, "x")], 2.2) == ""


def test_f7_alterna_entre_as_pessoas_e_os_outros_nao() -> None:
    """f7: TRILHA_CONVERSA corta seco para a parceira no plano aberto (render/conversa.py); o f1,
    com a mesma câmera, segue fixo na pessoa padrão."""
    dois = Rosto(1920, 1080, tuple(Amostra(i * 0.25, (Face(500, 540, 80, 0.9), Face(500, 540, 80, 0.9),
                                                     Face(1500, 540, 80, 0.9))) for i in range(120)), ())
    gs = [Grupo(float(i), 1.0, ("fala",), (float(i),)) for i in range(30)]
    tr = trilha_conversa(dois, {}, gs, 30.0)
    assert len(tr) == 3
    f7 = caminho_template(REPO, "f7").read_text(encoding="utf-8")
    assert f"const TR = {json.dumps(tr)};" in montar_html(f7, valores(f7, 30.0, dois, gs, {}, "f7", "T"))
    f1 = caminho_template(REPO, "f1").read_text(encoding="utf-8")
    assert json.dumps(trilha_fixa(dois, {})) in montar_html(f1, valores(f1, 30.0, dois, gs, {}, "f1", "T"))
