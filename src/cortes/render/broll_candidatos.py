"""f4 B-roll, os candidatos de uma deixa: vídeos do YouTube e, só na deixa literal, fotos
(plano 2026-10-03-broll-automatico, Task 3).

O YouTube é consultado em série — busca e um trecho por vez, nunca em paralelo — com até
`broll_video.MAX_CANDIDATOS` vídeos por deixa. Uma falha de busca ou um bloqueio (429, "não é um
robô") marca o YouTube como fora nesta rodada: as deixas seguintes nem tentam, ficam transitórias,
e nada é repetido em laço (spec §8: o IP já foi bloqueado uma vez). A foto cobre a deixa literal.
"""
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cortes.render.broll_folha import LinhaFolha, Quadros
from cortes.render.broll_video import (
    MAX_CANDIDATOS,
    VideoCandidato,
    baixar_trecho,
    buscar_videos,
    extrair_quadros,
)
from cortes.render.ilustracao import Deixa
from cortes.render.ilustracao_imagens import (
    BuscaImagens,
    Candidata,
    ErroBusca,
    baixar_candidatas,
    buscar,
    falha_temporaria,
)
from cortes.render.processo import ErroRender, Rodar

N_FOTOS = 2   # por deixa literal; com 2 vídeos, a linha da folha fica com 4 tiles


@dataclass(frozen=True)
class DepCandidatos:
    ddgs: Callable[[], BuscaImagens]
    rodar_download: Rodar      # download das fotos, com prazo curto próprio
    rodar_busca_video: Rodar   # busca no YouTube (yt-dlp), com prazo próprio
    rodar_video: Rodar         # trecho do YouTube e ffmpeg dos quadros e da foto em tela cheia


@dataclass
class YouTube:
    """O estado do YouTube numa rodada da etapa: `fora` guarda a primeira falha de busca ou o
    bloqueio, e a partir dela nenhuma deixa consulta o YouTube de novo."""
    fora: str | None = None


@dataclass(frozen=True)
class VideoBaixado:
    candidato: VideoCandidato
    trecho: Path       # `D<k>-v<j>.mp4`, já em 1080×1920
    quadros: Quadros   # `D<k>-v<j>-q1.jpg` a `-q3.jpg`, para a folha


@dataclass(frozen=True)
class Achadas:
    """O que a busca e o download deram para uma deixa."""
    videos: list[VideoBaixado]
    fotos: list[tuple[Candidata, Path]]
    falhas: list[str]
    motivo: str          # por que ficou sem candidato ("" se algum baixou)
    transitorio: bool    # uma parte falhou de um jeito que outra tentativa pode resolver

    def linha(self, k: int, deixa: Deixa) -> LinhaFolha:
        return LinhaFolha(k, deixa, tuple(v.quadros for v in self.videos),
                          tuple(p for _, p in self.fotos))


def _um_video(k: int, j: int, c: VideoCandidato, pasta: Path, dep: DepCandidatos) -> VideoBaixado:
    trecho = pasta / f"D{k}-v{j}.mp4"
    baixar_trecho(c, trecho, dep.rodar_video)
    return VideoBaixado(c, trecho, extrair_quadros(trecho, pasta / f"D{k}-v{j}", dep.rodar_video))


def _videos(k: int, deixa: Deixa, pasta: Path, dep: DepCandidatos,
            yt: YouTube) -> tuple[list[VideoBaixado], list[str], bool]:
    """(baixados, falhas, transitório). Em série; o bloqueio para tudo, inclusive as próximas deixas."""
    if yt.fora is not None:
        return [], [f"vídeo: não buscado, o YouTube falhou antes nesta rodada ({yt.fora})"], True
    try:
        cands = buscar_videos(deixa.busca, MAX_CANDIDATOS, dep.rodar_busca_video)
    except ErroBusca as e:
        yt.fora = str(e)
        return [], [f"vídeo: {e}"], True
    if not cands:
        return [], [f"vídeo: a busca '{deixa.busca}' não achou vídeo de 20 s a 20 min"], False
    baixados: list[VideoBaixado] = []
    falhas: list[str] = []
    temporaria = False
    for j, c in enumerate(cands, start=1):
        try:
            baixados.append(_um_video(k, j, c, pasta, dep))
        except ErroBusca as e:
            yt.fora = str(e)
            falhas.append(f"vídeo {c.url}: {e}")
            return baixados, falhas, not baixados
        except ErroRender as e:
            falhas.append(f"vídeo {c.url}: {e}")
            temporaria = temporaria or falha_temporaria(str(e))
    return baixados, falhas, temporaria and not baixados


def _fotos(k: int, deixa: Deixa, pasta: Path,
           dep: DepCandidatos) -> tuple[list[tuple[Candidata, Path]], list[str], bool]:
    """(baixadas, falhas, transitório) da foto de reserva; acontecimento não tem foto."""
    if deixa.tipo != "literal":
        return [], [], False
    try:
        cands = buscar(deixa.busca, N_FOTOS, dep.ddgs())
    except ErroBusca as e:
        return [], [f"foto: {e}"], True
    if not cands:
        return [], [f"foto: a busca '{deixa.busca}' não achou foto do tamanho mínimo"], False
    baixadas, falhas = baixar_candidatas(cands, pasta, f"D{k}", dep.rodar_download)
    temporaria = not baixadas and any(falha_temporaria(f) for f in falhas)
    return baixadas, [f"foto: {f}" for f in falhas], temporaria


def achar(k: int, deixa: Deixa, pasta: Path, dep: DepCandidatos, yt: YouTube) -> Achadas:
    """Busca que falha é motivo, não exceção: a deixa fica sem visual com a causa. Erro de ffmpeg
    nos quadros de um trecho baixado também é só a falha daquele candidato."""
    videos, falhas_v, temp_v = _videos(k, deixa, pasta, dep, yt)
    fotos, falhas_f, temp_f = _fotos(k, deixa, pasta, dep)
    falhas = falhas_v + falhas_f
    sem_foto = " (acontecimento: sem foto de reserva)" if deixa.tipo != "literal" else ""
    motivo = "" if videos or fotos else f"sem visual: {'; '.join(falhas)}{sem_foto}"
    return Achadas(videos, fotos, falhas, motivo, temp_v or temp_f)
