"""Legenda queimada do Short: palavras do corte e grupos de legenda (puro; spec produção §4.1).

Portado de testes/comum/corte.py (`palavras`, `grupos`, `legenda_html`), sem as trocas manuais
de palavra do protótipo (eram erros do Whisper daquele episódio). Até o editor (plano C), a
legenda sai como veio (spec §10).
"""
import html
import re
from dataclasses import dataclass

from cortes.tipos import Palavra

MAX_PALAVRAS = 5
JUNTA_S = 0.55      # grupos que começam a menos disso um do outro viram um só
JUNTA_MAX = 7       # ... desde que juntos não passem disso
DUR_MAX_S = 2.6
_FECHA = re.compile(r"[.,?!…]$")


@dataclass(frozen=True)
class Grupo:
    ini: float
    dur: float
    palavras: tuple[str, ...]


def palavras_do_corte(palavras: list[Palavra], ini: float, fim: float) -> list[Palavra]:
    """Palavras que COMEÇAM em [ini, fim], com tempo relativo a ini."""
    return [Palavra(p.texto, round(p.inicio - ini, 3), round(p.fim - ini, 3))
            for p in palavras if ini - 0.01 <= p.inicio <= fim + 0.01]


def _brutos(ws: list[Palavra]) -> list[list[Palavra]]:
    gs: list[list[Palavra]] = [[]]
    for w in ws:
        gs[-1].append(w)
        if len(gs[-1]) >= MAX_PALAVRAS or (len(gs[-1]) >= 2 and _FECHA.search(w.texto)):
            gs.append([])
    return [g for g in gs if g]


def _fundir(gs: list[list[Palavra]]) -> list[list[Palavra]]:
    k = 0
    while k < len(gs) - 1:
        if gs[k + 1][0].inicio - gs[k][0].inicio < JUNTA_S and len(gs[k]) + len(gs[k + 1]) <= JUNTA_MAX:
            gs[k] += gs.pop(k + 1)
        else:
            k += 1
    return gs


def _sem_duracao_zero(gs: list[list[Palavra]]) -> list[list[Palavra]]:
    """Um grupo cuja janela ficaria com duração ≤ 0 (o próximo começa no mesmo instante ou antes —
    palavras remapeadas pro mesmo ponto) funde no anterior; sem anterior (é o primeiro), funde no
    seguinte. `_fundir` já cobre o caso comum (início próximo); isso só sobra quando a fusão normal
    não rolou por passar de `JUNTA_MAX` palavras."""
    k = 0
    while k < len(gs) - 1:
        if gs[k + 1][0].inicio - gs[k][0].inicio <= 0:
            if k > 0:
                gs[k - 1] += gs.pop(k)
                k -= 1
            else:
                gs[0] += gs.pop(1)
        else:
            k += 1
    return gs


def _funde_ultimo_se_vazio(gs: list[list[Palavra]], dur: float) -> list[list[Palavra]]:
    """O último grupo usa `b = dur` (não tem próximo para fechar nele); se o seu início foi
    remapeado para `dur` ou além, a janela fica com duração ≤ 0. `_sem_duracao_zero` não pega
    esse caso — só compara grupos adjacentes entre si, nunca contra `dur`."""
    if len(gs) > 1 and gs[-1][0].inicio >= dur:
        ultimo = gs.pop()
        gs[-1] += ultimo
    return gs


def grupos(ws: list[Palavra], dur: float) -> list[Grupo]:
    """Fecham em pontuação (2+ palavras) ou em 5 palavras; cada um fica até o próximo, no máx. 2,6 s."""
    gs = _funde_ultimo_se_vazio(_sem_duracao_zero(_fundir(_brutos(ws))), dur)
    res: list[Grupo] = []
    for k, g in enumerate(gs):
        a = g[0].inicio
        b = gs[k + 1][0].inicio if k + 1 < len(gs) else dur
        res.append(Grupo(round(a, 2), round(min(b, a + DUR_MAX_S) - a, 2), tuple(p.texto for p in g)))
    return res


def legenda_html(gs: list[Grupo]) -> str:
    return "\n".join(
        f'      <div class="clip leg" id="leg-{i}" data-start="{g.ini}" data-duration="{g.dur}" '
        f'data-track-index="20"><span>{html.escape(" ".join(g.palavras))}</span></div>'
        for i, g in enumerate(gs))
