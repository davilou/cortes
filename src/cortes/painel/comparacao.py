"""Comparação entre grupos de Shorts (spec painel §5.3–5.4). Puro.

Mediana, não média: views de Short têm cauda longa e um viral puxa a média do grupo inteiro.
"""
from dataclasses import dataclass
from statistics import median
from typing import Literal

from cortes.painel.dados import ErroPainel
from cortes.painel.metodo import Linha
from cortes.painel.publicados import Etiquetas

Dimensao = Literal["formato", "conta", "tema", "podcast"]
DIMENSOES: tuple[Dimensao, ...] = ("formato", "conta", "tema", "podcast")
PISTA_N = 5


@dataclass(frozen=True)
class Grupo:
    chave: str
    n: int
    rel_mediana: float
    pct_mediana: float
    insc_por_mil: float | None
    pista: bool
    rels: tuple[float, ...]
    video_ids: tuple[str, ...]


@dataclass(frozen=True)
class Celula:
    formato: str
    conta: str
    n: int
    rel_mediana: float


@dataclass(frozen=True)
class Confusao:
    """Formato que só rodou numa conta (ou conta com um formato só): o número mistura os dois."""
    tipo: Literal["formato", "conta"]
    chave: str
    unico: str


def dimensao(texto: str) -> Dimensao:
    for d in DIMENSOES:
        if d == texto:
            return d
    raise ErroPainel(f"dimensão '{texto}' inválida; use uma de {DIMENSOES}")


def _comparaveis(linhas: list[Linha]) -> list[tuple[Linha, Etiquetas, float]]:
    return [(linha, linha.etiquetas, linha.rel) for linha in linhas
            if linha.etiquetas is not None and linha.rel is not None]


def comparaveis(linhas: list[Linha]) -> int:
    return len(_comparaveis(linhas))


def _chaves(etiquetas: Etiquetas, conta: str, dim: Dimensao) -> list[str]:
    return {"formato": [etiquetas.formato], "conta": [conta], "tema": list(etiquetas.temas),
            "podcast": [etiquetas.podcast]}[dim]


def _grupo(chave: str, itens: list[tuple[Linha, float]]) -> Grupo:
    views = sum(linha.views for linha, _ in itens)
    inscritos = sum(linha.inscritos for linha, _ in itens)
    rels = sorted(rel for _, rel in itens)
    return Grupo(chave, len(itens), median(rels), median(linha.pct_media for linha, _ in itens),
                 inscritos / views * 1000 if views else None, len(itens) < PISTA_N,
                 tuple(rels), tuple(linha.video_id for linha, _ in itens))


def grupos(linhas: list[Linha], dim: Dimensao) -> list[Grupo]:
    """Só Shorts ligados e com relativo. Em 'tema', um Short entra em todos os seus temas."""
    por_chave: dict[str, list[tuple[Linha, float]]] = {}
    for linha, etiquetas, rel in _comparaveis(linhas):
        for chave in _chaves(etiquetas, linha.conta, dim):
            por_chave.setdefault(chave, []).append((linha, rel))
    return sorted((_grupo(k, v) for k, v in por_chave.items()), key=lambda g: (-g.rel_mediana, g.chave))


def matriz(linhas: list[Linha]) -> list[Celula]:
    por_celula: dict[tuple[str, str], list[float]] = {}
    for linha, etiquetas, rel in _comparaveis(linhas):
        por_celula.setdefault((etiquetas.formato, linha.conta), []).append(rel)
    return [Celula(f, c, len(rels), median(rels)) for (f, c), rels in sorted(por_celula.items())]


def confusoes(linhas: list[Linha]) -> list[Confusao]:
    contas_do_formato: dict[str, set[str]] = {}
    formatos_da_conta: dict[str, set[str]] = {}
    for cel in matriz(linhas):
        contas_do_formato.setdefault(cel.formato, set()).add(cel.conta)
        formatos_da_conta.setdefault(cel.conta, set()).add(cel.formato)
    formato_unico = [Confusao("formato", f, next(iter(cs)))
                     for f, cs in sorted(contas_do_formato.items()) if len(cs) == 1]
    conta_unica = [Confusao("conta", c, next(iter(fs)))
                   for c, fs in sorted(formatos_da_conta.items()) if len(fs) == 1]
    return formato_unico + conta_unica
