import xml.etree.ElementTree as ET

import pytest

from cortes.render.motion_params import Comodo, Planta
from cortes.render.motion_planta import LARGURA, PROFUNDIDADE, areas, caixas, planta_svg


def test_area_sem_valor_divide_o_resto_do_total() -> None:
    p = Planta((Comodo("Sala", 30), Comodo("Quarto", None), Comodo("Cozinha", None)), 72)
    assert areas(p) == [30.0, 21.0, 21.0]
    assert areas(Planta((Comodo("A", None), Comodo("B", None)))) == [1.0, 1.0]


def test_caixas_ocupam_a_planta_com_area_proporcional() -> None:
    p = Planta((Comodo("Sala", 30), Comodo("Quarto", 10)))
    a, b = caixas(p)
    assert (a.x, a.y, a.w, a.d) == (0.0, 0.0, 7.5, PROFUNDIDADE) and b.x == 7.5 and b.w == 2.5
    assert a.w * a.d == pytest.approx(3 * b.w * b.d)


def test_mais_de_3_comodos_em_duas_fileiras() -> None:
    cs = caixas(Planta(tuple(Comodo(f"C{j}", 10) for j in range(5))))
    assert [c.y for c in cs] == [0.0, 0.0, 0.0, 4.8, 4.8]
    assert sum(c.w for c in cs[:3]) == pytest.approx(LARGURA, abs=1e-3)


def test_svg_valido_com_os_nomes_escapados_e_um_grupo_por_comodo() -> None:
    p = Planta((Comodo("Sala <b>", 30), Comodo("Quarto", None)), 72)
    s = planta_svg(4, p)
    raiz = ET.fromstring(s)
    grupos = [g.get("id") for g in raiz.iter("{http://www.w3.org/2000/svg}g") if g.get("id")]
    assert grupos == ["m4-c0", "m4-c1"]
    assert "Sala &lt;b&gt;" in s and "30 m²" in s and "42 m²" not in s   # área não dita não aparece
