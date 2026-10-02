from pathlib import Path

import numpy as np
import pytest

from cortes.render.processo import ErroRender
from cortes.render.recorte import (
    args_recorte,
    duracao,
    palavras_sem_pausa,
    recortar,
    remapear,
    segmentos_sem_pausa,
    tempos_de_corte,
)
from cortes.tipos import Palavra

TAXA = 1000   # quadro de 20 ms = 20 amostras; seno de 50 Hz = 1 período por quadro (RMS constante)


def tom(s: float, amp: float = 0.5) -> np.ndarray:
    t = np.arange(int(s * TAXA)) / TAXA
    return (amp * np.sin(2 * np.pi * 50 * t)).astype(np.float32)


def silencio(s: float) -> np.ndarray:
    return np.zeros(int(s * TAXA), np.float32)


def test_pausa_longa_e_silenciosa_e_cortada_com_respiro() -> None:
    audio = np.concatenate([tom(1), silencio(1), tom(1)])
    assert segmentos_sem_pausa(audio, TAXA) == [(0.0, 1.12), (1.88, 3.0)]


def test_pausa_curta_fica() -> None:
    audio = np.concatenate([tom(1), silencio(0.3), tom(1)])
    assert segmentos_sem_pausa(audio, TAXA) == [(0.0, 2.3)]


def test_pausa_barulhenta_fica() -> None:   # 10 dB abaixo da fala (riso, reação): não é silêncio
    audio = np.concatenate([tom(1), tom(1, 0.5 * 10 ** (-10 / 20)), tom(1)])
    assert segmentos_sem_pausa(audio, TAXA) == [(0.0, 3.0)]


def test_silencio_na_borda_inicial_so_avanca_o_cursor() -> None:
    audio = np.concatenate([silencio(1), tom(2)])
    assert segmentos_sem_pausa(audio, TAXA) == [(0.88, 3.0)]


def test_silencio_na_borda_final_fecha_o_ultimo_segmento() -> None:
    audio = np.concatenate([tom(2), silencio(1)])
    assert segmentos_sem_pausa(audio, TAXA) == [(0.0, 2.12)]


def test_silencio_nas_duas_bordas() -> None:
    audio = np.concatenate([silencio(1), tom(2), silencio(1)])
    assert segmentos_sem_pausa(audio, TAXA) == [(0.88, 3.12)]


def test_audio_todo_silencioso_e_erro() -> None:
    with pytest.raises(ErroRender, match="só silêncio"):
        segmentos_sem_pausa(silencio(2), TAXA)


def test_remapear_leva_tempo_da_pausa_para_a_emenda() -> None:
    segs = [(0.0, 1.12), (1.88, 3.0)]
    assert [remapear(t, segs) for t in (0.5, 1.5, 2.0, 5.0)] == [0.5, 1.12, 1.24, 2.24]
    assert tempos_de_corte(segs) == [1.12] and duracao(segs) == 2.24


def test_palavras_sem_pausa() -> None:
    segs = [(0.0, 1.12), (1.88, 3.0)]
    assert palavras_sem_pausa([Palavra("oi", 2.0, 2.5)], segs) == [Palavra("oi", 1.24, 1.74)]


def test_args_do_recorte_buscam_antes_e_cortam_relativo() -> None:
    args = args_recorte(Path("v.mp4"), Path("t.mp4"), 100.0, [(0.0, 1.12), (1.88, 3.0)])
    assert args[:8] == ["ffmpeg", "-v", "error", "-y", "-ss", "100.000", "-t", "3.000"]
    fc = args[args.index("-filter_complex") + 1]
    assert "trim=0.000:1.120" in fc and "trim=1.880:3.000" in fc and fc.endswith("concat=n=2:v=1:a=1[v][a]")


def test_recortar_grava_por_parcial_e_falha_alto(tmp_path: Path) -> None:
    def ok(args: list[str], cwd: Path | None) -> tuple[int, str]:
        Path(args[-1]).write_bytes(b"mp4")
        return 0, ""

    recortar(Path("v.mp4"), tmp_path / "trecho.mp4", 0.0, [(0.0, 1.0)], ok)
    assert (tmp_path / "trecho.mp4").read_bytes() == b"mp4"
    with pytest.raises(ErroRender, match="recorte do trecho falhou"):
        recortar(Path("v.mp4"), tmp_path / "outro.mp4", 0.0, [(0.0, 1.0)], lambda a, c: (1, "ruim"))
    assert not (tmp_path / "outro.mp4").exists()
