"""CSV do export do Studio (modo avançado, dimensão VIDEO) → vídeos do retrato.

O cabeçalho vem no idioma da conta; a data de publicação vem em inglês ("Aug 11, 2026") mesmo
com cabeçalho em português (conferido em export real de 2026-08).
"""
import csv
import io
import math
import zipfile
from datetime import date
from pathlib import Path

from cortes.painel.dados import VIDEO_ID, ErroPainel
from cortes.painel.retratos import VideoRetrato

# (campo, nomes aceitos, casamento exato?). "Duração" é exato: "Duração média…" começa igual.
COLUNAS: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    ("video_id", ("Conteúdo", "Content"), True),
    ("titulo", ("Título do vídeo", "Video title"), True),
    ("publicado_em", ("Horário de publicação", "Video publish time"), False),
    ("duracao_s", ("Duração", "Duration"), True),
    ("views", ("Visualizações", "Views"), True),
    ("duracao_media_s", ("Duração média da visualização", "Average view duration"), False),
    ("pct_media", ("Porcentagem visualizada média", "Average percentage viewed"), False),
    ("inscritos", ("Inscritos", "Subscribers"), True),
)
_MESES = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def _indices(cabecalho: list[str]) -> dict[str, int]:
    idx: dict[str, int] = {}
    for campo, nomes, exato in COLUNAS:
        achados = [i for i, c in enumerate(cabecalho) if (c in nomes if exato else c.startswith(nomes))]
        if not achados:
            raise ErroPainel(f"export do Studio sem a coluna '{nomes[0]}' (colunas: {cabecalho})")
        idx[campo] = achados[0]
    return idx


def _data(texto: str) -> date:
    try:
        mes, dia, ano = texto.replace(",", "").split()
        return date(int(ano), _MESES[mes[:3]], int(dia))
    except (ValueError, KeyError) as e:
        raise ErroPainel(f"data de publicação em formato desconhecido: '{texto}'") from e


def _numero(video_id: str, campo: str, texto: str) -> float:
    try:
        return float(texto)
    except ValueError as e:
        raise ErroPainel(f"vídeo {video_id}: campo '{campo}' não é número ('{texto}')") from e


def _inteiro(video_id: str, campo: str, texto: str) -> int:
    n = _numero(video_id, campo, texto)
    if not math.isfinite(n) or n != int(n):
        raise ErroPainel(f"vídeo {video_id}: campo '{campo}' não é inteiro ('{texto}')")
    return int(n)


def _segundos(video_id: str, texto: str) -> float:
    total = 0.0
    for parte in texto.split(":"):
        total = total * 60 + _numero(video_id, "duracao_media_s", parte)
    return total


def _video(n: int, cel: dict[str, str]) -> VideoRetrato:
    vid = cel["video_id"]
    if not vid:
        raise ErroPainel(f"linha {n}: id do vídeo vazio")
    if not VIDEO_ID.fullmatch(vid):
        raise ErroPainel(f"linha {n}: id do vídeo fora do padrão de 11 caracteres: {vid!r}")
    if not cel["views"]:
        raise ErroPainel(f"vídeo {vid}: views vazio")
    views = _inteiro(vid, "views", cel["views"])

    def valor(campo: str) -> str:
        if cel[campo]:
            return cel[campo]
        if views == 0:
            return "0"  # vídeo sem view nenhuma: o Studio deixa as médias em branco
        raise ErroPainel(f"vídeo {vid}: '{campo}' vazio com {views} views")

    return VideoRetrato(
        video_id=vid, titulo=cel["titulo"], publicado_em=_data(cel["publicado_em"]),
        duracao_s=_numero(vid, "duracao_s", valor("duracao_s")), views=views,
        pct_media=_numero(vid, "pct_media", valor("pct_media")),
        duracao_media_s=_segundos(vid, valor("duracao_media_s")),
        inscritos=_inteiro(vid, "inscritos", valor("inscritos")),
    )


def ler_tabela(texto: str) -> list[VideoRetrato]:
    linhas = list(csv.reader(io.StringIO(texto)))
    if not linhas:
        raise ErroPainel("export do Studio vazio")
    cabecalho = [c.lstrip("﻿").strip() for c in linhas[0]]
    idx = _indices(cabecalho)
    videos: list[VideoRetrato] = []
    for n, linha in enumerate(linhas[1:], start=2):
        if not any(c.strip() for c in linha):
            continue
        if linha[0].strip() in ("Total", "Totals"):
            continue
        if len(linha) < len(cabecalho):
            raise ErroPainel(f"linha {n}: {len(linha)} colunas, o cabeçalho tem {len(cabecalho)}")
        cel = {campo: linha[i].strip() for campo, i in idx.items()}
        videos.append(_video(n, cel))
    return videos


def texto_do_zip(caminho: Path) -> str:
    with zipfile.ZipFile(caminho) as z:
        nome = next((n for n in z.namelist() if n.startswith(("Dados da tabela", "Table data"))), None)
        if nome is None:
            raise ErroPainel(f"{caminho}: zip sem a tabela por vídeo ({z.namelist()})")
        return z.read(nome).decode("utf-8-sig")
