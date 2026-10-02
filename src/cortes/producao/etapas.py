"""As 4 etapas do episódio no painel: vídeo, legenda do YouTube, sinais, momentos.

Cada etapa grava seu arquivo e pula se ele já existe (mesmo padrão do `cortes detectar`).
O `cortes detectar` do terminal segue com Whisper; aqui a transcrição é a legenda do YouTube.
"""
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from cortes import ingestao, sinais
from cortes.detector import ChamarLLM, chamar_llm_real, detectar
from cortes.episodio import ler_json, salvar_json
from cortes.perfil import carregar_perfil
from cortes.producao import legenda_yt
from cortes.producao.estado import ETAPAS, ErroProducao, EstadoEpisodio
from cortes.segmentacao import frases
from cortes.tipos import Palavra


@dataclass(frozen=True)
class Dependencias:
    baixar_video: Callable[[str, Path], None] = ingestao.baixar
    extrair_audio: Callable[[Path], None] = ingestao.extrair_audio
    baixar_legenda: Callable[[str, Path], Path] = legenda_yt.baixar
    chamar_llm: ChamarLLM = chamar_llm_real
    modelo: str = "sonnet"


def _video(pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    if not (pasta / "video.mp4").exists():
        dep.baixar_video(e.url, pasta)
    if not (pasta / "audio.wav").exists():
        dep.extrair_audio(pasta)


def _legenda(pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    if (pasta / "palavras.json").exists():
        return
    arquivo = dep.baixar_legenda(e.url, pasta)
    palavras = legenda_yt.palavras_do_json3(ler_json(arquivo))
    salvar_json(pasta / "palavras.json", [asdict(p) for p in palavras])


def _sinais(pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    if (pasta / "sinais.json").exists():
        return
    energia = sinais.energia_por_janela(sinais.ler_wav_mono(pasta / "audio.wav"))
    salvar_json(pasta / "sinais.json", {"janela_s": sinais.JANELA_S, "energia": energia})


def _momentos(pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    if (pasta / "candidatos.json").exists():
        return
    nicho = raiz / "nichos" / e.nicho
    if not (nicho / "perfil.yaml").exists():
        raise ErroProducao(f"nicho '{e.nicho}' não existe: falta {nicho / 'perfil.yaml'}")
    fs = frases([Palavra(**p) for p in ler_json(pasta / "palavras.json")])
    salvar_json(pasta / "frases.json", [asdict(f) for f in fs])
    aceitos, descartes = detectar(fs, ler_json(pasta / "sinais.json")["energia"], carregar_perfil(nicho),
                                  dep.modelo, dep.chamar_llm)
    salvar_json(pasta / "descartados.json", descartes)
    salvar_json(pasta / "candidatos.json", [asdict(c) for c in aceitos])


_ETAPAS = {"video": _video, "legenda": _legenda, "sinais": _sinais, "momentos": _momentos}


def rodar_etapa(nome: str, pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    if nome not in _ETAPAS:
        raise ErroProducao(f"etapa '{nome}' não existe; use uma de {ETAPAS}")
    _ETAPAS[nome](pasta, e, raiz, dep)
