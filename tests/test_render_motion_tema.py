import pytest

from cortes.render.motion_tema import TEMA_PADRAO, TEMAS, cores_do_tema, css_do_tema
from cortes.render.processo import ErroRender


def test_os_quatro_temas_da_spec() -> None:
    assert set(TEMAS) == {"escuro", "noite", "clinico", "dados"} and TEMA_PADRAO == "escuro"


@pytest.mark.parametrize("nome", ["escuro", "noite", "clinico", "dados"])
def test_css_leva_as_cores_do_tema(nome: str) -> None:
    p, css = TEMAS[nome], css_do_tema(nome)
    assert css.startswith(":root {") and all(c in css for c in (p.fundo, p.cartao, p.texto, p.acento))


def test_cores_do_tema_em_minusculas_para_o_sanitizador() -> None:
    cores = cores_do_tema("clinico")
    assert "#2f7de1" in cores and all(c == c.lower() and c.startswith("#") for c in cores)


def test_tema_desconhecido_e_erro() -> None:
    with pytest.raises(ErroRender, match="tema 'roxo'"):
        css_do_tema("roxo")
