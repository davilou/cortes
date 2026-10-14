"""Trilha de fundo do Short: contas puras de nível, clipes e HTML (spec trilha §5).

Regras de `pesquisa/04-trilha.md`: a cama fica ALVO_LU abaixo da voz, cada uma medida sozinha em
LUFS integrado (R1); entra com fade curto (R4) e sai num compasso inteiro que termina no fim do
vídeo (R5). Volume fixo, sem sidechain: as pausas já foram cortadas (R2). `data-volume` do
HyperFrames é ganho linear (`@hyperframes/core` 0.8.104, dist/audioGain.js).
"""
import math
import re
from dataclasses import dataclass

from cortes.render.processo import CAUDA, ErroRender

ALVO_LU = 18.0          # R1: voz 18 LU acima da cama
FADE_IN_S = 0.3         # R4
SOBREPOSICAO_S = 2.0    # crossfade entre repetições da cama (corte mais longo que ela)
TRACK = 11              # a voz (cam-audio) é a 10; repetições alternam 11/12 para se sobrepor
ARQUIVO_ASSET = "trilha.m4a"
_INTEGRADA = re.compile(r"I:\s+(-?[\d.]+) LUFS")
_TEMPO = re.compile(r"\bt:\s*([\d.]+)")
_MONO = re.compile(r"Stream #\S+.*Audio:.*\bmono\b")
DUPLICAR_DB = 10 * math.log10(2)   # mono nos dois canais do MP4 estéreo mede ~3,01 dB acima


@dataclass(frozen=True)
class Medida:
    lufs: float
    duracao: float


@dataclass(frozen=True)
class Clipe:
    inicio: float
    duracao: float
    media_inicio: float
    fade_in: float
    fade_out: float


def ler_ebur128(log: str) -> Medida:
    """O último `I: … LUFS` é o resumo (as linhas por quadro também têm `I:`); o último `t:` é a
    duração medida. Fonte mono (as camas da biblioteca) é medida como vai tocar: o render do
    HyperFrames sai estéreo, com o mono nos dois canais — +DUPLICAR_DB (achado no teste lento)."""
    integradas, tempos = _INTEGRADA.findall(log), _TEMPO.findall(log)
    if not integradas or not tempos:
        raise ErroRender(f"ebur128 sem loudness integrada: {log[-CAUDA:]}")
    extra = DUPLICAR_DB if _MONO.search(log) else 0.0
    return Medida(float(integradas[-1]) + extra, float(tempos[-1]))


def ganho(lufs_voz: float, lufs_cama: float, alvo_lu: float = ALVO_LU) -> float:
    """`data-volume` linear para a cama ficar `alvo_lu` abaixo da voz; nunca acima de 1.0 (não
    amplifica a cama)."""
    return min(1.0, 10 ** ((lufs_voz - alvo_lu - lufs_cama) / 20))


def compasso(bpm: float) -> float:
    return 4 * 60 / bpm


def clipes(dur: float, duracao_cama: float, bpm: float) -> list[Clipe]:
    if dur <= 0 or duracao_cama <= 2 * SOBREPOSICAO_S:
        raise ErroRender(f"trilha: duração inválida (corte {dur}s, cama {duracao_cama}s)")
    if dur <= duracao_cama:
        return [_clipe_unico(dur, duracao_cama, compasso(bpm))]
    return _encadeados(dur, duracao_cama, compasso(bpm))


def _clipe_unico(dur: float, duracao_cama: float, barra: float) -> Clipe:
    """Começa no ponto da cama que faz o vídeo terminar numa barra (R5); se essa barra passa do
    fim da cama, começa do zero, sem alinhar."""
    fim = math.ceil(dur / barra - 1e-9) * barra
    media = fim - dur if fim <= duracao_cama + 1e-9 else 0.0
    return Clipe(0.0, round(dur, 3), round(media, 3), FADE_IN_S, round(min(barra, dur / 2), 3))


def _encadeados(dur: float, duracao_cama: float, barra: float) -> list[Clipe]:
    """Repetições da cama a cada `duracao_cama - SOBREPOSICAO_S`, com crossfade de
    SOBREPOSICAO_S. A última sobra é sempre maior que SOBREPOSICAO_S (a anterior não coube)."""
    passo, res, t = duracao_cama - SOBREPOSICAO_S, [], 0.0
    while True:
        resto = dur - t
        ultimo = resto <= duracao_cama
        res.append(Clipe(round(t, 3), round(min(resto, duracao_cama), 3), 0.0,
                         FADE_IN_S if t == 0 else SOBREPOSICAO_S,
                         round(min(barra, resto / 2), 3) if ultimo else SOBREPOSICAO_S))
        if ultimo:
            return res
        t += passo


def html_trilha(cs: list[Clipe], volume: float) -> str:
    return "\n".join(
        f'      <audio id="trilha-{k}" src="assets/{ARQUIVO_ASSET}" data-start="{c.inicio}" '
        f'data-duration="{c.duracao}" data-media-start="{c.media_inicio}" '
        f'data-track-index="{TRACK + k % 2}" data-volume="{volume:.6g}" data-fade-in="{c.fade_in}" '
        f'data-fade-out="{c.fade_out}" data-audio-group="trilha"></audio>'
        for k, c in enumerate(cs))
