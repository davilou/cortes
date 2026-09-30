"""Tipos compartilhados entre as etapas do pipeline."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Palavra:
    texto: str
    inicio: float
    fim: float


@dataclass(frozen=True)
class Frase:
    indice: int
    texto: str
    inicio: float
    fim: float


@dataclass(frozen=True)
class Candidato:
    frase_inicio: int
    frase_fim: int
    inicio: float
    fim: float
    notas: dict[str, int]
    bonus: list[str]
    penalidades: list[str]
    justificativa: str
    titulo: str
    nota_final: float
