"""Método do painel (spec painel §5): views aos 7 dias e relativo à mediana da conta. Puro."""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

Estado = Literal["medido", "estimado", "maturando"]
DIA_ALVO = 7
FOLGA_DIAS = 3   # retrato depois do dia 7 a mais que isto → valor "estimado"


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
