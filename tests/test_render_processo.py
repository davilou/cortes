import subprocess
import sys
from pathlib import Path

import pytest

import cortes.render.processo as processo_mod
from cortes.render.processo import ErroRender, exigir, rodar_com_prazo, rodar_processo


def test_rodar_processo_que_trava_e_morto_de_verdade(monkeypatch: pytest.MonkeyPatch) -> None:
    """Processo real que dorme bem mais que o timeout: `rodar_processo` tem que matar a
    árvore inteira (não só o processo imediato) e devolver `ErroRender` em poucos segundos,
    sem ficar presa em `communicate()` por pipes herdados por netos (caso real do `npx.cmd`
    no Windows: cmd.exe → node → chromium)."""
    monkeypatch.setattr(processo_mod, "TIMEOUT_S", 1)
    args = [sys.executable, "-c", "import time; time.sleep(30)"]
    with pytest.raises(ErroRender, match="passou de 1 s"):
        rodar_processo(args, None)


def test_rodar_com_prazo_proprio_mata_a_arvore_no_prazo() -> None:
    """Prazo curto por chamada (download de imagem do f9) sem mexer no TIMEOUT_S do render."""
    args = [sys.executable, "-c", "import time; time.sleep(30)"]
    with pytest.raises(ErroRender, match="passou de 1 s"):
        rodar_com_prazo(1)(args, None)
    codigo, saida = rodar_com_prazo(5)([sys.executable, "-c", "print('ok')"], None)
    assert (codigo, saida.strip()) == (0, "ok")


def test_exigir_devolve_a_saida() -> None:
    assert exigir(lambda a, c: (0, "tudo certo"), ["x"], None, "teste") == "tudo certo"


def test_exigir_falha_alto_com_o_fim_do_log() -> None:
    log = "a" * 5000 + "causa real"

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        return 2, log

    with pytest.raises(ErroRender, match=r"recorte falhou \(código 2\).*causa real") as ex:
        exigir(rodar, ["ffmpeg"], None, "recorte")
    assert len(str(ex.value)) < 1700


class PopenQueTrava:
    """Processo falso cujo `communicate` estoura sempre: nem o taskkill solta os pipes."""
    pid = 4242
    returncode = None

    def __init__(self, *a: object, **k: object) -> None:
        self.esperas: list[float | None] = []

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        self.esperas.append(timeout)
        PopenQueTrava.ultimo = self
        raise subprocess.TimeoutExpired("x", timeout or 0)

    ultimo: "PopenQueTrava"


def _taskkill(codigo: int, chamados: list[list[str]]):  # type: ignore[no-untyped-def]
    def run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        chamados.append(args)
        return subprocess.CompletedProcess(args, codigo, "ERRO: acesso negado", "")
    return run


def test_arvore_que_nao_morre_vira_erro_com_a_causa(monkeypatch: pytest.MonkeyPatch) -> None:
    chamados: list[list[str]] = []
    monkeypatch.setattr(processo_mod.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "Popen", PopenQueTrava)
    monkeypatch.setattr(subprocess, "run", _taskkill(1, chamados))
    with pytest.raises(ErroRender, match=r"ffmpeg passou de 2 s.*não morreu.*código 1.*acesso negado"):
        rodar_com_prazo(2)(["ffmpeg"], None)
    assert chamados == [["taskkill", "/F", "/T", "/PID", "4242"]]
    assert PopenQueTrava.ultimo.esperas == [2, 10]   # o segundo communicate tem prazo: nada de travar


def test_taskkill_ok_mas_pipes_presos_tambem_e_erro(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(processo_mod.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "Popen", PopenQueTrava)
    monkeypatch.setattr(subprocess, "run", _taskkill(0, []))
    with pytest.raises(ErroRender, match=r"não morreu.*10 s"):
        rodar_com_prazo(2)(["ffmpeg"], None)


def test_taskkill_que_falha_mas_processo_morto_e_so_o_erro_de_prazo(monkeypatch: pytest.MonkeyPatch) -> None:
    class PopenQueMorre(PopenQueTrava):
        def communicate(self, timeout: float | None = None) -> tuple[str, str]:
            self.esperas.append(timeout)
            if len(self.esperas) == 1:
                raise subprocess.TimeoutExpired("x", timeout or 0)
            return "", ""

    monkeypatch.setattr(processo_mod.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "Popen", PopenQueMorre)
    monkeypatch.setattr(subprocess, "run", _taskkill(128, []))   # 128: o processo já tinha saído
    with pytest.raises(ErroRender, match=r"passou de 2 s e foi interrompido \(taskkill.*código 128"):
        rodar_com_prazo(2)(["ffmpeg"], None)


@pytest.mark.parametrize(("s", "texto"), [(30, "30 s"), (60, "1 min"), (90, "1 min 30 s"), (120, "2 min")])
def test_texto_prazo_nao_arredonda_minuto_quebrado(s: int, texto: str) -> None:
    """O prazo de 90 s do trecho do B-roll aparecia como "passou de 1 min" (render real de 2026-10-03)."""
    assert processo_mod._texto_prazo(s) == texto
