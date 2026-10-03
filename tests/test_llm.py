import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

import cortes.llm as llm
from cortes.llm import ErroLLM, chamar, montar_comando

SCHEMA: dict[str, Any] = {
    "type": "object", "required": ["nota"], "additionalProperties": False,
    "properties": {"nota": {"type": "integer", "minimum": 1, "maximum": 5}},
}


def executor_que_devolve(resposta: dict[str, Any]):  # type: ignore[no-untyped-def]
    chamadas: list[tuple[list[str], str, Path | None]] = []

    def executar(args: list[str], entrada: str, cwd: Path | None) -> str:
        chamadas.append((args, entrada, cwd))
        return json.dumps(resposta)

    executar.chamadas = chamadas  # type: ignore[attr-defined]
    return executar


def test_devolve_structured_output_valido() -> None:
    ex = executor_que_devolve({"is_error": False, "structured_output": {"nota": 4}})
    assert chamar("prompt", SCHEMA, "sistema", executar=ex) == {"nota": 4}
    args, entrada, cwd = ex.chamadas[0]
    assert entrada == "prompt" and cwd is None
    assert args[:2] == ["claude", "-p"]


def test_is_error_levanta() -> None:
    ex = executor_que_devolve({"is_error": True, "result": "limite de uso atingido"})
    with pytest.raises(ErroLLM, match="limite de uso"):
        chamar("p", SCHEMA, "s", executar=ex)


def test_sem_structured_output_levanta() -> None:
    ex = executor_que_devolve({"is_error": False, "result": "texto solto"})
    with pytest.raises(ErroLLM, match="structured_output"):
        chamar("p", SCHEMA, "s", executar=ex)


def test_fora_do_schema_levanta() -> None:
    ex = executor_que_devolve({"is_error": False, "structured_output": {"nota": 9}})
    with pytest.raises(ErroLLM, match="fora do schema"):
        chamar("p", SCHEMA, "s", executar=ex)


def test_saida_nao_json_levanta() -> None:
    with pytest.raises(ErroLLM, match="não é JSON"):
        chamar("p", SCHEMA, "s", executar=lambda a, e, c: "Error: not logged in")


def test_executar_timeout_levanta_erro_claro(monkeypatch: pytest.MonkeyPatch) -> None:
    def _run_que_expira(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd=["claude"], timeout=1)

    monkeypatch.setattr(subprocess, "run", _run_que_expira)
    with pytest.raises(ErroLLM, match="não respondeu"):
        llm._executar(["claude"], "x", None)


def test_comando_isola_contexto_e_nao_usa_bare() -> None:
    cmd = montar_comando("sis", SCHEMA, "sonnet")
    assert "--bare" not in cmd
    for flag in ["--system-prompt", "--setting-sources", "--strict-mcp-config",
                 "--no-session-persistence", "--json-schema"]:
        assert flag in cmd
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--setting-sources") + 1] == "project"
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == SCHEMA


def test_comando_com_read_nao_libera_read_em_todo_caminho() -> None:
    """Escopo pelo cwd: sem `--allowedTools Read` (liberava qualquer caminho) e sem `--add-dir`;
    `dontAsk` nega o que pediria permissão e as outras ferramentas são negadas pelo nome."""
    cmd = montar_comando("sis", SCHEMA, "sonnet", ferramentas="Read")
    assert cmd[cmd.index("--tools") + 1] == "Read"
    assert "--allowedTools" not in cmd and "--add-dir" not in cmd
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    negadas = cmd[cmd.index("--disallowedTools") + 1].split(",")
    assert {"Bash", "PowerShell", "Write", "Edit", "WebFetch", "WebSearch"} <= set(negadas)
    assert cmd.index("--disallowedTools") < cmd.index("--no-session-persistence")   # variádica fecha


def test_ferramenta_e_pasta_andam_juntas(tmp_path: Path) -> None:
    ex = executor_que_devolve({"is_error": False, "structured_output": {"nota": 3}})
    with pytest.raises(ValueError, match="juntas"):
        chamar("p", SCHEMA, "s", executar=ex, pasta=tmp_path)
    with pytest.raises(ValueError, match="juntas"):
        chamar("p", SCHEMA, "s", executar=ex, ferramentas="Read")


def test_chamar_com_ferramenta_roda_na_pasta(tmp_path: Path) -> None:
    ex = executor_que_devolve({"is_error": False, "structured_output": {"nota": 3}})
    chamar("p", SCHEMA, "s", executar=ex, ferramentas="Read", pasta=tmp_path)
    _, _, cwd = ex.chamadas[0]
    assert cwd == tmp_path


def test_ferramenta_negada_e_erro_mesmo_com_resposta_valida() -> None:
    negada = [{"tool_name": "Read", "tool_input": {"file_path": "C:\repo\pyproject.toml"}}]
    ex = executor_que_devolve({"is_error": False, "structured_output": {"nota": 3},
                               "permission_denials": negada})
    with pytest.raises(ErroLLM, match="fora do permitido.*pyproject"):
        chamar("p", SCHEMA, "s", executar=ex)


def test_executar_roda_no_cwd_dado(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    visto: dict[str, Any] = {}

    def _run(*args: Any, **kwargs: Any) -> Any:
        visto.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "{}", "")

    monkeypatch.setattr(subprocess, "run", _run)
    llm._executar(["claude"], "x", tmp_path)
    assert visto["cwd"] == tmp_path
