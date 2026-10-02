"""Transcrição local com faster-whisper na GPU → palavras com tempo (spec produção §4.2).

Benchmark em 2026-10-02 (20 min do PrimoCast 536, RTX 3090; diferença contra a legenda do
YouTube): openai-whisper large-v3 358 s (12,4%); faster-whisper large-v3 22,5 s (12,3%, frases
sem ponto); **large-v3-turbo int8_float16, lote 16: 11,1 s (~35 s por hora), 12,2%**, com boa
pontuação — o segmentador corta frases pela pontuação — e início e fim por palavra.

O áudio entra como array float32 de 16 kHz mono (`sinais.ler_wav_mono`): passar o caminho faz o
faster-whisper abrir com PyAV, e o PyAV instalado recusa o `metadata_errors` que ele passa.
O CTranslate2 precisa do cuBLAS do CUDA 12 e do cuDNN 9 (pacotes `nvidia-*-cu12`); no Windows
as DLLs deles só são achadas com as pastas `bin` registradas antes do import.
"""
import os
import sys
import sysconfig
import threading
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol

from cortes import sinais
from cortes.tipos import Palavra

MODELO = "large-v3-turbo"
COMPUTE = "int8_float16"   # pesos int8, contas em float16: a receita medida no benchmark
BATCH = 16                 # trechos por lote no BatchedInferencePipeline
IDIOMA = "pt"
PASTAS_DLL = ("nvidia/cublas/bin", "nvidia/cudnn/bin")
SEM_MEMORIA = ("placa de vídeo sem memória para transcrever (feche o ComfyUI ou outro programa "
               "que usa a GPU e tente de novo)")
_SINAIS_OOM = ("out of memory", "cublas_status_alloc_failed")


class ErroTranscricao(RuntimeError):
    pass


class PalavraWhisper(Protocol):
    @property
    def word(self) -> str: ...
    @property
    def start(self) -> float: ...
    @property
    def end(self) -> float: ...


class SegmentoWhisper(Protocol):
    @property
    def words(self) -> Sequence[PalavraWhisper] | None: ...


def palavras_dos_segmentos(segmentos: Iterable[SegmentoWhisper]) -> list[Palavra]:
    """Texto sem espaço nas pontas, palavra vazia descartada, tempos em ms (3 casas) e `float`
    do Python (o faster-whisper devolve np.float64). O início nunca volta para trás da palavra
    anterior e o fim nunca fica antes do início."""
    palavras: list[Palavra] = []
    for seg in segmentos:
        for w in seg.words or ():
            texto = w.word.strip()
            if not texto:
                continue
            inicio = round(max(float(w.start), palavras[-1].inicio if palavras else 0.0), 3)
            palavras.append(Palavra(texto, inicio, max(round(float(w.end), 3), inicio)))
    if not palavras:
        raise ErroTranscricao("a transcrição local não achou nenhuma palavra no áudio")
    return palavras


def pastas_dll(site: Path) -> list[Path]:
    faltando = [sub for sub in PASTAS_DLL if not (site / sub).is_dir()]
    if faltando:
        raise ErroTranscricao(f"faltam as DLLs da GPU em {site} ({', '.join(faltando)}): "
                              "instale nvidia-cublas-cu12 e nvidia-cudnn-cu12")
    return [site / sub for sub in PASTAS_DLL]


def sem_memoria(ex: BaseException) -> bool:
    msg = str(ex).lower()
    return any(s in msg for s in _SINAIS_OOM)


def _registrar_dlls() -> None:
    if sys.platform != "win32":
        return
    for pasta in pastas_dll(Path(sysconfig.get_paths()["purelib"])):
        os.add_dll_directory(str(pasta))
        os.environ["PATH"] = str(pasta) + os.pathsep + os.environ["PATH"]


_TRAVA = threading.Lock()
_pipeline: Any = None   # BatchedInferencePipeline (faster-whisper não tem tipos), carregado uma vez


def _carregar() -> Any:
    global _pipeline
    if _pipeline is None:
        _registrar_dlls()
        from faster_whisper import BatchedInferencePipeline, WhisperModel

        _pipeline = BatchedInferencePipeline(model=WhisperModel(MODELO, device="cuda", compute_type=COMPUTE))
    return _pipeline


def transcrever(audio: Path) -> list[Palavra]:
    """Modelo carregado na primeira chamada e mantido no processo. A trava
    serializa carga e transcrição: duas ao mesmo tempo disputariam a memória da placa."""
    amostras = sinais.ler_wav_mono(audio)
    with _TRAVA:
        try:
            segmentos, _ = _carregar().transcribe(amostras, language=IDIOMA, batch_size=BATCH,
                                                  word_timestamps=True)
            return palavras_dos_segmentos(segmentos)   # gerador: a GPU trabalha aqui, na iteração
        except RuntimeError as ex:
            if isinstance(ex, ErroTranscricao) or not sem_memoria(ex):
                raise
            raise ErroTranscricao(SEM_MEMORIA) from ex
