"""Processos externos do render (ffmpeg, Python da visão, HyperFrames) atrás de um executor
injetável — os testes passam um falso; nada de rede, GPU ou render de verdade fora do `lento`."""
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

Rodar = Callable[[list[str], Path | None], tuple[int, str]]   # (args, cwd) → (código, stdout+stderr)
CAUDA = 1500   # caracteres do fim do log que vão para a mensagem de erro (a tela mostra)
ESPERA_MORTE_S = 10   # depois de matar a árvore, quanto esperar os pipes fecharem
TIMEOUT_S = 20 * 60   # render de 1-4 min por Short; acima disso algo travou (rede do CDN ou npx interativo)


class ErroRender(RuntimeError):
    """Falha no render de um corte. A mensagem traz o passo e o fim do log."""


def _matar_arvore(p: "subprocess.Popen[str]") -> str:
    """Mata o processo e toda a árvore de filhos/netos que ele abriu. No Windows,
    `Popen.kill()` mata só o `npx.cmd`, e `node`/`chromium` (netos) continuam vivos com os
    pipes de stdout/stderr abertos — por isso o `communicate()` seguinte travaria para
    sempre. `taskkill /T` mata a árvore inteira pelo PID raiz. Devolve o problema do taskkill
    (código diferente de 0, ex.: 128 se o processo já tinha saído), ou "" se ele matou."""
    if sys.platform != "win32":
        p.kill()
        return ""
    r = subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, text=True,
                       errors="replace")
    if r.returncode == 0:
        return ""
    return f"taskkill falhou (código {r.returncode}): {(r.stdout + r.stderr).strip()[-300:]}"


_FLAGS = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0


def _texto_prazo(s: int) -> str:
    if s < 60:
        return f"{s} s"
    minutos, resto = divmod(s, 60)
    return f"{minutos} min" + (f" {resto} s" if resto else "")


def rodar_processo(args: list[str], cwd: Path | None) -> tuple[int, str]:
    return _rodar(args, cwd, TIMEOUT_S)


def rodar_com_prazo(prazo_s: int) -> Rodar:
    """Um `Rodar` com prazo próprio (ex.: download de imagem), matando a árvore como o do render."""
    return lambda args, cwd: _rodar(args, cwd, prazo_s)


def _rodar(args: list[str], cwd: Path | None, prazo_s: int) -> tuple[int, str]:
    p = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace", creationflags=_FLAGS)
    try:
        saida, _ = p.communicate(timeout=prazo_s)
    except subprocess.TimeoutExpired as ex:
        raise _interromper(p, args[0], prazo_s) from ex
    return p.returncode, saida


def _interromper(p: "subprocess.Popen[str]", nome: str, prazo_s: int) -> ErroRender:
    """Mata a árvore e espera os pipes fecharem, com prazo: se nem assim soltarem, o erro diz que o
    processo não morreu (e o que o taskkill respondeu) em vez de travar a fila."""
    problema = _matar_arvore(p)
    nota = f" ({problema})" if problema else ""
    try:
        p.communicate(timeout=ESPERA_MORTE_S)
    except subprocess.TimeoutExpired:
        return ErroRender(f"{nome} passou de {_texto_prazo(prazo_s)} e não morreu: os pipes seguiam "
                          f"abertos {_texto_prazo(ESPERA_MORTE_S)} depois de matar a árvore{nota}")
    return ErroRender(f"{nome} passou de {_texto_prazo(prazo_s)} e foi interrompido{nota}")


def exigir(rodar: Rodar, args: list[str], cwd: Path | None, passo: str) -> str:
    codigo, saida = rodar(args, cwd)
    if codigo != 0:
        raise ErroRender(f"{passo} falhou (código {codigo}): {saida[-CAUDA:]}")
    return saida
