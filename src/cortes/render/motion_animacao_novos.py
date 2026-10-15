"""f3 Motion, a animação dos componentes novos (spec 2026-10-15-f3-denso §5; pesquisa/05: os
elementos entram um a um, ~1 batida por segundo, e o texto "digita"). Puro.

Só ids gerados em render/motion_componentes_novos.py e números entram no JavaScript. Linhas e
anéis usam `pathLength="1"`: desenhar é levar o `strokeDashoffset` de 1 a 0.
"""

from cortes.render.motion import Cena
from cortes.render.motion_params import Check, Destaque, Fluxo, Grade, Grafico, Ilustracao, Planta, Timer

DESENHO_MAX_S = 1.2
_MODO = {"s": 0, "min": 1, "h": 2}   # relogio() do motion.tpl: 0 → "00:SS", 1 e 2 → "VV:00"


def t(x: float) -> str:
    return f"{round(x, 2)}"


def de(sel: str, de_: str, ate: str, dur: float, ease: str, quando: float) -> str:
    ate_ = f'{{ {ate}, duration: {round(dur, 2)}, ease: "{ease}" }}'
    return f'tl.fromTo("{sel}", {{ {de_} }}, {ate_}, {t(quando)});'


def _desenho(c: Cena) -> float:
    return round(min(DESENHO_MAX_S, max(0.4, (c.fim - c.inicio) * 0.45)), 2)


def grafico(c: Cena, p: Grafico) -> list[str]:
    k, ini, d = c.k, c.inicio, _desenho(c)
    quando = max(c.batidas[0], ini + d) if c.batidas else ini + d
    return [
        de(f"#m{k}-linha", "strokeDashoffset: 1", "strokeDashoffset: 0", d, "power2.inOut", ini + 0.1),
        de(f"#m{k}-area", "opacity: 0", "opacity: 1", d, "none", ini + 0.1),
        de(f"#m{k} .gp", "scale: 0", "scale: 1, stagger: 0.08", 0.25, "back.out(2)", ini + 0.2),
        de(f"#m{k}-dest", "scale: 0, transformOrigin: '50% 50%'", "scale: 1", 0.35, "back.out(2.4)", quando),
        de(f"#m{k}-valor", "y: 20, opacity: 0", "y: 0, opacity: 1", 0.3, "power3.out", quando + 0.05),
    ]


def fluxo(c: Cena, p: Fluxo) -> list[str]:
    linhas = []
    for j, quando in enumerate(c.batidas):
        linhas.append(
            de(f"#m{c.k}-p{j}", "y: 30, opacity: 0", "y: 0, opacity: 1", 0.35, "power3.out", quando)
        )
        if j < len(p.passos) - 1:
            linhas.append(de(f"#m{c.k}-s{j}", "scaleX: 0", "scaleX: 1", 0.3, "power2.out", quando + 0.2))
    if c.batidas:
        linhas.append(
            f'tl.to("#m{c.k}-p{p.ativo} .bola", {{ scale: 1.12, duration: 0.18, yoyo: true, '
            f'repeat: 1, ease: "sine.inOut" }}, {t(c.batidas[p.ativo] + 0.35)});'
        )
    return linhas


def timer(c: Cena, p: Timer) -> list[str]:
    d = round(min(1.8, max(0.6, c.fim - c.inicio - 0.6)), 2)
    return [
        f'relogio("#m{c.k}-rel", {p.valor}, {_MODO[p.unidade]}, {t(c.inicio + 0.1)}, {d});',
        de(f"#m{c.k}-anel", "strokeDashoffset: 1", "strokeDashoffset: 0", d, "sine.inOut", c.inicio + 0.1),
    ]


def check(c: Cena, p: Check) -> list[str]:
    quando = max(c.batidas[0], c.inicio + 0.45) if c.batidas else c.inicio + 0.45
    return [
        de(
            f"#m{c.k}-circ", "strokeDashoffset: 1", "strokeDashoffset: 0", 0.45, "power2.out", c.inicio + 0.05
        ),
        de(f"#m{c.k}-marca", "strokeDashoffset: 1", "strokeDashoffset: 0", 0.35, "power3.out", quando),
        de(f"#m{c.k}-txt", "y: 24, opacity: 0", "y: 0, opacity: 1", 0.3, "power3.out", c.inicio + 0.2),
    ]


def grade(c: Cena, p: Grade) -> list[str]:
    return [
        de(f"#m{c.k}-b{j}", "scale: 0.8, opacity: 0", "scale: 1, opacity: 1", 0.3, "back.out(1.8)", quando)
        for j, quando in enumerate(c.batidas)
    ]


def destaque(c: Cena, p: Destaque) -> list[str]:
    n = len(p.frase.split())
    passo = round(min(0.18, max(0.05, (c.fim - c.inicio - 0.8) / max(n, 1))), 3)
    linhas = [
        f'tl.fromTo("#m{c.k} .w", {{ opacity: 0, y: 16 }}, {{ opacity: 1, y: 0, duration: 0.16, '
        f'stagger: {passo}, ease: "power2.out" }}, {t(c.inicio + 0.05)});'
    ]
    if c.batidas:
        linhas.append(
            f'tl.fromTo("#m{c.k} .w.on", {{ scale: 1 }}, {{ scale: 1.12, duration: 0.18, yoyo: true, '
            f'repeat: 1, ease: "sine.inOut" }}, {t(c.batidas[0])});'
        )
    return linhas


def planta(c: Cena, p: Planta) -> list[str]:
    return [
        de(f"#m{c.k}-c{j}", "y: 40, opacity: 0", "y: 0, opacity: 1", 0.4, "power3.out", quando)
        for j, quando in enumerate(c.batidas)
    ]


def ilustracao(c: Cena, p: Ilustracao) -> list[str]:
    quando = c.batidas[0] if c.batidas else c.inicio + 0.6
    return [
        f'tl.fromTo("#m{c.k}-ilus svg > *", {{ opacity: 0, scale: 0.92, transformOrigin: "50% 50%" }}, '
        f'{{ opacity: 1, scale: 1, duration: 0.3, stagger: 0.05, ease: "power2.out" }}, '
        f"{t(c.inicio + 0.05)});",
        de(f"#m{c.k}-rot", "y: 20, opacity: 0", "y: 0, opacity: 1", 0.3, "power3.out", quando),
    ]
