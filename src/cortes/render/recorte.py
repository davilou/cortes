"""Trecho do Short: pausas cortadas pela energia do áudio e o recorte no ffmpeg (spec produção §4.1).

Portado de testes/comum/corte.py (dia 2), com uma diferença: as pausas vêm do ÁUDIO, não do vão
entre palavras. Na legenda do YouTube o fim de cada palavra é o início da seguinte (spec §4.2),
então esse vão é quase sempre zero. Regra mantida (testes/TEMPLATES.md, dia 2): pausa > 0,4 s,
só se estiver 18 dB abaixo da fala; 0,12 s de respiro de cada lado. Pausa "barulhenta" (riso,
reação) fica.
"""
import subprocess
from collections.abc import Callable
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from cortes.render.processo import CAUDA, ErroRender, Rodar, exigir
from cortes.tipos import Palavra

PAUSA_MIN = 0.4
RESPIRO = 0.12
SILENCIO_DB = 18.0
QUADRO_S = 0.02
PERCENTIL_FALA = 90   # nível de referência da fala: o trecho de um corte é quase todo fala
TAXA = 16000

Segmento = tuple[float, float]
LerAudio = Callable[[Path, float, float], NDArray[np.float32]]


def _db_por_quadro(audio: NDArray[np.float32], taxa: int) -> NDArray[np.float64]:
    n = int(taxa * QUADRO_S)
    k = len(audio) // n
    if k == 0:
        raise ErroRender("áudio do trecho mais curto que um quadro de 20 ms")
    q = audio[: k * n].astype(np.float64).reshape(k, n)
    return np.asarray(20 * np.log10(np.sqrt(np.mean(q ** 2, axis=1)) + 1e-9), dtype=np.float64)


def _corridas(marcas: NDArray[np.bool_]) -> list[tuple[int, int]]:
    """[início, fim) de cada sequência de True."""
    res: list[tuple[int, int]] = []
    ini: int | None = None
    for i, m in enumerate(marcas):
        if m and ini is None:
            ini = i
        elif not m and ini is not None:
            res.append((ini, i))
            ini = None
    if ini is not None:
        res.append((ini, len(marcas)))
    return res


def segmentos_sem_pausa(audio: NDArray[np.float32], taxa: int = TAXA) -> list[Segmento]:
    """Trechos a manter, em segundos desde o início do áudio."""
    db = _db_por_quadro(audio, taxa)
    silencio = db < float(np.percentile(db, PERCENTIL_FALA)) - SILENCIO_DB
    manter: list[Segmento] = []
    cursor = 0.0
    for a, b in _corridas(silencio):
        ta, tb = a * QUADRO_S, b * QUADRO_S
        if tb - ta <= PAUSA_MIN:
            continue
        manter.append((round(cursor, 3), round(ta + RESPIRO, 3)))
        cursor = tb - RESPIRO
    manter.append((round(cursor, 3), round(len(audio) / taxa, 3)))
    return manter


def remapear(t: float, segs: list[Segmento]) -> float:
    """Tempo do trecho original → tempo sem pausas. Um tempo dentro de uma pausa removida vai para
    a emenda: o início de palavra da legenda tem erro de ~0,3 s e pode cair na pausa sem ser bug."""
    acum = 0.0
    for a, b in segs:
        if t < a:
            return round(acum, 3)
        if t <= b:
            return round(acum + t - a, 3)
        acum += b - a
    return round(acum, 3)


def palavras_sem_pausa(ws: list[Palavra], segs: list[Segmento]) -> list[Palavra]:
    return [Palavra(p.texto, remapear(p.inicio, segs), remapear(p.fim, segs)) for p in ws]


def tempos_de_corte(segs: list[Segmento]) -> list[float]:
    """Instantes, no vídeo novo, em que uma pausa foi removida (onde o template alterna o zoom)."""
    acum, ts = 0.0, []
    for a, b in segs[:-1]:
        acum += b - a
        ts.append(round(acum, 3))
    return ts


def duracao(segs: list[Segmento]) -> float:
    return round(sum(b - a for a, b in segs), 3)


def args_recorte(video: Path, destino: Path, ini: float, segs: list[Segmento]) -> list[str]:
    """`-ss` antes do `-i` (busca rápida num episódio de 1 h) e trims relativos ao início do corte;
    micro-fade de 8 ms em cada emenda para o áudio não estalar."""
    partes, rot = [], []
    for i, (a, b) in enumerate(segs):
        partes.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}];"
                      f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,"
                      f"afade=t=in:d=0.008,afade=t=out:st={max(0.0, b - a - 0.008):.3f}:d=0.008[a{i}];")
        rot.append(f"[v{i}][a{i}]")
    fc = "".join(partes) + "".join(rot) + f"concat=n={len(segs)}:v=1:a=1[v][a]"
    return ["ffmpeg", "-v", "error", "-y", "-ss", f"{ini:.3f}", "-t", f"{segs[-1][1]:.3f}", "-i", str(video),
            "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16",
            "-preset", "fast", "-c:a", "aac", "-b:a", "192k", str(destino)]


def recortar(video: Path, destino: Path, ini: float, segs: list[Segmento], rodar: Rodar) -> None:
    parcial = destino.with_name(destino.stem + ".parcial.mp4")
    exigir(rodar, args_recorte(video, parcial, ini, segs), None, "recorte do trecho")
    parcial.replace(destino)


def ler_trecho_wav(audio: Path, ini: float, dur: float) -> NDArray[np.float32]:
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ini:.3f}", "-t", f"{dur:.3f}", "-i", str(audio),
                        "-ac", "1", "-ar", str(TAXA), "-f", "f32le", "-"], capture_output=True)
    if r.returncode != 0:
        raise ErroRender(f"ffmpeg falhou ao ler {audio}: {r.stderr.decode(errors='replace')[-CAUDA:]}")
    return np.frombuffer(r.stdout, dtype=np.float32)
