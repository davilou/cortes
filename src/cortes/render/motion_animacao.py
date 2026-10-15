"""f3 Motion, a animação de cada cena: linhas de GSAP na timeline `tl` do motion.tpl (plano
2026-10-03-motion; estilo denso: spec 2026-10-15-f3-denso). Puro.

Só ids gerados em render/motion_componentes.py e números entram no JavaScript, nunca texto do LLM.
O painel entra rápido (0,25 s) e os elementos dele um a um, nas batidas. A contagem usa
`contar(...)` do template, que escreve um valor por quadro (determinística, como o count-up do
registry do HyperFrames); o relógio do timer, `relogio(...)`. Os componentes novos estão em
render/motion_animacao_novos.py.
"""

from cortes.render import motion_animacao_novos as novos
from cortes.render.motion import Cena
from cortes.render.motion_animacao_novos import de, t
from cortes.render.motion_params import (
    Capa,
    Chat,
    Check,
    Comparacao,
    Contador,
    Destaque,
    Fluxo,
    Grade,
    Grafico,
    Ilustracao,
    Lista,
    Planta,
    Respiro,
    Rota,
    Timer,
    Valor,
    casas,
)

CONTA_S = 1.7  # count-up do registry: 1,72 s


def _conta(k: int, de_: float, valor: float, t0: float, dur_cena: float) -> list[str]:
    dur = round(min(CONTA_S, max(0.4, dur_cena - 0.5)), 2)
    c = max(casas(de_), casas(valor))
    return [
        f'contar("#m{k}-n", {de_}, {valor}, {c}, {t(t0)}, {dur});',
        f'tl.to("#m{k}-c", {{ scale: 1.07, duration: 0.16, ease: "power3.out" }}, {t(t0 + dur)});',
        f'tl.to("#m{k}-c", {{ scale: 1, duration: 0.16, ease: "power2.out" }}, {t(t0 + dur + 0.16)});',
    ]


def _entrada(c: Cena) -> list[str]:
    s, quando = f"#m{c.k}", c.inicio
    if c.componente == "capa":
        return [
            de(f"{s} .rotulo", "x: -60, opacity: 0", "x: 0, opacity: 1", 0.3, "power3.out", quando),
            de(f"{s} .titulo", "y: 60, opacity: 0", "y: 0, opacity: 1", 0.35, "expo.out", quando + 0.05),
        ]
    return [
        de(f"{s} .painel", "y: -24, opacity: 0", "y: 0, opacity: 1", 0.25, "power3.out", quando),
        de(f"{s} .cab", "x: -20, opacity: 0", "x: 0, opacity: 1", 0.25, "power2.out", quando + 0.08),
    ]


def _contador(c: Cena, p: Contador) -> list[str]:
    linhas = _conta(c.k, 0.0, p.valor, c.inicio + 0.05, c.fim - c.inicio)
    if p.marcos:
        dur = round(max(0.3, min(0.8, c.fim - c.batidas[0] - 0.1)), 2)
        linhas.append(de(f"#m{c.k}-prog", "scaleX: 0", "scaleX: 1", dur, "power2.inOut", c.batidas[0]))
    return linhas


def _valor(c: Cena, p: Valor) -> list[str]:
    linhas = _conta(c.k, p.de or 0.0, p.valor, c.inicio + 0.1, c.fim - c.inicio)
    if p.selo:
        linhas.append(
            de(
                f"#m{c.k}-selo",
                "scale: 0, rotation: -12",
                "scale: 1, rotation: 0",
                0.4,
                "back.out(2)",
                c.batidas[0],
            )
        )
    return linhas


def _comparacao(c: Cena, p: Comparacao) -> list[str]:
    s, ini = f"#m{c.k}", c.inicio
    linhas = [
        de(f"{s} .base", "scaleX: 0", "scaleX: 1", 0.25, "power2.out", ini),
        de(f"{s} .c0 .barra", "scaleY: 0", "scaleY: 1", 0.35, "power3.out", ini + 0.02),
        de(f"{s} .c1 .barra", "scaleY: 0", "scaleY: 1", 0.45, "power3.out", ini + 0.08),
        de(f"{s} .cval, {s} .crot", "opacity: 0", "opacity: 1", 0.2, "none", ini + 0.2),
    ]
    if p.carimbo:
        linhas.append(
            de(
                f"#m{c.k}-carimbo",
                "scale: 2.4, opacity: 0, rotation: -20",
                "scale: 1, opacity: 1, rotation: -6",
                0.25,
                "power4.in",
                max(c.batidas[0], ini + 0.15),
            )
        )
    return linhas


def _chat(c: Cena) -> list[str]:
    k, ini = c.k, c.inicio
    dig = ini + min(1.0, max(0.5, (c.fim - ini) * 0.4))
    pula = 'y: -14, duration: 0.25, ease: "sine.inOut", stagger: 0.12, yoyo: true, repeat: 3'
    return [
        de(f"#m{k}-perg", "scale: 0.75, opacity: 0", "scale: 1, opacity: 1", 0.18, "power2.out", ini + 0.15),
        de(f"#m{k}-dig", "scale: 0", "scale: 1", 0.3, "back.out(2)", dig),
        f'tl.fromTo("#m{k}-dig i", {{ y: 0 }}, {{ {pula} }}, {t(dig + 0.2)});',
    ]


def _lista(c: Cena) -> list[str]:
    linhas = []
    for j, quando in enumerate(c.batidas):
        linhas += [
            de(f"#m{c.k}-i{j}", "x: -120, opacity: 0", "x: 0, opacity: 1", 0.4, "expo.out", quando),
            de(f"#m{c.k}-i{j} .n", "scale: 0", "scale: 1", 0.3, "back.out(2.2)", quando + 0.15),
        ]
    return linhas


def _rota(c: Cena, p: Rota) -> list[str]:
    k, ini = c.k, c.inicio
    t2 = max(c.batidas[0], ini + 0.5)
    linhas = [
        de(f"#m{k}-p1", "y: -80, opacity: 0", "y: 0, opacity: 1", 0.4, "bounce.out", ini + 0.05),
        de(f"#m{k}-n1", "opacity: 0", "opacity: 1", 0.3, "none", ini + 0.2),
        de(
            f"#m{k}-rota",
            "strokeDashoffset: 1",
            "strokeDashoffset: 0",
            max(0.3, t2 - ini - 0.2),
            "power1.inOut",
            ini + 0.2,
        ),
        de(f"#m{k}-p2", "y: -80, opacity: 0", "y: 0, opacity: 1", 0.4, "bounce.out", t2),
        de(f"#m{k}-n2", "opacity: 0", "opacity: 1", 0.3, "none", t2 + 0.2),
    ]
    if p.selo:
        linhas.append(
            de(
                f"#m{k}-selo",
                "scale: 0.6, opacity: 0",
                "scale: 1, opacity: 1",
                0.35,
                "back.out(2)",
                min(max(c.batidas[1], t2 + 0.3), c.fim - 0.4),
            )
        )
    return linhas


def _novas(c: Cena) -> list[str]:
    p = c.params
    match p:
        case Grafico():
            return novos.grafico(c, p)
        case Fluxo():
            return novos.fluxo(c, p)
        case Timer():
            return novos.timer(c, p)
        case Check():
            return novos.check(c, p)
        case Grade():
            return novos.grade(c, p)
        case Destaque():
            return novos.destaque(c, p)
        case Planta():
            return novos.planta(c, p)
        case Ilustracao():
            return novos.ilustracao(c, p)
        case _:
            return []


def _proprias(c: Cena) -> list[str]:
    p = c.params
    match p:
        case Contador():
            return _contador(c, p)
        case Valor():
            return _valor(c, p)
        case Comparacao():
            return _comparacao(c, p)
        case Chat():
            return _chat(c)
        case Lista():
            return _lista(c)
        case Rota():
            return _rota(c, p)
        case Capa() | Respiro():
            return []
        case _:
            return _novas(c)


def animacoes(cenas: list[Cena]) -> str:
    return "\n".join(
        f"      {linha}"
        for c in cenas
        if c.componente != "respiro"
        for linha in (*_entrada(c), *_proprias(c))
    )
