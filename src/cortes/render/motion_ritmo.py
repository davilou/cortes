"""f3 Motion, o ritmo das cenas (plano 2026-10-03-motion). Puro.

As regras vão no prompt e são aplicadas de novo aqui: o LLM pode errar a conta, e painel atrás de
painel sem o rosto voltar, ou motion tapando quase todo o Short, estraga o corte.
- a `capa` (gancho) só uma, de 0 a 2,2 s; nenhuma outra cena no primeiro GANCHO_S, com o rosto;
- cada cena de DUR_MIN_S a DUR_MAX_S (o tempo já vem cortado assim de render/motion.py; a que ficou
  curta é a que bateu no fim da fala);
- cenas não se sobrepõem; entre duas cenas "cheio" (cartão ou capa na tela inteira), pelo menos
  ROSTO_MIN_S de rosto. Cena "div" pode colar na vizinha: o rosto já está na janela de baixo, e o
  manual (testes/short-400mil-dinamica) cola chat → "PERDI DINHEIRO" e contador → valor cheio;
- motion somado ≤ FRACAO_MAX da duração do Short: passou, saem as últimas (nunca as `fixas`, as
  cenas já aceitas antes da segunda chamada ao LLM; render/motion.py).

Ritmo-alvo da pesquisa (pesquisa/03-corpus-financas-r2.md): 0,6–0,8 trocas de plano por 10 s.
Cada entrada e saída de painel é uma troca (`trocas_por_10s`); os limites acima não seguram abaixo
disso — uma cena a cada ~5 s já passa de 2 trocas por 10 s.
"""
from dataclasses import dataclass
from typing import Any

from cortes.render.motion_params import ESTADO, Params, params_json

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


def _vizinhos(b: Bruta, ficam: list[Bruta]) -> tuple[Bruta | None, Bruta | None]:
    antes = [f for f in ficam if f.inicio <= b.inicio]
    depois = [f for f in ficam if f.inicio > b.inicio]
    return (antes[-1] if antes else None), (depois[0] if depois else None)


def _rosto_entre(a: Bruta, b: Bruta) -> str | None:
    """Por que `b` não pode vir logo depois de `a` (None = pode)."""
    vao = b.inicio - a.fim
    if vao < -_EPS:
        return f"ritmo: sobrepõe a cena {a.componente} ({a.inicio:.2f}–{a.fim:.2f} s)"
    if ESTADO[a.componente] == ESTADO[b.componente] == "cheio" and vao < ROSTO_MIN_S - _EPS:
        return (f"ritmo: menos de {ROSTO_MIN_S:.1f} s de rosto entre {a.componente} "
                f"({a.inicio:.2f}–{a.fim:.2f} s) e {b.componente} ({b.inicio:.2f}–{b.fim:.2f} s)")
    return None


def _motivo(b: Bruta, ficam: list[Bruta]) -> str | None:
    """Por que a cena não cabe entre as que já ficaram (None = cabe)."""
    if b.componente == "capa" and any(f.componente == "capa" for f in ficam):
        return "ritmo: só uma capa, no gancho"
    if b.componente != "capa" and b.inicio < GANCHO_S - _EPS:
        return f"ritmo: começa no gancho (antes de {GANCHO_S:.1f} s), que é do rosto"
    if b.fim - b.inicio < DUR_MIN_S - _EPS and b.componente != "capa":
        return f"ritmo: só {b.fim - b.inicio:.1f} s até o fim da fala (mínimo {DUR_MIN_S:.1f} s)"
    antes, depois = _vizinhos(b, ficam)
    if antes is not None and (m := _rosto_entre(antes, b)):
        return m
    return _rosto_entre(b, depois) if depois is not None else None


def ritmo(cenas: list[Bruta], dur: float,
          fixas: list[Bruta] | None = None) -> tuple[list[Bruta], list[Descartada]]:
    """As cenas que ficam (com as `fixas`), em ordem, e as que saem, com o motivo."""
    ficam: list[Bruta] = sorted(fixas or [], key=lambda b: b.inicio)
    fora: list[Descartada] = []
    for b in sorted(cenas, key=lambda b: (b.inicio, b.componente != "capa")):
        motivo = _motivo(b, ficam)
        if motivo is None:
            ficam = sorted([*ficam, b], key=lambda x: x.inicio)
        else:
            fora.append(_fora(b, motivo))
    novas = [b for b in ficam if b not in (fixas or [])]
    while novas and sum(b.fim - b.inicio for b in ficam) > FRACAO_MAX * dur + _EPS:
        b = novas.pop()
        ficam.remove(b)
        fora.append(_fora(b, f"ritmo: motion passaria de {FRACAO_MAX:.0%} do Short"))
    return ficam, fora


def trocas_por_10s(cenas: list[Bruta], dur: float) -> float:
    """Trocas de plano: cada entrada e cada saída de painel; duas cenas coladas trocam uma vez só;
    a entrada em 0 e a saída no fim do Short não contam."""
    bordas = {round(t, 2) for b in cenas for t in (b.inicio, b.fim)}
    return 10 * len([t for t in bordas if _EPS < t < dur - _EPS]) / dur
