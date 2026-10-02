"""Legenda do YouTube (json3) → palavras com tempo, sem Whisper (spec produção §4.2).

Automática: um segmento por palavra, com tOffsetMs. Manual: a linha inteira num segmento só —
o tempo é distribuído pelas palavras na proporção do tamanho. O json3 não traz o fim de cada
palavra: fim = início da seguinte, limitado a FIM_MAX_S (uma pausa longa não estica a palavra).
Marcas entre colchetes (`[música]`, palavrão censurado `[ __ ]`) e marcas de troca de locutor
(`>>`) são descartadas de propósito: a palavra por trás delas não dá para recuperar.
"""
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cortes.tipos import Palavra

FIM_MAX_S = 1.5
MARCA = re.compile(r"\[[^\]]*\]|>>")


class ErroLegenda(RuntimeError):
    pass


Executor = Callable[[list[str]], subprocess.CompletedProcess[str]]
ARQUIVO = "legenda.pt.json3"


def comando(url: str, destino: Path) -> list[str]:
    """Só a faixa 'pt' original: pedir 'pt.*' traz a tradução 'pt-PT' e levou HTTP 429
    (conferido em 2026-10-02). Com --write-subs e --write-auto-subs, a manual tem preferência.

    Nome do arquivo conferido em 2026-10-02: o yt-dlp põe o idioma antes da extensão
    (<id>.pt.json3)."""
    return [sys.executable, "-m", "yt_dlp", "--skip-download", "--write-subs", "--write-auto-subs",
            "--sub-langs", "pt", "--sub-format", "json3", "--no-progress",
            "-o", str(destino / "legenda.%(ext)s"), url]


def _rodar(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")


def baixar(url: str, destino: Path, executar: Executor = _rodar) -> Path:
    arquivo = destino / ARQUIVO
    arquivo.unlink(missing_ok=True)  # um arquivo antigo não pode passar por resultado novo
    r = executar(comando(url, destino))
    if "HTTP Error 429" in r.stderr:
        raise ErroLegenda("YouTube limitou as requisições; tente em alguns minutos")
    if r.returncode != 0:
        raise ErroLegenda(f"yt-dlp falhou ao baixar a legenda: {r.stderr.strip()[-400:]}")
    if not arquivo.exists():
        raise ErroLegenda("vídeo sem legenda em português no YouTube")
    return arquivo


def _validar_evento(ev: dict[str, Any]) -> None:
    if not isinstance(ev.get("tStartMs"), (int, float)):
        raise ErroLegenda("legenda do YouTube fora do formato json3: evento sem 'tStartMs' numérico")
    segs = ev.get("segs")
    if not isinstance(segs, list):
        raise ErroLegenda("legenda do YouTube fora do formato json3: 'segs' do evento não é lista")
    for seg in segs:
        utf8 = seg.get("utf8", "") if isinstance(seg, dict) else None
        if not isinstance(utf8, str):
            raise ErroLegenda("legenda do YouTube fora do formato json3: segmento com 'utf8' que não é texto")


def _inicios_do_evento(ev: dict[str, Any]) -> list[tuple[str, float]]:
    t0 = ev["tStartMs"] / 1000
    fim_ev = t0 + ev.get("dDurationMs", 0) / 1000
    segs = [s for s in ev["segs"] if MARCA.sub(" ", s.get("utf8", "")).strip()]
    saida: list[tuple[str, float]] = []
    for k, seg in enumerate(segs):
        ini = t0 + seg.get("tOffsetMs", 0) / 1000
        fim = t0 + segs[k + 1].get("tOffsetMs", 0) / 1000 if k + 1 < len(segs) else max(fim_ev, ini)
        saida.extend(distribuir(MARCA.sub(" ", seg["utf8"]).split(), ini, fim))
    return saida


def distribuir(palavras: list[str], ini: float, fim: float) -> list[tuple[str, float]]:
    """Início de cada palavra de um trecho [ini, fim) sem tempo próprio, na proporção do
    tamanho (em caracteres) das palavras anteriores. Usado na legenda manual e na transcrição
    colada (`transcricao_colada`)."""
    total = sum(len(w) for w in palavras)
    saida: list[tuple[str, float]] = []
    acumulado = 0
    for w in palavras:
        saida.append((w, ini + (fim - ini) * acumulado / total))
        acumulado += len(w)
    return saida


def com_fim(inicios: list[tuple[str, float]]) -> list[Palavra]:
    """Fim = início da palavra seguinte, limitado a FIM_MAX_S (a última ganha FIM_MAX_S)."""
    palavras: list[Palavra] = []
    for i, (texto, ini) in enumerate(inicios):
        seguinte = inicios[i + 1][1] if i + 1 < len(inicios) else ini + FIM_MAX_S
        palavras.append(Palavra(texto, round(ini, 3), round(min(seguinte, ini + FIM_MAX_S), 3)))
    return palavras


def palavras_do_json3(dados: dict[str, Any]) -> list[Palavra]:
    eventos = dados.get("events")
    if not isinstance(eventos, list):
        raise ErroLegenda("legenda do YouTube fora do formato json3 (sem 'events')")
    inicios: list[tuple[str, float]] = []
    for ev in eventos:
        if "segs" not in ev:
            continue
        _validar_evento(ev)
        inicios.extend(_inicios_do_evento(ev))
    if not inicios:
        raise ErroLegenda("legenda do YouTube sem palavras")
    inicios.sort(key=lambda par: par[1])
    return com_fim(inicios)
