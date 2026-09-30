"""Chamada ao Claude pela assinatura do Claude Code (`claude -p`), com saída validada por schema.

Não usa --bare: esse modo pula a leitura do login OAuth. Não há flag que impeça o CLAUDE.md
global de entrar; --setting-sources project + --strict-mcp-config + --system-prompt reduzem o
custo fixo para ~3,7 mil tokens por chamada (medido em 2026-09-30).
"""
import json
import subprocess
from collections.abc import Callable
from typing import Any

import jsonschema

Executor = Callable[[list[str], str], str]
TIMEOUT_S = 900


class ErroLLM(RuntimeError):
    pass


def montar_comando(sistema: str, schema: dict[str, Any], modelo: str) -> list[str]:
    return [
        "claude", "-p",
        "--output-format", "json",
        "--json-schema", json.dumps(schema, ensure_ascii=False),
        "--system-prompt", sistema,
        "--setting-sources", "project",
        "--strict-mcp-config",
        "--tools", "",
        "--no-session-persistence",
        "--model", modelo,
    ]


def _executar(args: list[str], entrada: str) -> str:
    r = subprocess.run(args, input=entrada, capture_output=True, text=True,
                       encoding="utf-8", timeout=TIMEOUT_S)
    if r.returncode != 0 and not r.stdout.strip():
        raise ErroLLM(f"claude saiu com código {r.returncode}: {r.stderr[-500:]}")
    return r.stdout


def chamar(prompt: str, schema: dict[str, Any], sistema: str, modelo: str = "sonnet",
           executar: Executor = _executar) -> dict[str, Any]:
    saida = executar(montar_comando(sistema, schema, modelo), prompt)
    try:
        resposta = json.loads(saida)
    except json.JSONDecodeError as e:
        raise ErroLLM(f"saída do CLI não é JSON: {saida[:300]}") from e
    if resposta.get("is_error"):
        raise ErroLLM(f"CLI reportou erro: {str(resposta.get('result', ''))[:500]}")
    dados = resposta.get("structured_output")
    if not isinstance(dados, dict):
        raise ErroLLM("resposta sem structured_output")
    try:
        jsonschema.validate(dados, schema)
    except jsonschema.ValidationError as e:
        raise ErroLLM(f"structured_output fora do schema: {e.message}") from e
    return dados
