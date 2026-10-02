"""Legenda do YouTube (json3) → palavras com tempo, sem Whisper (spec produção §4.2).

Automática: um segmento por palavra, com tOffsetMs. Manual: a linha inteira num segmento só —
o tempo é distribuído pelas palavras na proporção do tamanho. O json3 não traz o fim de cada
palavra: fim = início da seguinte, limitado a FIM_MAX_S (uma pausa longa não estica a palavra).
"""
import re
from typing import Any

from cortes.tipos import Palavra

FIM_MAX_S = 1.5
_MARCA = re.compile(r"\[[^\]]*\]")


class ErroLegenda(RuntimeError):
    pass


def _inicios_do_evento(ev: dict[str, Any]) -> list[tuple[str, float]]:
    t0 = ev["tStartMs"] / 1000
    fim_ev = t0 + ev.get("dDurationMs", 0) / 1000
    segs = [s for s in ev["segs"] if _MARCA.sub(" ", s.get("utf8", "")).strip()]
    saida: list[tuple[str, float]] = []
    for k, seg in enumerate(segs):
        ini = t0 + seg.get("tOffsetMs", 0) / 1000
        fim = t0 + segs[k + 1].get("tOffsetMs", 0) / 1000 if k + 1 < len(segs) else max(fim_ev, ini)
        palavras = _MARCA.sub(" ", seg["utf8"]).split()
        total = sum(len(w) for w in palavras)
        acumulado = 0
        for w in palavras:
            saida.append((w, ini + (fim - ini) * acumulado / total))
            acumulado += len(w)
    return saida


def palavras_do_json3(dados: dict[str, Any]) -> list[Palavra]:
    eventos = dados.get("events")
    if not isinstance(eventos, list):
        raise ErroLegenda("legenda do YouTube fora do formato json3 (sem 'events')")
    inicios = [par for ev in eventos if "segs" in ev for par in _inicios_do_evento(ev)]
    if not inicios:
        raise ErroLegenda("legenda do YouTube sem palavras")
    inicios.sort(key=lambda par: par[1])
    palavras: list[Palavra] = []
    for i, (texto, ini) in enumerate(inicios):
        seguinte = inicios[i + 1][1] if i + 1 < len(inicios) else ini + FIM_MAX_S
        palavras.append(Palavra(texto, round(ini, 3), round(min(seguinte, ini + FIM_MAX_S), 3)))
    return palavras
