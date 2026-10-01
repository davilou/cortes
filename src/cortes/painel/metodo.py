"""Método do painel (spec painel §5): views aos 7 dias e relativo à mediana da conta. Puro."""
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import Literal

from cortes.painel.dados import ErroPainel
from cortes.painel.publicados import Etiquetas, Publicado
from cortes.painel.retratos import Retrato, VideoRetrato

Estado = Literal["medido", "estimado", "maturando"]
DIA_ALVO = 7
FOLGA_DIAS = 3   # retrato depois do dia 7 a mais que isto → valor "estimado"
BASE_MIN = 3     # Shorts medidos para a conta ter mediana de referência


@dataclass(frozen=True)
class Medida:
    estado: Estado
    views_7d: float | None


def views_7d(publicado_em: date, pontos: list[tuple[date, int]]) -> Medida:
    """Interpola as views no dia 7 a partir dos retratos (total acumulado em cada dia)."""
    alvo = publicado_em + timedelta(days=DIA_ALVO)
    serie = sorted([(publicado_em, 0), *((dia, v) for dia, v in pontos if dia >= publicado_em)])
    depois = [p for p in serie if p[0] >= alvo]
    if not depois:
        return Medida("maturando", None)
    d1, v1 = depois[0]
    d0, v0 = [p for p in serie if p[0] <= alvo][-1]
    valor = float(v1) if d1 == d0 else v0 + (v1 - v0) * (alvo - d0).days / (d1 - d0).days
    return Medida("estimado" if (d1 - alvo).days > FOLGA_DIAS else "medido", valor)


@dataclass(frozen=True)
class Linha:
    """Um Short como a tela o mostra: totais do último retrato + medida + ligação."""
    video_id: str
    conta: str
    titulo: str
    publicado_em: date
    etiquetas: Etiquetas | None   # None = ainda sem ligação
    corte: str | None
    medida: Medida
    rel: float | None             # views_7d ÷ mediana da conta; None sem base ou maturando
    views: int
    pct_media: float
    inscritos: int


def _base(valores: list[float]) -> float | None:
    if len(valores) < BASE_MIN:
        return None
    m = median(valores)
    return m if m > 0 else None   # mediana 0 → sem base (evita dividir por zero)


def _ligacao(vid: str, conta: str, pub: dict[str, Publicado]) -> Publicado | None:
    p = pub.get(vid)
    if p is not None and p.conta != conta:
        raise ErroPainel(f"vídeo {vid}: ligado à conta '{p.conta}' mas aparece nos retratos de '{conta}'")
    return p


def _linhas_da_conta(conta: str, rs: list[Retrato], pub: dict[str, Publicado]) -> list[Linha]:
    ultimo: dict[str, VideoRetrato] = {}
    pontos: dict[str, list[tuple[date, int]]] = {}
    for r in sorted(rs, key=lambda retrato: retrato.dia):
        for v in r.videos:
            ultimo[v.video_id] = v
            pontos.setdefault(v.video_id, []).append((r.dia, v.views))
    medidas = {vid: views_7d(v.publicado_em, pontos[vid]) for vid, v in ultimo.items()}
    base = _base([m.views_7d for m in medidas.values() if m.views_7d is not None])
    linhas = []
    for vid, v in ultimo.items():
        m = medidas[vid]
        p = _ligacao(vid, conta, pub)
        rel = m.views_7d / base if base is not None and m.views_7d is not None else None
        linhas.append(Linha(vid, conta, v.titulo, v.publicado_em, p.etiquetas if p else None,
                            p.corte if p else None, m, rel, v.views, v.pct_media, v.inscritos))
    return linhas


def _validar_contas_unicas(retratos: dict[str, list[Retrato]]) -> None:
    conta_do: dict[str, str] = {}
    for conta, rs in retratos.items():
        for r in rs:
            for v in r.videos:
                anterior = conta_do.setdefault(v.video_id, conta)
                if anterior != conta:
                    raise ErroPainel(
                        f"vídeo {v.video_id}: aparece nos retratos de '{anterior}' e de '{conta}'")


def montar_linhas(retratos: dict[str, list[Retrato]], publicados: list[Publicado]) -> list[Linha]:
    """Todos os Shorts dos retratos, do mais novo ao mais antigo. A base de cada conta usa todos
    os Shorts medidos dela, ligados ou não."""
    _validar_contas_unicas(retratos)
    pub = {p.video_id: p for p in publicados}
    linhas = [linha for conta, rs in retratos.items() for linha in _linhas_da_conta(conta, rs, pub)]
    return sorted(linhas, key=lambda linha: linha.publicado_em, reverse=True)
