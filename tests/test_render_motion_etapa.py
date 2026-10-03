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
    return pasta


class LLM:
    def __init__(self, valor: float = 400, erro: Exception | None = None) -> None:
        self.valor, self.erro, self.prompts = valor, erro, []

    def __call__(self, prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        if self.erro:
            raise self.erro
        params = {"rotulo": "PAGOU", "valor": self.valor, "prefixo": "R$", "sufixo": "mil"}
        cena = {"componente": "contador", "inicio_palavra": 2, "fim_palavra": 6, "params": params}
        return {"cenas": [cena]}


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
    assert len(llm.prompts) == 1


def test_corrigir_a_legenda_ou_mudar_o_trecho_chama_o_llm_de_novo(tmp_path: Path) -> None:
    pasta, llm = _episodio(tmp_path), LLM()
    _montar(pasta, tmp_path, llm)
    _montar(pasta, tmp_path, llm, replace(C3, edicoes=Edicoes({1: "Comprei,"}, (), {})))
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
    assert len(llm.prompts) == 1


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
