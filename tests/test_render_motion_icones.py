import xml.etree.ElementTree as ET

import pytest

from cortes.render.motion_icones import ICONES, NOMES_ICONES, icone_svg
from cortes.render.processo import ErroRender

TRACO = {"svg", "path", "circle", "rect", "line", "polyline", "ellipse"}


def test_conjunto_cobre_os_assuntos_da_spec() -> None:
    assert len(NOMES_ICONES) >= 30 and set(NOMES_ICONES) == set(ICONES)
    assert {"casa", "dinheiro", "grafico", "relogio", "pessoa", "check", "alerta", "saude"} <= set(ICONES)


@pytest.mark.parametrize("nome", sorted(ICONES))
def test_icone_e_svg_de_traco(nome: str) -> None:
    raiz = ET.fromstring(icone_svg(nome, "ic"))
    tags = {el.tag.split("}")[-1] for el in raiz.iter()}
    assert tags <= TRACO and raiz.get("viewBox") == "0 0 24 24" and raiz.get("class") == "ic"
    assert raiz.get("stroke") == "currentColor" and raiz.get("fill") == "none"
    assert all(el.get("fill") in (None, "none") for el in raiz.iter() if el is not raiz)


def test_icone_desconhecido_e_erro() -> None:
    with pytest.raises(ErroRender, match="ícone 'unicornio'"):
        icone_svg("unicornio", "ic")
