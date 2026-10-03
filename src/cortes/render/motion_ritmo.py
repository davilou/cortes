"""f3 Motion, o ritmo das cenas (plano 2026-10-03-motion). Puro.

As regras vão no prompt e são aplicadas de novo aqui: o LLM pode errar a conta, e painel atrás de
painel sem o rosto voltar, ou motion tapando quase todo o Short, estraga o corte.
- a `capa` (gancho) só uma, de 0 a 2,2 s; nenhuma outra cena no primeiro GANCHO_S, com o rosto;
- cada cena de DUR_MIN_S a DUR_MAX_S (o tempo já vem cortado assim de render/motion.py; a que ficou
  curta é a que bateu no fim da fala);
- pelo menos ROSTO_MIN_S de rosto em tela cheia entre uma cena e a próxima;
- motion somado ≤ FRACAO_MAX da duração do Short: passou, saem as últimas.
"""
from dataclasses import dataclass
from typing import Any

from cortes.render.motion_params import Params, params_json

GANCHO_S = 1.0
DUR_MIN_S = 1.5
DUR_MAX_S = 4.0
ROSTO_MIN_S = 1.0
FRACAO_MAX = 0.7
_EPS = 1e-6


@dataclass(frozen=True)
class Bruta:
    """Cena que passou nos parâmetros e nos números; falta o ritmo."""
    componente: str
    inicio: float
    fim: float
    params: Params
    batidas: tuple[float, ...]


@dataclass(frozen=True)
class Descartada:
    componente: str
    inicio: float
    fim: float
    params: Any     # como o LLM mandou (pode ser o que não passou na validação)
    motivo: str


def _fora(b: Bruta, motivo: str) -> Descartada:
    return Descartada(b.componente, b.inicio, b.fim, params_json(b.params), motivo)


def _motivo(b: Bruta, ficam: list[Bruta]) -> str | None:
    """Por que a cena não cabe depois das que já ficaram (None = cabe)."""
    if b.componente == "capa" and any(f.componente == "capa" for f in ficam):
        return "ritmo: só uma capa, no gancho"
    if b.componente != "capa" and b.inicio < GANCHO_S - _EPS:
        return f"ritmo: começa no gancho (antes de {GANCHO_S:.1f} s), que é do rosto"
    if b.fim - b.inicio < DUR_MIN_S - _EPS and b.componente != "capa":
        return f"ritmo: só {b.fim - b.inicio:.1f} s até o fim da fala (mínimo {DUR_MIN_S:.1f} s)"
    if ficam and b.inicio - ficam[-1].fim < ROSTO_MIN_S - _EPS:
        return (f"ritmo: menos de {ROSTO_MIN_S:.1f} s de rosto depois da cena anterior "
                f"({ficam[-1].componente}, até {ficam[-1].fim:.2f} s)")
    return None


def ritmo(cenas: list[Bruta], dur: float) -> tuple[list[Bruta], list[Descartada]]:
    """As cenas que ficam, em ordem, e as que saem, com o motivo."""
    ficam: list[Bruta] = []
    fora: list[Descartada] = []
    for b in sorted(cenas, key=lambda b: (b.inicio, b.componente != "capa")):
        motivo = _motivo(b, ficam)
        if motivo is None:
            ficam.append(b)
        else:
            fora.append(_fora(b, motivo))
    while sum(b.fim - b.inicio for b in ficam) > FRACAO_MAX * dur + _EPS:
        b = ficam.pop()
        fora.append(_fora(b, f"ritmo: motion passaria de {FRACAO_MAX:.0%} do Short"))
    return ficam, fora
