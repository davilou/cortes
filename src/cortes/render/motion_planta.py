"""f3 Motion, a planta de imóvel em 3D isométrico (spec 2026-10-15-f3-denso §5; pesquisa/05: a
planta 3D do "Residencial Aurora"). Puro.

Desenhada por código a partir dos cômodos, sem SVG do LLM: os cômodos viram retângulos numa planta
de LARGURA × PROFUNDIDADE unidades, com área proporcional à dita (cômodo sem área divide o que
sobra por igual), em uma fileira até 3 cômodos e em duas acima disso. A projeção isométrica põe o
piso em z = 0 e o topo das paredes em z = ALTURA, desenhados do fundo para a frente.
"""

import html
import math
from dataclasses import dataclass

from cortes.render.motion_params import Planta, formatar

LARGURA, PROFUNDIDADE, ALTURA = 10.0, 8.0, 1.3
CAIXA = (900.0, 520.0)  # onde a planta cabe, dentro do painel
_COS, _SEN = math.cos(math.radians(30)), math.sin(math.radians(30))


@dataclass(frozen=True)
class Caixa:
    x: float
    y: float
    w: float
    d: float


def areas(p: Planta) -> list[float]:
    """A área de cada cômodo; sem área dita, o resto do total (ou 1) dividido por igual."""
    ditas = [c.m2 for c in p.comodos if c.m2 is not None]
    sem = sum(1 for c in p.comodos if c.m2 is None)
    if not sem:
        return [float(c.m2 or 0) for c in p.comodos]
    sobra = (p.total_m2 or 0) - sum(ditas)
    cada = sobra / sem if sobra > 0 else (sum(ditas) / len(ditas) if ditas else 1.0)
    return [float(c.m2) if c.m2 is not None else cada for c in p.comodos]


def _fileiras(n: int) -> list[range]:
    if n <= 3:
        return [range(n)]
    meio = math.ceil(n / 2)
    return [range(meio), range(meio, n)]


def caixas(p: Planta) -> list[Caixa]:
    """Os cômodos na planta, em ordem, com área proporcional (a soma ocupa a planta toda)."""
    a = areas(p)
    total = sum(a)
    res: list[Caixa] = []
    y = 0.0
    for f in _fileiras(len(a)):
        soma = sum(a[j] for j in f)
        d = PROFUNDIDADE * soma / total
        x = 0.0
        for j in f:
            w = LARGURA * a[j] / soma
            res.append(Caixa(round(x, 4), round(y, 4), round(w, 4), round(d, 4)))
            x += w
        y += d
    return res


def _escala() -> tuple[float, float, float]:
    """Escala e deslocamento que centram a planta inteira na CAIXA."""
    larg = (LARGURA + PROFUNDIDADE) * _COS
    alt = (LARGURA + PROFUNDIDADE) * _SEN + ALTURA
    s = min(CAIXA[0] / larg, CAIXA[1] / alt)
    return s, (CAIXA[0] - larg * s) / 2 + PROFUNDIDADE * _COS * s, (CAIXA[1] - alt * s) / 2 + ALTURA * s


def _ponto(x: float, y: float, z: float, s: float, ox: float, oy: float) -> str:
    return f"{ox + (x - y) * _COS * s:.1f},{oy + (x + y) * _SEN * s - z * s:.1f}"


def _comodo(j: int, k: int, c: Caixa, nome: str, area: str, esc: tuple[float, float, float]) -> str:
    s, ox, oy = esc
    cantos = [(c.x, c.y), (c.x + c.w, c.y), (c.x + c.w, c.y + c.d), (c.x, c.y + c.d)]
    piso = " ".join(_ponto(x, y, 0, s, ox, oy) for x, y in cantos)
    topo = " ".join(_ponto(x, y, ALTURA, s, ox, oy) for x, y in cantos)
    pilares = "".join(
        f'<line x1="{a.split(",")[0]}" y1="{a.split(",")[1]}" x2="{b.split(",")[0]}" y2="{b.split(",")[1]}"/>'
        for a, b in zip(piso.split(), topo.split(), strict=True)
    )
    cx, cy = _ponto(c.x + c.w / 2, c.y + c.d / 2, 0, s, ox, oy).split(",")
    rotulo = f'<text class="pl-nome" x="{cx}" y="{cy}">{html.escape(nome)}</text>'
    if area:
        rotulo += f'<text class="pl-area" x="{cx}" y="{float(cy) + 30:.1f}">{html.escape(area)}</text>'
    return (
        f'<g class="pl-comodo" id="m{k}-c{j}"><polygon class="pl-piso" points="{piso}"/>'
        f'<g class="pl-parede">{pilares}<polygon points="{topo}"/></g>{rotulo}</g>'
    )


def _area(m2: float | None) -> str:
    """Só a área dita aparece (regra dos números); a calculada só dá o tamanho do cômodo."""
    return f"{formatar(m2)} m²" if m2 is not None else ""


def planta_svg(k: int, p: Planta) -> str:
    """A planta da cena `k`; cada cômodo é `#m{k}-c{j}` (a animação os levanta um a um)."""
    esc = _escala()
    cs = caixas(p)
    ordem = sorted(range(len(cs)), key=lambda j: (cs[j].x + cs[j].y, j))  # do fundo para a frente
    corpo = "".join(_comodo(j, k, cs[j], p.comodos[j].nome, _area(p.comodos[j].m2), esc) for j in ordem)
    return (
        f'<svg class="planta-svg" viewBox="0 0 {CAIXA[0]:.0f} {CAIXA[1]:.0f}" '
        f'xmlns="http://www.w3.org/2000/svg">{corpo}</svg>'
    )
