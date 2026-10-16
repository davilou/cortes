from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from cortes.llm import ErroLLM
from cortes.render.corte import Edicoes, novo_corte, pasta_corte
from cortes.render.motion_prompt import Contexto
from cortes.render.processo import ErroRender
from cortes.render.seo import ARQUIVO, ler_seo, preparar_seo, tamanho_tags, texto_do_corte, validar
from cortes.tipos import Palavra

C = novo_corte(0, {"inicio": 10.0, "fim": 12.0, "titulo": "Ideia"}, "f7")
CTX = Contexto("Episódio 1", "PrimoCast")
BOM = {"titulo": "Como ele ganhou", "descricao": "Ele conta.", "hashtags": ["#dinheiro"],
       "tags": ["ganhar dinheiro"]}


def test_tamanho_tags_conta_virgula_e_aspas() -> None:
    assert tamanho_tags(("ab", "c d")) == 2 + 5 + 1
    assert tamanho_tags(()) == 0


@pytest.mark.parametrize(("campo", "valor", "erro"), [
    ("titulo", "a < b", "título com < ou >"),
    ("descricao", "x > y", "descrição com < ou >"),
    ("hashtags", ["#ok", "sem cerquilha"], "hashtag fora do formato"),
    ("hashtags", ["#dois termos"], "hashtag fora do formato"),
    ("tags", ["x" * 300, "y" * 300], "tags com 601 caracteres"),
    ("titulo", "   ", "vazios"),
])
def test_validar_recusa(campo: str, valor: Any, erro: str) -> None:
    with pytest.raises(ErroRender, match=erro):
        validar({**BOM, campo: valor})


def test_texto_do_corte_aplica_edicoes_sem_mascara() -> None:
    todas = [Palavra("antes", 9.0, 9.5), Palavra("porra", 10.1, 10.4), Palavra("ganhei", 10.5, 11.0),
             Palavra("muito", 11.1, 11.5), Palavra("depois", 13.0, 13.5)]
    c = replace(C, edicoes=Edicoes(legenda={3: ""}, mascaradas=(1,)))
    assert texto_do_corte(todas, c, 10.0, 12.0) == "porra ganhei"


def test_preparar_seo_grava_e_usa_o_cache_ate_o_texto_mudar(tmp_path: Path) -> None:
    chamadas: list[str] = []

    def llm(prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
        chamadas.append(prompt)
        return BOM

    s = preparar_seo(tmp_path, C, "eu ganhei", CTX, llm)
    assert s.titulo == "Como ele ganhou" and ler_seo(pasta_corte(tmp_path, 0)) == s
    assert "PrimoCast" in chamadas[0] and "eu ganhei" in chamadas[0] and "Ideia" in chamadas[0]
    preparar_seo(tmp_path, C, "eu ganhei", CTX, llm)
    assert len(chamadas) == 1
    preparar_seo(tmp_path, C, "eu perdi", CTX, llm)
    assert len(chamadas) == 2


def test_erro_do_llm_vira_erro_de_render_e_nada_e_gravado(tmp_path: Path) -> None:
    def quebra(*_: Any) -> dict[str, Any]:
        raise ErroLLM("claude saiu com código 1")

    with pytest.raises(ErroRender, match="SEO: claude saiu com código 1"):
        preparar_seo(tmp_path, C, "eu ganhei", CTX, quebra)
    assert not (pasta_corte(tmp_path, 0) / ARQUIVO).exists()
