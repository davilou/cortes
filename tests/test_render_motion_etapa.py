"""Etapa do motion do f3 pelo pipeline, com o LLM falso: cache, invalidação e erro claro."""
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from cortes.llm import ErroLLM
from cortes.render.corte import Edicoes
from cortes.render.motion_cache import NENHUMA, ler_cenas
from cortes.render.motion_params import Contador
from cortes.render.motion_svg import SCHEMA_SVG
from cortes.render.pipeline import montar_projeto
from cortes.render.processo import ErroRender
from tests.test_render_pipeline import C, Falso, episodio

C3 = replace(C, formato="f3", fim=16.0)
FALA = "Comprei por 400 mil reais, passou 10 anos, e hoje vale bem mais.".split()


def _episodio(tmp: Path) -> Path:
    pasta = episodio(tmp)
    palavras = [{"texto": t, "inicio": round(10.1 + 0.45 * i, 2), "fim": round(10.5 + 0.45 * i, 2)}
                for i, t in enumerate(FALA)]
    (pasta / "palavras.json").write_text(json.dumps(palavras), encoding="utf-8")
    meta = {"titulo": "COMO FULANO DE TAL INVESTE | Cast 1", "canal": "Cast", "id": "abcdefghijk"}
    (pasta / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return pasta


class LLM:
    def __init__(self, valor: float = 400, erro: Exception | None = None) -> None:
        self.valor, self.erro, self.prompts = valor, erro, []

    def __call__(self, prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        if self.erro:
            raise self.erro
        params = {"rotulo": "PAGOU", "valor": self.valor, "prefixo": "R$", "sufixo": "mil"}
        # depois do gancho (2 s)
        cena = {"componente": "contador", "inicio_palavra": 5, "fim_palavra": 9, "params": params}
        return {"tema": "dados", "cenas": [cena]}


def _montar(pasta: Path, tmp: Path, llm: LLM, c: Any = C3) -> str:
    f = Falso()
    montar_projeto(pasta, c, tmp, replace(f.dep(), chamar_llm=llm))
    return (pasta / "cortes" / "0" / "projeto" / "index.html").read_text(encoding="utf-8")


def test_f3_monta_as_cenas_e_reaproveita_o_cache(tmp_path: Path) -> None:
    pasta, llm = _episodio(tmp_path), LLM()
    html = _montar(pasta, tmp_path, llm)
    assert 'id="m1"' in html and 'contar("#m1-n", 0.0, 400' in html and '"div"' in html
    lido = ler_cenas(pasta / "cortes" / "0")
    assert lido is not None and lido.resultado.cenas[0].params == Contador("PAGOU", 400.0, "R$", "mil")
    _montar(pasta, tmp_path, llm)
    assert len(llm.prompts) == 1   # sem vão para cobrir, uma chamada; o cache não chama mais


def test_corrigir_a_legenda_ou_mudar_o_trecho_chama_o_llm_de_novo(tmp_path: Path) -> None:
    pasta, llm = _episodio(tmp_path), LLM()
    _montar(pasta, tmp_path, llm)
    _montar(pasta, tmp_path, llm, replace(C3, edicoes=Edicoes({1: "Comprei,"}, (), {}, "A")))
    assert len(llm.prompts) == 2
    (pasta / "cortes" / "0" / "motion" / "lixo.txt").write_text("x", encoding="utf-8")
    _montar(pasta, tmp_path, llm, replace(C3, inicio=10.2))
    assert len(llm.prompts) == 3 and not (pasta / "cortes" / "0" / "motion" / "lixo.txt").exists()


def test_sem_cena_valida_e_erro_claro_e_fica_no_cache(tmp_path: Path) -> None:
    pasta, llm = _episodio(tmp_path), LLM(valor=600)
    with pytest.raises(ErroRender, match=f"{NENHUMA}.*número que a fala não disse: 600 mil"):
        _montar(pasta, tmp_path, llm)
    with pytest.raises(ErroRender, match=NENHUMA):
        _montar(pasta, tmp_path, llm)
    assert len(llm.prompts) == 2


def test_erro_do_llm_vira_erro_do_render(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="Motion: cota"):
        _montar(_episodio(tmp_path), tmp_path, LLM(erro=ErroLLM("cota")))


def test_cache_adulterado_e_erro_claro(tmp_path: Path) -> None:
    pasta = _episodio(tmp_path)
    _montar(pasta, tmp_path, LLM())
    arq = pasta / "cortes" / "0" / "motion" / "cenas.json"
    b = json.loads(arq.read_text(encoding="utf-8"))
    b["cenas"][0]["params"]["valor"] = "muito"
    arq.write_text(json.dumps(b), encoding="utf-8")
    with pytest.raises(ErroRender, match="cache do motion inválido"):
        ler_cenas(pasta / "cortes" / "0")


def test_outros_formatos_nao_chamam_o_llm(tmp_path: Path) -> None:
    llm = LLM()
    _montar(_episodio(tmp_path), tmp_path, llm, replace(C3, formato="f7"))
    assert llm.prompts == []


def test_o_prompt_leva_o_titulo_e_o_canal_do_episodio(tmp_path: Path) -> None:
    llm = LLM()
    _montar(_episodio(tmp_path), tmp_path, llm)
    assert 'Episódio: "COMO FULANO DE TAL INVESTE | Cast 1" (canal: Cast)' in llm.prompts[0]


def test_sem_meta_json_ou_sem_titulo_e_erro_claro(tmp_path: Path) -> None:
    pasta, llm = _episodio(tmp_path), LLM()
    (pasta / "meta.json").write_text(json.dumps({"titulo": "T"}), encoding="utf-8")
    with pytest.raises(ErroRender, match="'titulo' e 'canal' deveriam ser texto"):
        _montar(pasta, tmp_path, llm)
    (pasta / "meta.json").unlink()
    with pytest.raises(ErroRender, match="meta.json não existe"):
        _montar(pasta, tmp_path, llm)
    assert llm.prompts == []


class LLMIlus:
    """Uma cena de ilustração; o SVG é `svg` (pode ser ruim). Conta as chamadas por tipo."""
    def __init__(self, svg: str) -> None:
        self.svg, self.cenas, self.svgs = svg, 0, []

    def __call__(self, prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
        if schema is SCHEMA_SVG:
            self.svgs.append(prompt)
            return {"svg": self.svg}
        self.cenas += 1
        params = {"descricao": "um apartamento", "rotulo": "APÊ", "icone": "casa"}
        return {"tema": "noite", "cenas": [{"componente": "ilustracao", "inicio_palavra": 5, "fim_palavra": 9,
                                            "params": params}]}


SVG_NOITE = ('<svg viewBox="0 0 1000 700"><rect x="100" y="100" width="800" height="500" '
             'fill="#12203a" stroke="#d9b46a"/></svg>')


def test_ilustracao_recusada_vira_icone_sem_derrubar_o_corte(tmp_path: Path) -> None:
    pasta, llm = _episodio(tmp_path), LLMIlus('<svg viewBox="0 0 1000 700"><script/></svg>')
    html = _montar(pasta, tmp_path, llm)
    ilus = html[html.index('<div class="ilus"'):html.index('class="ilus-rot"')]
    assert 'class="ilus-icone"' in ilus and "script" not in ilus and ">APÊ<" in html


def test_tema_do_editor_refaz_o_desenho_mas_nao_as_cenas(tmp_path: Path) -> None:
    pasta, llm = _episodio(tmp_path), LLMIlus(SVG_NOITE)
    html = _montar(pasta, tmp_path, llm)
    assert "--brand: #d9b46a" in html and 'fill="#12203a"' in html and (llm.cenas, len(llm.svgs)) == (1, 1)
    llm.svg = SVG_NOITE.replace("#12203a", "#13211c").replace("#d9b46a", "#3ddc84")
    html = _montar(pasta, tmp_path, llm, replace(C3, edicoes=Edicoes(trilha="A", tema="dados")))
    assert "--brand: #3ddc84" in html and 'fill="#13211c"' in html and (llm.cenas, len(llm.svgs)) == (1, 2)


def test_cache_do_f3_antigo_e_ignorado_e_refeito(tmp_path: Path) -> None:
    pasta, llm = _episodio(tmp_path), LLM()
    arq = pasta / "cortes" / "0" / "motion" / "cenas.json"
    arq.parent.mkdir(parents=True)
    arq.write_text(json.dumps({"formato": 1, "cenas": [{"componente": "valor_cheio"}]}), encoding="utf-8")
    _montar(pasta, tmp_path, llm)
    assert len(llm.prompts) == 1 and json.loads(arq.read_text(encoding="utf-8"))["formato"] == 2
