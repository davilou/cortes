import os
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from cortes.producao import transcricao_local
from cortes.producao.transcricao_local import (
    PASTAS_DLL,
    SEM_MEMORIA,
    SEM_MODELO,
    ErroTranscricao,
    palavras_dos_segmentos,
    pastas_dll,
    sem_memoria,
    transcrever,
)
from cortes.tipos import Palavra


@dataclass(frozen=True)
class W:
    word: str
    start: float
    end: float


@dataclass(frozen=True)
class S:
    words: list[W] | None


def test_palavras_sem_espaco_e_tempo_em_ms() -> None:
    segs = [S([W(" Eu", 0.12345, 0.4), W(" ganhei", 0.4, 0.80049)]), S([W(" mil.", 1.0, 1.5)])]
    assert palavras_dos_segmentos(segs) == [Palavra("Eu", 0.123, 0.4), Palavra("ganhei", 0.4, 0.8),
                                            Palavra("mil.", 1.0, 1.5)]


def test_tempo_numpy_vira_float_do_python() -> None:
    p = palavras_dos_segmentos([S([W("oi", np.float64(0.5), np.float64(0.9))])])[0]
    assert type(p.inicio) is float and type(p.fim) is float


def test_palavra_vazia_e_segmento_sem_palavras_somem() -> None:
    segs = [S(None), S([W("  ", 0.0, 0.1), W(" oi", 0.2, 0.3)]), S([])]
    assert palavras_dos_segmentos(segs) == [Palavra("oi", 0.2, 0.3)]


def test_inicio_nao_volta_e_fim_nao_fica_antes_do_inicio() -> None:
    ps = palavras_dos_segmentos([S([W("a", 2.0, 2.5), W("b", 1.9, 1.95), W("c", 3.0, 2.8)])])
    assert ps[1] == Palavra("b", 2.0, 2.0)
    assert ps[2] == Palavra("c", 3.0, 3.0)


def test_sem_palavras_e_erro() -> None:
    with pytest.raises(ErroTranscricao, match="nenhuma palavra"):
        palavras_dos_segmentos([S(None), S([W(" ", 0, 1)])])


def test_pastas_dll_ausentes_dizem_o_que_instalar(tmp_path: Path) -> None:
    (tmp_path / PASTAS_DLL[0]).mkdir(parents=True)
    with pytest.raises(ErroTranscricao, match="instale nvidia-cublas-cu12 e nvidia-cudnn-cu12") as exc:
        pastas_dll(tmp_path)
    assert "cudnn" in str(exc.value)


def test_pastas_dll_presentes(tmp_path: Path) -> None:
    for sub in PASTAS_DLL:
        (tmp_path / sub).mkdir(parents=True)
    assert pastas_dll(tmp_path) == [tmp_path / sub for sub in PASTAS_DLL]


@pytest.mark.parametrize("msg, oom", [
    ("CUDA failed with error out of memory", True),
    ("cuBLAS failed with status CUBLAS_STATUS_ALLOC_FAILED", True),
    ("cuDNN failed with status CUDNN_STATUS_ALLOC_FAILED", True),
    ("CUDA failed with error invalid device ordinal", False),
])
def test_reconhece_falta_de_memoria_da_gpu(msg: str, oom: bool) -> None:
    assert sem_memoria(RuntimeError(msg)) is oom



class Pesos:
    def __init__(self) -> None:
        self.liberado = False

    def unload_model(self) -> None:
        self.liberado = True


class Pipeline:
    """Imita BatchedInferencePipeline: .model (WhisperModel) .model (ctranslate2 Whisper)."""

    def __init__(self, erro: Exception | None = None) -> None:
        self.pesos = Pesos()
        self.model = type("WhisperModel", (), {"model": self.pesos})()
        self.erro = erro

    def transcribe(self, audio: object, **kw: object) -> tuple[list[S], None]:
        if self.erro is not None:
            raise self.erro
        return [S([W(" oi", 0.0, 0.2)])], None


def com_pipeline(monkeypatch: pytest.MonkeyPatch, p: Pipeline) -> Pipeline:
    monkeypatch.setattr("cortes.sinais.ler_wav_mono", lambda audio: np.zeros(16000, dtype=np.float32))
    monkeypatch.setattr(transcricao_local, "_carregar", lambda: p)
    return p


def test_transcrever_libera_a_gpu_depois_de_transcrever(monkeypatch: pytest.MonkeyPatch) -> None:
    p = com_pipeline(monkeypatch, Pipeline())
    assert transcrever(Path("a.wav")) == [Palavra("oi", 0.0, 0.2)]
    assert p.pesos.liberado


def test_gpu_sem_memoria_vira_erro_claro_e_libera(monkeypatch: pytest.MonkeyPatch) -> None:
    p = com_pipeline(monkeypatch, Pipeline(RuntimeError("CUDA failed with error out of memory")))
    with pytest.raises(ErroTranscricao, match="placa de vídeo sem memória") as exc:
        transcrever(Path("a.wav"))
    assert str(exc.value) == SEM_MEMORIA and p.pesos.liberado


def test_erro_de_transcricao_passa_direto(monkeypatch: pytest.MonkeyPatch) -> None:
    p = com_pipeline(monkeypatch, Pipeline(ErroTranscricao("alloc_failed de mentira")))
    with pytest.raises(ErroTranscricao, match="alloc_failed de mentira"):
        transcrever(Path("a.wav"))
    assert p.pesos.liberado


def test_outro_runtime_error_sobe_como_veio(monkeypatch: pytest.MonkeyPatch) -> None:
    p = com_pipeline(monkeypatch, Pipeline(RuntimeError("invalid device ordinal")))
    with pytest.raises(RuntimeError, match="invalid device ordinal") as exc:
        transcrever(Path("a.wav"))
    assert not isinstance(exc.value, ErroTranscricao) and p.pesos.liberado


def test_modelo_fora_do_cache_diz_como_baixar(monkeypatch: pytest.MonkeyPatch) -> None:
    import faster_whisper
    from huggingface_hub.errors import LocalEntryNotFoundError

    def sem_cache(*args: object, **kw: object) -> None:
        assert kw["local_files_only"] is True
        raise LocalEntryNotFoundError("não está no cache")

    monkeypatch.setattr(transcricao_local, "_registrar_dlls", lambda: None)
    monkeypatch.setattr(faster_whisper, "WhisperModel", sem_cache)
    with pytest.raises(ErroTranscricao) as exc:
        transcricao_local._carregar()
    assert str(exc.value) == SEM_MODELO and "uma vez com internet" in SEM_MODELO


TRECHO = os.environ.get("CORTES_TRECHO_WAV")


@pytest.mark.lento
@pytest.mark.skipif(not TRECHO, reason="defina CORTES_TRECHO_WAV com um .wav de fala em português")
def test_transcreve_de_verdade_na_gpu() -> None:
    assert TRECHO is not None
    t0 = time.perf_counter()
    ps = transcrever(Path(TRECHO))
    print(f"\n{time.perf_counter() - t0:.1f} s, {len(ps)} palavras: {' '.join(p.texto for p in ps[:30])}")
    assert len(ps) > 100
    assert all(b.inicio >= a.inicio and b.fim >= b.inicio for a, b in zip(ps, ps[1:], strict=False))
