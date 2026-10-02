"""Processos externos do render (ffmpeg, Python da visão, HyperFrames) atrás de um executor
injetável — os testes passam um falso; nada de rede, GPU ou render de verdade fora do `lento`."""
import subprocess
from collections.abc import Callable
from pathlib import Path

Rodar = Callable[[list[str], Path | None], tuple[int, str]]   # (args, cwd) → (código, stdout+stderr)
CAUDA = 1500   # caracteres do fim do log que vão para a mensagem de erro (a tela mostra)
TIMEOUT_S = 20 * 60   # render de 1-4 min por Short; acima disso algo travou (rede do CDN ou npx interativo)


class ErroRender(RuntimeError):
    """Falha no render de um corte. A mensagem traz o passo e o fim do log."""


def rodar_processo(args: list[str], cwd: Path | None) -> tuple[int, str]:
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired as ex:
        raise ErroRender(f"{args[0]} passou de {TIMEOUT_S // 60} min e foi interrompido") from ex
    return r.returncode, r.stdout + r.stderr


def exigir(rodar: Rodar, args: list[str], cwd: Path | None, passo: str) -> str:
    codigo, saida = rodar(args, cwd)
    if codigo != 0:
        raise ErroRender(f"{passo} falhou (código {codigo}): {saida[-CAUDA:]}")
    return saida
