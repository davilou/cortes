from pathlib import Path
from typing import Any

import pytest

from cortes.llm import ErroLLM
from cortes.render.processo import ErroRender
from cortes.render.trilha_mood import SCHEMA, Mood, ler_mood, preparar_mood, validar


class Llm:
    def __init__(self, resposta: dict[str, Any]) -> None:
        self.resposta, self.prompts = resposta, []

    def __call__(self, prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
        assert schema is SCHEMA and modelo == "sonnet" and "neutro" in sistema
        self.prompts.append(prompt)
        return self.resposta


def test_preparar_mood_chama_uma_vez_por_texto(tmp_path: Path) -> None:
    llm = Llm({"mood": "tensao", "motivo": "perdeu tudo na bolsa"})
    assert preparar_mood(tmp_path, "eu perdi tudo", llm) == Mood("tensao", "perdeu tudo na bolsa")
    assert preparar_mood(tmp_path, "eu perdi tudo", llm).mood == "tensao"
    assert len(llm.prompts) == 1 and "eu perdi tudo" in llm.prompts[0]
    preparar_mood(tmp_path, "texto novo", llm)
    assert len(llm.prompts) == 2


def test_ler_mood(tmp_path: Path) -> None:
    assert ler_mood(tmp_path, "x") is None
    preparar_mood(tmp_path, "x", Llm({"mood": "leve", "motivo": "piada"}))
    assert ler_mood(tmp_path, "x") == Mood("leve", "piada")
    assert ler_mood(tmp_path, "texto mudou") is None


def test_mood_fora_da_lista_e_erro() -> None:
    with pytest.raises(ErroRender, match="alegre"):
        validar({"mood": "alegre", "motivo": "x"})


def test_resposta_sem_motivo_e_erro() -> None:
    with pytest.raises(ErroRender, match="motivo"):
        validar({"mood": "neutro"})
    with pytest.raises(ErroRender, match="motivo"):
        validar({"mood": "neutro", "motivo": "  "})


def test_erro_do_llm_vira_erro_de_render(tmp_path: Path) -> None:
    def falha(prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
        raise ErroLLM("limite da assinatura")

    with pytest.raises(ErroRender, match="trilha: limite"):
        preparar_mood(tmp_path, "x", falha)
