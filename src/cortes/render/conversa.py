"""f7 Conversa: alternar o enquadramento entre as pessoas de um plano aberto (puro; plano
2026-10-03-melhora-f7, spec produção §4.1).

Pesquisa R2 (pesquisa/03-corpus-financas-r2.md): os cortes top de finanças **mostram a outra pessoa
da conversa** (53% × 37%, 10×1 canais) e trocam mais de plano (mediana 0,62 por 10 s × 0,52; alvo
do app 0,6–0,8). Sem diarização não sabemos quem fala: alternar entre as pessoas já mostra a reação
de quem ouve, que é o sinal da R2 — não é "seguir quem fala".

Regras: só em plano com padrão e parceira (`parceira`), com ≥ PLANO_MIN_S e sem escolha manual no
editor (a escolha fixa o plano); corte seco no início de um grupo de legenda, nunca no meio de
palavra; cada trecho na mesma pessoa ≥ TRECHO_MIN_S; alternâncias só até o alvo de trocas
(`alvo_trocas`), contando as trocas reais de câmera; sem flash e sem zoom (Davi, 2026-10-02).
"""
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from cortes.render.legenda import Grupo
from cortes.render.rosto import Plano, Rosto, planos, posicao, trilha_fixa

TRECHO_MIN_S = 1.8      # tempo mínimo na mesma pessoa
PLANO_MIN_S = 3.5       # plano mais curto que isso não alterna
RITMO_ALVO = (0.6, 0.8)  # trocas por 10 s (R2)
RITMO_MIRA = 0.7        # o meio da faixa
DISTINTA = 0.2          # parceira a pelo menos isso × a largura da padrão; mais perto é a mesma
# pessoa partida em dois grupos pelo agrupamento por x, ou cabe na mesma janela
RAIO_MIN = 0.6          # parceira com rosto ≥ isso × o raio da padrão: menor é boneco, foto ou
# rosto cortado na borda (render real, wxCto9WSZcI: boneco na estante com r 55 × 223)
CONF_MIN = 0.75         # confiança média mínima da parceira (o boneco: 0,69; rostos reais: ≥ 0,79)
JANELA_FRASE_S = 1.5    # perto assim do ponto ideal, um início de frase ganha do ponto exato
_FECHA_FRASE = re.compile(r"[.?!…]$")


@dataclass(frozen=True)
class Alternancia:
    t: float   # instante do corte seco, no tempo do trecho
    k: int     # plano
    j: int     # pessoa que entra


@dataclass(frozen=True)
class Ritmo:
    trocas_10s: float
    reais: int
    alternancias: int


def trocas_por_10s(trocas: Sequence[float], dur: float) -> float:
    """Trocas de plano por 10 s: conta só as que caem dentro do Short (0 < t < dur)."""
    if dur <= 0:
        raise ValueError(f"duração do Short deveria ser positiva, veio {dur}")
    return round(sum(1 for t in trocas if 0 < t < dur) * 10 / dur, 2)


def alvo_trocas(dur: float) -> int:
    """Total de trocas que mira RITMO_MIRA dentro de RITMO_ALVO; se a faixa não cabe (Short curto),
    o maior total que não passa do teto."""
    menor = math.ceil(RITMO_ALVO[0] * dur / 10 - 1e-9)
    maior = math.floor(RITMO_ALVO[1] * dur / 10 + 1e-9)
    if menor > maior:
        return maior
    return min(maior, max(menor, math.floor(RITMO_MIRA * dur / 10 + 0.5)))


def parceira(p: Plano, largura: int) -> int | None:
    """A pessoa com quem a padrão alterna: a mais detectada entre as que ficam a pelo menos
    DISTINTA × largura da padrão, com rosto de tamanho parecido (RAIO_MIN) e confiança ≥ CONF_MIN.
    None se não houver."""
    if p.padrao is None:
        return None
    base = p.pessoas[p.padrao]
    longe = [j for j, s in enumerate(p.pessoas) if abs(s.x - base.x) >= DISTINTA * largura
             and s.r >= RAIO_MIN * base.r and s.conf >= CONF_MIN]
    if not longe:
        return None
    return max(longe, key=lambda j: (p.pessoas[j].n, p.pessoas[j].conf))


def _elegivel(p: Plano, escolhas: Mapping[int, int], dur: float, largura: int) -> bool:
    return (p.k not in escolhas and min(p.fim, dur) - p.ini >= PLANO_MIN_S
            and parceira(p, largura) is not None)


def _capacidade(p: Plano, dur: float) -> int:
    return max(0, math.floor((min(p.fim, dur) - p.ini) / TRECHO_MIN_S) - 1)


def _distribuir(elegiveis: list[Plano], n: int, dur: float) -> dict[int, int]:
    """Quantas alternâncias cada plano recebe: uma de cada vez, para o plano cujo maior pedaço
    (duração / (m + 1)) ainda é o mais longo — as trocas ficam espalhadas pelo Short."""
    m = {p.k: 0 for p in elegiveis}
    for _ in range(n):
        livres = [p for p in elegiveis if m[p.k] < _capacidade(p, dur)]
        if not livres:
            break
        p = max(livres, key=lambda q: ((min(q.fim, dur) - q.ini) / (m[q.k] + 1), -q.ini))
        m[p.k] += 1
    return m


def _inicios(grupos: Sequence[Grupo]) -> list[tuple[float, bool]]:
    """Início de cada grupo (menos o primeiro) e se ele abre frase (o anterior fecha em . ? ! …)."""
    return [(g.ini, bool(_FECHA_FRASE.search(ant.palavras[-1])))
            for ant, g in zip(grupos, grupos[1:], strict=False)]


def _no_plano(p: Plano, m: int, inicios: list[tuple[float, bool]], dur: float) -> list[float]:
    """Até m instantes no plano, cada um o início de grupo mais perto do ponto ideal (pedaços
    iguais), com início de frase preferido a até JANELA_FRASE_S; ≥ TRECHO_MIN_S entre vizinhos."""
    fim = min(p.fim, dur)
    passo = (fim - p.ini) / (m + 1)
    res: list[float] = []
    for i in range(1, m + 1):
        ideal, ant = p.ini + i * passo, res[-1] if res else p.ini
        validos = [(t, f) for t, f in inicios
                   if t - ant >= TRECHO_MIN_S - 1e-9 and fim - t >= TRECHO_MIN_S - 1e-9]
        if not validos:
            break
        res.append(min(validos, key=lambda c: (abs(c[0] - ideal) > JANELA_FRASE_S or not c[1],
                                                abs(c[0] - ideal), c[0]))[0])
    return res


def alternancias(pls: Sequence[Plano], escolhas: Mapping[int, int], grupos: Sequence[Grupo], dur: float,
                 largura: int) -> list[Alternancia]:
    """As alternâncias do Short, em ordem: cada plano elegível começa na padrão e vai e volta com
    a parceira, até o total de trocas (reais + alternâncias) chegar a `alvo_trocas(dur)`."""
    reais = sum(1 for p in pls[1:] if p.ini < dur)
    elegiveis = [p for p in pls if _elegivel(p, escolhas, dur, largura)]
    por_plano = _distribuir(elegiveis, max(0, alvo_trocas(dur) - reais), dur)
    inicios = _inicios(grupos)
    res: list[Alternancia] = []
    for p in elegiveis:
        par = parceira(p, largura)
        assert p.padrao is not None and par is not None   # garantido por _elegivel
        for i, t in enumerate(_no_plano(p, por_plano[p.k], inicios, dur)):
            res.append(Alternancia(t, p.k, par if i % 2 == 0 else p.padrao))
    return res


def trilha_conversa(r: Rosto, escolhas: Mapping[int, int], grupos: Sequence[Grupo],
                    dur: float) -> list[list[float]]:
    """A trilha fixa por plano (`rosto.trilha_fixa`) com um corte seco [t, x, y, 1] a cada
    alternância."""
    pls = planos(r)
    base = trilha_fixa(r, dict(escolhas))
    extra = [[a.t, *posicao(r, pls[a.k].pessoas[a.j]), 1]
             for a in alternancias(pls, escolhas, grupos, dur, r.largura)]
    return sorted(base + extra, key=lambda e: e[0])


def ritmo(r: Rosto, escolhas: Mapping[int, int], grupos: Sequence[Grupo], dur: float) -> Ritmo:
    pls = planos(r)
    reais = [p.ini for p in pls[1:]]
    alts = [a.t for a in alternancias(pls, escolhas, grupos, dur, r.largura)]
    return Ritmo(trocas_por_10s(reais + alts, dur), sum(1 for t in reais if t < dur), len(alts))
