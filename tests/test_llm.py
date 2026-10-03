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
    chamadas: list[tuple[list[str], str]] = []

    def executar(args: list[str], entrada: str) -> str:
        chamadas.append((args, entrada))
        return json.dumps(resposta)

    executar.chamadas = chamadas  # type: ignore[attr-defined]
    return executar


def test_devolve_structured_output_valido() -> None:
    ex = executor_que_devolve({"is_error": False, "structured_output": {"nota": 4}})
    assert chamar("prompt", SCHEMA, "sistema", executar=ex) == {"nota": 4}
    args, entrada = ex.chamadas[0]
    assert entrada == "prompt"
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
        chamar("p", SCHEMA, "s", executar=lambda a, e: "Error: not logged in")


def test_executar_timeout_levanta_erro_claro(monkeypatch: pytest.MonkeyPatch) -> None:
    def _run_que_expira(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd=["claude"], timeout=1)

    monkeypatch.setattr(subprocess, "run", _run_que_expira)
    with pytest.raises(ErroLLM, match="não respondeu"):
        llm._executar(["claude"], "x")


def test_comando_isola_contexto_e_nao_usa_bare() -> None:
    cmd = montar_comando("sis", SCHEMA, "sonnet")
    assert "--bare" not in cmd
    for flag in ["--system-prompt", "--setting-sources", "--strict-mcp-config",
                 "--no-session-persistence", "--json-schema"]:
        assert flag in cmd
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--setting-sources") + 1] == "project"
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == SCHEMA


def test_comando_com_read_libera_so_a_pasta_dada(tmp_path: Path) -> None:
    cmd = montar_comando("sis", SCHEMA, "sonnet", ferramentas="Read", pastas=[tmp_path])
    assert cmd[cmd.index("--tools") + 1] == "Read"
    assert cmd[cmd.index("--allowedTools") + 1] == "Read"
    assert cmd[cmd.index("--add-dir") + 1] == str(tmp_path)
    assert cmd.index("--add-dir") < cmd.index("--no-session-persistence")   # a lista variádica fecha


def test_comando_sem_ferramenta_nao_aceita_pasta(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="sem ferramenta"):
        montar_comando("sis", SCHEMA, "sonnet", pastas=[tmp_path])


def test_chamar_repassa_ferramenta_e_pasta(tmp_path: Path) -> None:
    ex = executor_que_devolve({"is_error": False, "structured_output": {"nota": 3}})
    chamar("p", SCHEMA, "s", executar=ex, ferramentas="Read", pastas=[tmp_path])
    args, _ = ex.chamadas[0]
    assert args[args.index("--add-dir") + 1] == str(tmp_path)
