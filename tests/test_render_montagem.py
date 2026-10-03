from pathlib import Path

import pytest

from cortes.render.ilustracao import Deixa
from cortes.render.ilustracao_cache import Ilustracao
from cortes.render.legenda import Grupo
from cortes.render.montagem import FORMATOS, caminho_template, imagens_html, montar_html, valores
from cortes.render.processo import ErroRender
from cortes.render.rosto import Amostra, Face, Rosto

REPO = Path(__file__).resolve().parents[1]
R = Rosto(1920, 1080, (Amostra(0.0, (Face(960, 540, 80, 0.9),)),), ())


def test_placeholder_sobrando_e_erro() -> None:
    with pytest.raises(ErroRender, match=r"\{\{QW\}\}"):
        montar_html("<p>{{DUR}} {{QW}}</p>", {"DUR": "3"})


def test_valor_com_placeholder_literal_nao_e_reprocessado() -> None:
    html = montar_html("<p>{{LEGENDAS}} {{CORTES}}</p>", {"LEGENDAS": "{{CORTES}}", "CORTES": "[1]"})
    assert html == "<p>{{CORTES}} [1]</p>"


def test_formato_sem_template_e_erro() -> None:
    with pytest.raises(ErroRender, match="formato 'f4'"):
        caminho_template(REPO, "f4")


G = [Grupo(0.0, 1.0, ("Oi",), (0.0,))]


def test_formatos_do_app() -> None:
    assert FORMATOS == ("f7", "f1", "f6", "f5", "f8", "f9")


@pytest.mark.parametrize("formato", FORMATOS)
def test_templates_reais_montam_sem_sobra(formato: str) -> None:
    tpl = caminho_template(REPO, formato).read_text(encoding="utf-8")
    html = montar_html(tpl, valores(tpl, 12.5, R, G, {}, formato, "Título"))
    assert 'data-duration="12.5"' in html and ">Oi<" in html
    cheio = formato in ("f7", "f1", "f6", "f9")
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


def _ilus(k: int, coisa: str, imagem: bool = True) -> Ilustracao:
    img = Path(f"D{k}-c1.jpg") if imagem else None
    return Ilustracao(k, Deixa(2.0 * k, 2.0 * k + 1.5, coisa, coisa), img, "http://loja", "ok", (), False)


def test_ilustrado_poe_um_cartao_por_imagem_escapado() -> None:
    tpl = caminho_template(REPO, "f9").read_text(encoding="utf-8")
    ilus = [_ilus(1, 'tênis "Vans" <&>'), _ilus(2, "bota", imagem=False), _ilus(3, "camisa")]
    html = montar_html(tpl, valores(tpl, 6.0, R, G, {}, "f9", "T", ilustracoes=ilus))
    assert ('<div class="clip ilus" id="ilus-1" data-start="2.0" data-duration="1.5" data-track-index="15">'
            '<img src="assets/ilus-1.jpg" alt="tênis &quot;Vans&quot; &lt;&amp;&gt;"></div>') in html
    assert "ilus-2.jpg" not in html   # deixa sem imagem não vira cartão
    assert "ilus-3" not in html   # começa no fim do Short: não cabe
    # entrada e saída só por opacidade, sem scale nem flash
    assert "{ opacity: 0 }, { opacity: 1, duration: 0.15" in html and 'id="flash"' not in html


def test_imagens_vazio_fora_do_f9() -> None:
    tpl = caminho_template(REPO, "f7").read_text(encoding="utf-8")
    assert "IMAGENS" not in valores(tpl, 6.0, R, G, {}, "f7", "T", ilustracoes=[_ilus(1, "x")])


def test_cartao_que_passa_do_fim_do_short_e_cortado_no_fim() -> None:
    ilus = Ilustracao(1, Deixa(5.0, 6.5, "Vans", "Vans"), Path("D1-c1.jpg"), "http://loja", "ok", (), False)
    assert 'data-start="5.0" data-duration="1.0"' in imagens_html([ilus], 6.0)
