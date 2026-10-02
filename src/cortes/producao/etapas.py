"""As 5 etapas do episódio no painel: vídeo, transcrição local (etapa "legenda"), sinais,
momentos, render.

Cada etapa grava seu arquivo e pula se ele já existe (mesmo padrão do `cortes detectar`).
A transcrição é local, com faster-whisper (`transcricao_local`); o `cortes detectar` do
terminal segue com o openai-whisper. A etapa mantém o nome "legenda" porque é a chave dela nos
`estado.json` já gravados.
"""
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from cortes import ingestao, sinais
from cortes.detector import ChamarLLM, chamar_llm_real, detectar
from cortes.episodio import ler_json, salvar_json
from cortes.perfil import carregar_perfil
from cortes.producao import transcricao_local
from cortes.producao.estado import ETAPAS, ErroProducao, EstadoEpisodio
from cortes.producao.render import rodar_render
from cortes.render.pipeline import DepRender
from cortes.segmentacao import frases
from cortes.tipos import Palavra


@dataclass(frozen=True)
class Dependencias:
    baixar_video: Callable[[str, Path], None] = ingestao.baixar
    extrair_audio: Callable[[Path], None] = ingestao.extrair_audio
    transcrever: Callable[[Path], list[Palavra]] = transcricao_local.transcrever
    chamar_llm: ChamarLLM = chamar_llm_real
    modelo: str = "sonnet"
    render: DepRender | None = None   # o servidor monta com a configuração verificada na subida


def _video(pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    """`meta.json` é o marcador de download feito: `ingestao.baixar` só o grava depois de
    validar a altura, então `video.mp4` sozinho (queda ou altura rejeitada) não basta."""
    if not (pasta / "meta.json").exists():
        dep.baixar_video(e.url, pasta)
    if not (pasta / "audio.wav").exists():
        dep.extrair_audio(pasta)


def _legenda(pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    if (pasta / "palavras.json").exists():
        return
    palavras = dep.transcrever(pasta / "audio.wav")
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


def _render(pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    if dep.render is None:
        raise ErroProducao("render sem configuração: o servidor não montou Dependencias.render")
    rodar_render(pasta, e, raiz, dep.render)


_ETAPAS = {"video": _video, "legenda": _legenda, "sinais": _sinais, "momentos": _momentos, "render": _render}


def rodar_etapa(nome: str, pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    if nome not in _ETAPAS:
        raise ErroProducao(f"etapa '{nome}' não existe; use uma de {ETAPAS}")
    _ETAPAS[nome](pasta, e, raiz, dep)
