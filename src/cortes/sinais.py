"""Energia RMS do áudio por janela de 0,5 s (spec §6.3). Risada entra no nicho de humor."""
import subprocess
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

JANELA_S = 0.5
TAXA = 16000


def ler_wav_mono(audio: Path, taxa: int = TAXA) -> NDArray[np.float32]:
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-f", "f32le", "-ac", "1",
                        "-ar", str(taxa), "-"], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(
            f"ffmpeg falhou ao ler {audio}: {r.stderr.decode(errors='replace')[-300:]}")
    return np.frombuffer(r.stdout, dtype=np.float32)


def energia_por_janela(amostras: NDArray[np.float32], taxa: int = TAXA,
                       janela_s: float = JANELA_S) -> list[float]:
    n = int(taxa * janela_s)
    k = len(amostras) // n
    if k == 0:
        raise ValueError("áudio mais curto que uma janela")
    blocos = amostras[: k * n].reshape(k, n)
    return [round(float(x), 5)
            for x in np.sqrt(np.mean(np.square(blocos, dtype=np.float32), axis=1))]
