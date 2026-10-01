"""Retrato = export do Studio de uma conta num dia, com o total acumulado de cada vídeo (spec painel §3.4)."""
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from cortes.episodio import ler_json, salvar_json
from cortes.painel.dados import ErroPainel


@dataclass(frozen=True)
class VideoRetrato:
    video_id: str
    titulo: str
    publicado_em: date
    duracao_s: float
    views: int
    pct_media: float
    duracao_media_s: float
    inscritos: int


@dataclass(frozen=True)
class Retrato:
    conta: str
    coletado_em: datetime
    videos: tuple[VideoRetrato, ...]

    @property
    def dia(self) -> date:
        return self.coletado_em.date()


def salvar_retrato(pasta: Path, r: Retrato) -> Path:
    """Um retrato por conta por dia: atualizar de novo no mesmo dia sobrescreve."""
    destino = pasta / r.conta / f"{r.dia.isoformat()}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    salvar_json(destino, {
        "conta": r.conta,
        "coletado_em": r.coletado_em.isoformat(timespec="seconds"),
        "videos": [{**asdict(v), "publicado_em": v.publicado_em.isoformat()} for v in r.videos],
    })
    return destino


def _texto(d: Any, campo: str) -> str:
    v = d[campo]
    if not isinstance(v, str):
        raise ErroPainel(f"campo '{campo}' não é texto")
    return v


def _numero(d: Any, campo: str) -> float:
    v = d[campo]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ErroPainel(f"campo '{campo}' não é número")
    return float(v)


def _inteiro(d: Any, campo: str) -> int:
    v = d[campo]
    if isinstance(v, bool) or not isinstance(v, int):
        raise ErroPainel(f"campo '{campo}' não é inteiro")
    return v


def _video(v: Any) -> VideoRetrato:
    if not isinstance(v, dict):
        raise ErroPainel("vídeo não é um mapa")
    return VideoRetrato(
        video_id=_texto(v, "video_id"),
        titulo=_texto(v, "titulo"),
        publicado_em=date.fromisoformat(_texto(v, "publicado_em")),
        duracao_s=_numero(v, "duracao_s"),
        views=_inteiro(v, "views"),
        pct_media=_numero(v, "pct_media"),
        duracao_media_s=_numero(v, "duracao_media_s"),
        inscritos=_inteiro(v, "inscritos"),
    )


def _ler(arquivo: Path) -> Retrato:
    d = ler_json(arquivo)
    try:
        if not isinstance(d, dict):
            raise ErroPainel("não é um mapa")
        videos = tuple(_video(v) for v in d["videos"])
        return Retrato(_texto(d, "conta"), datetime.fromisoformat(_texto(d, "coletado_em")), videos)
    except (KeyError, TypeError, ValueError, ErroPainel) as e:
        raise ErroPainel(f"{arquivo}: retrato inválido ({e!r})") from e


def ler_retratos(pasta: Path) -> dict[str, list[Retrato]]:
    """Retratos por conta, do mais antigo ao mais novo."""
    por_conta: dict[str, list[Retrato]] = {}
    for arquivo in sorted(pasta.glob("*/*.json")):
        r = _ler(arquivo)
        por_conta.setdefault(r.conta, []).append(r)
    for lista in por_conta.values():
        lista.sort(key=lambda r: r.coletado_em)
    return por_conta
