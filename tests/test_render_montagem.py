from pathlib import Path

import pytest

from cortes.render.legenda import Grupo
from cortes.render.montagem import FORMATOS, caminho_template, montar_html, valores
from cortes.render.processo import ErroRender
from cortes.render.rosto import Ponto, Rosto

REPO = Path(__file__).resolve().parents[1]
R = Rosto(1920, 1080, (Ponto(0.0, 960, 540, False),))


def test_placeholder_sobrando_e_erro() -> None:
    with pytest.raises(ErroRender, match=r"\{\{QW\}\}"):
        montar_html("<p>{{DUR}} {{QW}}</p>", {"DUR": "3"})


def test_formato_sem_template_e_erro() -> None:
    with pytest.raises(ErroRender, match="formato 'f4'"):
        caminho_template(REPO, "f4")


@pytest.mark.parametrize("formato", FORMATOS)
def test_templates_reais_montam_sem_sobra(formato: str) -> None:
    tpl = caminho_template(REPO, formato).read_text(encoding="utf-8")
    html = montar_html(tpl, valores(12.5, R, [Grupo(0.0, 1.0, ("Oi",))], [4.2]))
    assert 'data-duration="12.5"' in html and "3413px" in html and "<span>Oi</span>" in html
    assert "[4.2].forEach" in html
