"""Detector de momentos: prompt → LLM (assinatura) → candidatos pontuados (spec §6.4)."""
from collections.abc import Callable
from typing import Any

from cortes import llm
from cortes.detector.pontuacao import converter
from cortes.detector.prompt import SISTEMA, montar_prompt, schema_candidatos
from cortes.perfil import Perfil
from cortes.tipos import Candidato, Frase

ChamarLLM = Callable[[str, dict[str, Any], str, str], dict[str, Any]]


def _chamar_real(prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
    return llm.chamar(prompt, schema, sistema, modelo)


def detectar(frases: list[Frase], energia: list[float], perfil: Perfil, modelo: str = "sonnet",
             chamar_llm: ChamarLLM = _chamar_real) -> tuple[list[Candidato], list[dict[str, Any]]]:
    if any(f.indice != i for i, f in enumerate(frases)):
        raise ValueError("frases fora de ordem: índice não bate com a posição")
    bruto = chamar_llm(montar_prompt(frases, perfil), schema_candidatos(perfil), SISTEMA, modelo)
    return converter(bruto, frases, perfil, energia)
