"""Chamada ao Claude pela assinatura do Claude Code (`claude -p`), com saída validada por schema.

Não usa --bare: esse modo pula a leitura do login OAuth. Não há flag que impeça o CLAUDE.md
global de entrar; --setting-sources project + --strict-mcp-config + --system-prompt reduzem o
custo fixo para ~3,7 mil tokens por chamada (medido em 2026-09-30).
"""
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jsonschema

Executor = Callable[[list[str], str, Path | None], str]   # (args, entrada, cwd) → stdout
TIMEOUT_S = 900
# negadas pelo nome (somem do contexto) além de ficarem fora de --tools (nomes da doc de permissões)
FERRAMENTAS_NEGADAS = "Bash,PowerShell,Write,Edit,NotebookEdit,WebFetch,WebSearch"


class ErroLLM(RuntimeError):
    pass


def _flags_ferramentas(ferramentas: str) -> list[str]:
    """Sem ferramenta, `--tools ""` desliga todas. Com ferramenta (ex.: "Read" na conferência visual
    do Ilustrado), o escopo vem do cwd, não de regra de allow: não há `--allowedTools`, e o modo
    `dontAsk` nega sozinho tudo que pediria permissão — Read fora das pastas de trabalho incluído.
    Leitura dentro do cwd não pede permissão, então passa. Conferido numa chamada real em 2026-10-02
    (claude 2.1.280): Read da folha no cwd leu; Read de um arquivo do repo por caminho absoluto veio
    em `permission_denials`. Com o antigo `--allowedTools Read` o mesmo arquivo era lido."""
    if not ferramentas:
        return ["--tools", ""]
    return ["--tools", ferramentas, "--permission-mode", "dontAsk",
            "--disallowedTools", FERRAMENTAS_NEGADAS]


def montar_comando(sistema: str, schema: dict[str, Any], modelo: str, ferramentas: str = "") -> list[str]:
    return [
        "claude", "-p",
        "--output-format", "json",
        "--json-schema", json.dumps(schema, ensure_ascii=False),
        "--system-prompt", sistema,
        "--setting-sources", "project",
        "--strict-mcp-config",
        *_flags_ferramentas(ferramentas),
        "--no-session-persistence",
        "--model", modelo,
    ]


def _executar(args: list[str], entrada: str, cwd: Path | None) -> str:
    try:
        r = subprocess.run(args, input=entrada, capture_output=True, text=True,
                           encoding="utf-8", timeout=TIMEOUT_S, cwd=cwd)
    except subprocess.TimeoutExpired as e:
        raise ErroLLM(f"claude -p não respondeu em {TIMEOUT_S}s") from e
    if r.returncode != 0 and not r.stdout.strip():
        raise ErroLLM(f"claude saiu com código {r.returncode}: {r.stderr[-500:]}")
    return r.stdout


def _negadas(negacoes: Any) -> str:
    """O que foi negado, para a mensagem. Formato inesperado (não lista, item que não é dict) também
    é negação: vira texto como veio, nunca AttributeError."""
    if not isinstance(negacoes, list):
        return repr(negacoes)
    return str([d.get("tool_input") if isinstance(d, dict) else d for d in negacoes])


def chamar(prompt: str, schema: dict[str, Any], sistema: str, modelo: str = "sonnet",
           executar: Executor = _executar, ferramentas: str = "",
           pasta: Path | None = None) -> dict[str, Any]:
    """`pasta` é o cwd do `claude -p` e a única pasta que as ferramentas alcançam: exigida com
    ferramenta, recusada sem (o cwd do painel é o repositório)."""
    if bool(ferramentas) != (pasta is not None):
        raise ValueError("ferramenta e pasta andam juntas: a pasta é o escopo da ferramenta")
    saida = executar(montar_comando(sistema, schema, modelo, ferramentas), prompt, pasta)
    try:
        resposta = json.loads(saida)
    except json.JSONDecodeError as e:
        raise ErroLLM(f"saída do CLI não é JSON: {saida[:300]}") from e
    if resposta.get("is_error"):
        raise ErroLLM(f"CLI reportou erro: {str(resposta.get('result', ''))[:500]}")
    if resposta.get("permission_denials"):
        negadas = _negadas(resposta["permission_denials"])
        raise ErroLLM(f"o modelo tentou usar ferramenta fora do permitido: {negadas[:500]}")
    dados = resposta.get("structured_output")
    if not isinstance(dados, dict):
        raise ErroLLM("resposta sem structured_output")
    try:
        jsonschema.validate(dados, schema)
    except jsonschema.ValidationError as e:
        raise ErroLLM(f"structured_output fora do schema: {e.message}") from e
    return dados
