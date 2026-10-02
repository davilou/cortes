import sys
from pathlib import Path

import pytest

import cortes.render.processo as processo_mod
from cortes.render.processo import ErroRender, exigir, rodar_processo


def test_rodar_processo_que_trava_e_morto_de_verdade(monkeypatch: pytest.MonkeyPatch) -> None:
    """Processo real que dorme bem mais que o timeout: `rodar_processo` tem que matar a
    árvore inteira (não só o processo imediato) e devolver `ErroRender` em poucos segundos,
    sem ficar presa em `communicate()` por pipes herdados por netos (caso real do `npx.cmd`
    no Windows: cmd.exe → node → chromium)."""
    monkeypatch.setattr(processo_mod, "TIMEOUT_S", 1)
    args = [sys.executable, "-c", "import time; time.sleep(30)"]
    with pytest.raises(ErroRender, match="passou de 0 min"):
        rodar_processo(args, None)


def test_exigir_devolve_a_saida() -> None:
    assert exigir(lambda a, c: (0, "tudo certo"), ["x"], None, "teste") == "tudo certo"


def test_exigir_falha_alto_com_o_fim_do_log() -> None:
    log = "a" * 5000 + "causa real"

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        return 2, log

    with pytest.raises(ErroRender, match=r"recorte falhou \(código 2\).*causa real") as ex:
        exigir(rodar, ["ffmpeg"], None, "recorte")
    assert len(str(ex.value)) < 1700
