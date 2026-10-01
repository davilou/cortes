"""Retrato = export do Studio de uma conta num dia, com o total acumulado de cada vídeo (spec painel §3.4)."""
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from cortes.episodio import ler_json, salvar_json
from cortes.painel.dados import VIDEO_ID, ErroPainel, campo_texto


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


def _numero_json(d: Any, campo: str) -> float:
    v = d[campo]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ErroPainel(f"campo '{campo}' não é número")
    return float(v)


def _inteiro_json(d: Any, campo: str) -> int:
    v = d[campo]
    if isinstance(v, bool) or not isinstance(v, int):
        raise ErroPainel(f"campo '{campo}' não é inteiro")
    return v


def _video(v: Any) -> VideoRetrato:
    if not isinstance(v, dict):
        raise ErroPainel("vídeo não é um mapa")
    vid = campo_texto(v, "video_id")
    if not VIDEO_ID.fullmatch(vid):
        raise ErroPainel(f"video_id inválido: {vid!r}")
    return VideoRetrato(
        video_id=vid,
        titulo=campo_texto(v, "titulo"),
        publicado_em=date.fromisoformat(campo_texto(v, "publicado_em")),
        duracao_s=_numero_json(v, "duracao_s"),
        views=_inteiro_json(v, "views"),
        pct_media=_numero_json(v, "pct_media"),
        duracao_media_s=_numero_json(v, "duracao_media_s"),
        inscritos=_inteiro_json(v, "inscritos"),
    )


def _ler(arquivo: Path) -> Retrato:
    try:
        d = ler_json(arquivo)
        if not isinstance(d, dict):
            raise ErroPainel("não é um mapa")
        videos = tuple(_video(v) for v in d["videos"])
        r = Retrato(campo_texto(d, "conta"), datetime.fromisoformat(campo_texto(d, "coletado_em")), videos)
    except (KeyError, TypeError, ValueError, ErroPainel) as e:
        raise ErroPainel(f"{arquivo}: retrato inválido ({e!r})") from e
    if r.conta != arquivo.parent.name or r.dia.isoformat() != arquivo.stem:
        raise ErroPainel(f"{arquivo}: retrato inválido (conta/dia não casam com a pasta e o nome do arquivo)")
    return r


def ler_retratos(pasta: Path) -> dict[str, list[Retrato]]:
    """Retratos por conta, do mais antigo ao mais novo."""
    por_conta: dict[str, list[Retrato]] = {}
    for arquivo in sorted(pasta.glob("*/*.json")):
        r = _ler(arquivo)
        por_conta.setdefault(r.conta, []).append(r)
    for lista in por_conta.values():
        lista.sort(key=lambda r: r.coletado_em)
    return por_conta
