"""Chamada ao Claude pela assinatura do Claude Code (`claude -p`), com saída validada por schema.

Não usa --bare: esse modo pula a leitura do login OAuth. Não há flag que impeça o CLAUDE.md
global de entrar; --setting-sources project + --strict-mcp-config + --system-prompt reduzem o
custo fixo para ~3,7 mil tokens por chamada (medido em 2026-09-30).
"""
import json
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import jsonschema

Executor = Callable[[list[str], str], str]
TIMEOUT_S = 900


class ErroLLM(RuntimeError):
    pass


def _flags_ferramentas(ferramentas: str, pastas: Sequence[Path]) -> list[str]:
    """Sem ferramenta, `--tools ""` desliga todas. Com ferramenta (ex.: "Read" na conferência
    visual do Ilustrado), `--tools` limita o conjunto, `--allowedTools` a libera sem pedir
    permissão e `--add-dir` abre só as pastas dadas (flags conferidas no `claude --help`)."""
    if not ferramentas:
        if pastas:
            raise ValueError("pasta liberada sem ferramenta que a use")
        return ["--tools", ""]
    flags = ["--tools", ferramentas, "--allowedTools", ferramentas]
    for pasta in pastas:
        flags += ["--add-dir", str(pasta)]
    return flags


def montar_comando(sistema: str, schema: dict[str, Any], modelo: str, ferramentas: str = "",
                   pastas: Sequence[Path] = ()) -> list[str]:
    return [
        "claude", "-p",
        "--output-format", "json",
        "--json-schema", json.dumps(schema, ensure_ascii=False),
        "--system-prompt", sistema,
        "--setting-sources", "project",
        "--strict-mcp-config",
        *_flags_ferramentas(ferramentas, pastas),
        "--no-session-persistence",
        "--model", modelo,
    ]


def _executar(args: list[str], entrada: str) -> str:
    try:
        r = subprocess.run(args, input=entrada, capture_output=True, text=True,
                           encoding="utf-8", timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired as e:
        raise ErroLLM(f"claude -p não respondeu em {TIMEOUT_S}s") from e
    if r.returncode != 0 and not r.stdout.strip():
        raise ErroLLM(f"claude saiu com código {r.returncode}: {r.stderr[-500:]}")
    return r.stdout


def chamar(prompt: str, schema: dict[str, Any], sistema: str, modelo: str = "sonnet",
           executar: Executor = _executar, ferramentas: str = "",
           pastas: Sequence[Path] = ()) -> dict[str, Any]:
    saida = executar(montar_comando(sistema, schema, modelo, ferramentas, pastas), prompt)
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
