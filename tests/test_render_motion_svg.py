import json
from pathlib import Path
from typing import Any

import pytest

from cortes.llm import ErroLLM
from cortes.render.motion_params import Ilustracao
from cortes.render.motion_svg import SCHEMA_SVG, ErroSvg, sanitizar, svg_da_cena, textos_svg
from cortes.render.motion_tema import cores_do_tema

CORES = cores_do_tema("escuro")   # #ff6a3d é o acento
BOM = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 700">'
       '<defs><linearGradient id="g1"><stop offset="0" stop-color="#ff6a3d"/></linearGradient></defs>'
       '<circle cx="500" cy="350" r="200" fill="url(#g1)" stroke="#F2F2F2" stroke-width="6"/>'
       '<path d="M100 100 L300 300" stroke="#ff6a3d"/><text x="500" y="650" text-anchor="middle" '
       'fill="#f2f2f2">testa</text></svg>')
IL = Ilustracao("rosto com os músculos da testa", "TESTA", "pessoa")


def test_svg_bom_sai_re_serializado_com_ids_prefixados() -> None:
    s = sanitizar(BOM, CORES, "s3-")
    assert s.startswith('<svg viewBox="0 0 1000 700" xmlns="http://www.w3.org/2000/svg"')
    assert 'id="s3-g1"' in s and 'fill="url(#s3-g1)"' in s and 'r="200"' in s and ">testa</text>" in s
    assert textos_svg(s) == ["testa"]


@pytest.mark.parametrize("ruim, motivo", [
    (BOM.replace("<defs>", "<script>alert(1)</script><defs>"), "elemento 'script'"),
    (BOM.replace("<path ", '<path onclick="x()" '), "atributo 'onclick'"),
    (BOM.replace("<path ", '<image href="http://x/y.png"/><path '), "elemento 'image'"),
    (BOM.replace("<path ", '<foreignObject/><path '), "elemento 'foreignObject'"),
    (BOM.replace('stroke="#ff6a3d"/>', 'stroke="#00ff00"/>'), "cor '#00ff00'"),
    (BOM.replace('fill="url(#g1)"', 'fill="url(http://x)"'), "url"),
    (BOM.replace('viewBox="0 0 1000 700"', 'viewBox="0 0 500 500"'), "viewBox"),
    ('<!DOCTYPE svg [<!ENTITY a "b">]>' + BOM, "DOCTYPE"),
    ("<svg", "XML inválido"),
    ('<g viewBox="0 0 1000 700"/>', "raiz"),
    (BOM.replace("</svg>", "<g/>" * 401 + "</svg>"), "elementos"),
    (BOM.replace("</svg>", "<!--" + "x" * 8000 + "--></svg>"), "KB"),
    (BOM.replace('<path ', '<path style="fill:red" '), "atributo 'style'"),
], ids=lambda x: x[:30] if isinstance(x, str) else x)
def test_svg_ruim_e_recusado_com_motivo(ruim: str, motivo: str) -> None:
    with pytest.raises(ErroSvg, match=motivo):
        sanitizar(ruim, CORES, "s1-")


class Llm:
    def __init__(self, svg: str | Exception) -> None:
        self.svg, self.prompts = svg, []

    def __call__(self, prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
        assert schema is SCHEMA_SVG
        self.prompts.append(prompt)
        if isinstance(self.svg, Exception):
            raise self.svg
        return {"svg": self.svg}


def test_svg_da_cena_com_cache_pela_descricao_e_tema(tmp_path: Path) -> None:
    llm = Llm(BOM)
    svg, motivo = svg_da_cena(tmp_path, 2, IL, "escuro", ["testa"], llm)
    assert motivo is None and svg is not None and 'id="s2-g1"' in svg
    assert "rosto com os músculos da testa" in llm.prompts[0] and "#ff6a3d" in llm.prompts[0]
    assert svg_da_cena(tmp_path, 2, IL, "escuro", ["testa"], llm) == (svg, None)
    assert len(llm.prompts) == 1
    svg_da_cena(tmp_path, 2, IL, "clinico", ["testa"], Llm(BOM.replace("#ff6a3d", "#2f7de1")
                                                          .replace("#F2F2F2", "#16202a")
                                                          .replace("#f2f2f2", "#16202a")))
    assert json.loads((tmp_path / "motion" / "svg" / "2.json").read_text(encoding="utf-8"))["chave"]["tema"] \
        == "clinico"


def test_svg_recusado_vira_motivo_e_fica_no_cache(tmp_path: Path) -> None:
    llm = Llm(BOM.replace("<path ", '<path onload="x" '))
    svg, motivo = svg_da_cena(tmp_path, 1, IL, "escuro", [], llm)
    assert svg is None and motivo is not None and "onload" in motivo
    svg_da_cena(tmp_path, 1, IL, "escuro", [], llm)
    assert len(llm.prompts) == 1


def test_numero_nao_dito_no_svg_e_recusado(tmp_path: Path) -> None:
    llm = Llm(BOM.replace(">testa<", ">72 m²<"))
    assert svg_da_cena(tmp_path, 1, IL, "escuro", ["um", "apartamento"], llm)[1] == \
        "número que a fala não disse no desenho: 72"
    dito = Llm(BOM.replace(">testa<", ">72 m²<"))
    assert svg_da_cena(tmp_path, 4, IL, "escuro", ["72", "metros"], dito)[1] is None


def test_erro_do_llm_vira_motivo_sem_cache(tmp_path: Path) -> None:
    svg, motivo = svg_da_cena(tmp_path, 1, IL, "escuro", [], Llm(ErroLLM("cota")))
    assert svg is None and motivo == "LLM: cota"
    assert not (tmp_path / "motion" / "svg" / "1.json").exists()


def test_numero_depois_do_tspan_tambem_conta() -> None:
    s = sanitizar(BOM.replace(">testa</text>", ">Valor <tspan>x</tspan> 500 mil</text>"), CORES, "s1-")
    assert textos_svg(s) == ["Valor x 500 mil"]


def test_atributos_inofensivos_saem_em_vez_de_recusar() -> None:
    cru = (BOM.replace('viewBox="0 0 1000 700">', 'viewBox="0 0 1000 700" version="1.1" width="1000" '
                       'height="700" preserveAspectRatio="xMidYMid meet"><title>t</title><desc>d</desc>')
           .replace('text-anchor="middle"', 'text-anchor="middle" font-family="Arial" class="x"'))
    s = sanitizar(cru, CORES, "s1-")
    assert "version" not in s and "font-family" not in s and "class" not in s and "<title" not in s
    assert 'r="200"' in s


def test_prompt_lista_os_atributos_permitidos() -> None:
    from cortes.render.motion_svg import prompt_svg
    p = prompt_svg(IL, "escuro")
    assert "stroke-width" in p and "text-anchor" in p and "font-family" in p
