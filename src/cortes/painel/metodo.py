"""Método do painel (spec painel §5): views aos 7 dias e relativo à mediana da conta. Puro."""
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import Literal

from cortes.painel.dados import ErroPainel
from cortes.painel.publicados import Etiquetas, Publicado
from cortes.painel.retratos import Retrato, VideoRetrato

Estado = Literal["medido", "estimado", "maturando", "sem_dado"]
DIA_ALVO = 7
FOLGA_DIAS = 3              # retrato depois do dia 7 a mais que isto → valor "estimado"
LIMITE_ESTIMADO_DIAS = 7    # ... e a mais que isto → "sem_dado": a reta desde 0 subestimaria
BASE_MIN = 3                # Shorts medidos para a conta ter mediana de referência
DURACAO_MAX_SHORT_S = 180   # Shorts vão até 3 min; vídeo mais longo não entra no painel


@dataclass(frozen=True)
class Medida:
    estado: Estado
    views_7d: float | None


def views_7d(publicado_em: date, pontos: list[tuple[date, int]]) -> Medida:
    """Interpola as views no dia 7 a partir dos retratos (total acumulado em cada dia).

    Primeiro retrato a mais de LIMITE_ESTIMADO_DIAS depois do dia 7 → "sem_dado": as views de
    Short se concentram nos primeiros dias, e a reta desde 0 sobre uma lacuna longa as subestima
    (decisão de 2026-10-01, spec painel §5.1)."""
    alvo = publicado_em + timedelta(days=DIA_ALVO)
    serie = sorted([(publicado_em, 0), *((dia, v) for dia, v in pontos if dia >= publicado_em)])
    depois = [p for p in serie if p[0] >= alvo]
    if not depois:
        return Medida("maturando", None)
    d1, v1 = depois[0]
    atraso = (d1 - alvo).days
    if atraso > LIMITE_ESTIMADO_DIAS:
        return Medida("sem_dado", None)
    d0, v0 = [p for p in serie if p[0] <= alvo][-1]
    valor = float(v1) if d1 == d0 else v0 + (v1 - v0) * (alvo - d0).days / (d1 - d0).days
    return Medida("estimado" if atraso > FOLGA_DIAS else "medido", valor)


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
    rel: float | None             # views_7d ÷ mediana da conta; None sem base, maturando ou sem_dado
    views: int
    pct_media: float
    inscritos: int


def _base(valores: list[float]) -> float | None:
    if len(valores) < BASE_MIN:
        return None
    m = median(valores)
    return m if m > 0 else None   # mediana 0 → sem base (evita dividir por zero)


@dataclass(frozen=True)
class Base:
    """A referência de uma conta: mediana das views_7d dos seus Shorts com medida."""
    mediana_7d: float | None   # None com menos de BASE_MIN medidos (ou mediana 0)
    medidos: int               # Shorts com views_7d (medido ou estimado), ligados ou não


def bases(linhas: list[Linha], contas: Iterable[str]) -> dict[str, Base]:
    """Base de cada conta pedida — a mesma regra que montar_linhas usa para o relativo."""
    valores: dict[str, list[float]] = {c: [] for c in contas}
    for linha in linhas:
        if linha.conta in valores and linha.medida.views_7d is not None:
            valores[linha.conta].append(linha.medida.views_7d)
    return {c: Base(_base(vs), len(vs)) for c, vs in valores.items()}


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
            if v.duracao_s > DURACAO_MAX_SHORT_S:
                continue
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
    """Todos os Shorts dos retratos (vídeo acima de DURACAO_MAX_SHORT_S fica fora), do mais novo
    ao mais antigo. A base de cada conta usa todos os Shorts medidos dela, ligados ou não."""
    _validar_contas_unicas(retratos)
    pub = {p.video_id: p for p in publicados}
    linhas = [linha for conta, rs in retratos.items() for linha in _linhas_da_conta(conta, rs, pub)]
    return sorted(linhas, key=lambda linha: linha.publicado_em, reverse=True)
