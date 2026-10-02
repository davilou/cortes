"""Transcrição colada do YouTube ("Mostrar transcrição") → palavras com tempo (spec produção §4.2).

Saída de reserva quando o YouTube bloqueia o download da legenda (HTTP 429). O texto copiado
traz uma linha de tempo (`0:10`, `1:00:03`) seguida do texto do bloco, que pode ocupar várias
linhas. Só o início do bloco tem tempo: o bloco i vai de t_i a t_{i+1} e as palavras são
distribuídas nele pelo tamanho (`legenda_yt.distribuir`, a mesma regra da legenda manual);
o fim de cada palavra segue `legenda_yt.com_fim`. O último bloco não tem seguinte: dura
nº de palavras × S_POR_PALAVRA (fala média ~2,8 palavras/s). Precisão por palavra ~±0,3 s.
"""
import re
from dataclasses import dataclass, field

from cortes.producao.legenda_yt import MARCA, ErroLegenda, com_fim, distribuir
from cortes.tipos import Palavra

ARQUIVO = "transcricao.txt"   # em episodios/<id>/, gravado pela API na entrada
S_POR_PALAVRA = 0.35
MINIMO_PALAVRAS = 50
_TEMPO = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")


class ErroTranscricao(ErroLegenda):
    """Transcrição colada fora do formato. A mensagem diz a linha."""


@dataclass
class _Bloco:
    inicio: float
    palavras: list[str] = field(default_factory=list)


def _segundos(linha: str, n: int) -> float | None:
    """Segundos de uma linha de tempo; None se a linha não tem forma de tempo."""
    m = _TEMPO.fullmatch(linha)
    if not m:
        return None
    a, b, c = m.groups()
    if c is None:
        h, mi, s = 0, int(a), int(b)
    else:
        h, mi, s = int(a), int(b), int(c)
        if mi >= 60:
            raise ErroTranscricao(f"linha {n}: tempo inválido '{linha}' (minutos ≥ 60)")
    if s >= 60:
        raise ErroTranscricao(f"linha {n}: tempo inválido '{linha}' (segundos ≥ 60)")
    return float(h * 3600 + mi * 60 + s)


def _fmt(t: float) -> str:
    h, resto = divmod(int(t), 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _blocos(texto: str) -> list[_Bloco]:
    blocos: list[_Bloco] = []
    for n, bruta in enumerate(texto.lstrip("﻿").splitlines(), start=1):
        linha = bruta.strip()
        if not linha:
            continue
        t = _segundos(linha, n)
        if t is not None:
            if blocos and t <= blocos[-1].inicio:
                raise ErroTranscricao(f"linha {n}: tempo {linha} não é maior que o anterior "
                                      f"({_fmt(blocos[-1].inicio)})")
            blocos.append(_Bloco(t))
        elif not blocos:
            raise ErroTranscricao(f"linha {n}: texto antes do primeiro tempo — a transcrição deve "
                                  "começar com uma linha de tempo (ex.: 0:10); copie com os tempos")
        else:
            blocos[-1].palavras.extend(MARCA.sub(" ", linha).split())
    return blocos


def palavras_da_transcricao(texto: str) -> list[Palavra]:
    blocos = _blocos(texto)
    inicios: list[tuple[str, float]] = []
    for i, b in enumerate(blocos):
        fim = blocos[i + 1].inicio if i + 1 < len(blocos) else b.inicio + len(b.palavras) * S_POR_PALAVRA
        if b.palavras:
            inicios.extend(distribuir(b.palavras, b.inicio, fim))
    if not inicios:
        raise ErroTranscricao("transcrição colada sem palavras")
    if len(inicios) < MINIMO_PALAVRAS:
        raise ErroTranscricao(f"transcrição curta demais: {len(inicios)} palavras "
                              f"(mínimo {MINIMO_PALAVRAS}); cole a transcrição inteira do episódio")
    return com_fim(inicios)
