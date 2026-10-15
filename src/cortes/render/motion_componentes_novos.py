"""f3 Motion, o HTML dos componentes novos do estilo denso (spec 2026-10-15-f3-denso §5). Puro.

O CSS está em render/formatos/motion.tpl; a animação, em render/motion_animacao_novos.py. Todo
texto do LLM passa por `html.escape`; ícone só pelo nome, da lista fechada (render/motion_icones.py);
o SVG da ilustração só como saiu de render/motion_svg.py (sanitizado).
"""

import html

from cortes.render.motion_icones import icone_svg
from cortes.render.motion_params import (
    Check,
    Destaque,
    Fluxo,
    Grade,
    Grafico,
    Ilustracao,
    Planta,
    Timer,
    formatar,
)
from cortes.render.motion_planta import planta_svg

GRAF_W, GRAF_H, GRAF_X0, GRAF_Y0 = 880.0, 360.0, 60.0, 40.0  # área do gráfico dentro do svg 1000×460
GRAF_TOPO = 110  # o svg do gráfico fica a 110 px do topo do painel, em escala 1 (motion.tpl)


def _e(t: str) -> str:
    return html.escape(t, quote=True)


def cabecalho(rotulo: str, direita: str = "") -> str:
    lado = f'<span class="cab-dir">{_e(direita)}</span>' if direita else ""
    return f'<div class="cab"><i class="ponto"></i><span>{_e(rotulo)}</span>{lado}</div>'


def _pontos_grafico(p: Grafico) -> list[tuple[float, float]]:
    ys = [q.y for q in p.pontos]
    baixo, alto = min(0.0, min(ys)), max(ys)
    faixa = alto - baixo or 1.0
    n = len(p.pontos)
    return [
        (round(GRAF_X0 + GRAF_W * j / (n - 1), 1), round(GRAF_Y0 + GRAF_H * (1 - (q.y - baixo) / faixa), 1))
        for j, q in enumerate(p.pontos)
    ]


def grafico(k: int, p: Grafico) -> str:
    xy = _pontos_grafico(p)
    d = "M" + " L".join(f"{x} {y}" for x, y in xy)
    area = f"{d} L{xy[-1][0]} {GRAF_Y0 + GRAF_H} L{xy[0][0]} {GRAF_Y0 + GRAF_H} Z"
    dx, dy = xy[p.ponto_destaque]
    xs = "".join(
        f'<text class="gx" x="{x}" y="{GRAF_Y0 + GRAF_H + 52}">{_e(q.x)}</text>'
        for (x, _), q in zip(xy, p.pontos, strict=True)
    )
    pts = "".join(f'<circle class="gp" cx="{x}" cy="{y}" r="9"/>' for x, y in xy)
    valor = formatar(p.pontos[p.ponto_destaque].y)
    return (
        f'{cabecalho(p.rotulo)}<svg class="graf" viewBox="0 0 1000 460">'
        f'<line class="gbase" x1="{GRAF_X0}" y1="{GRAF_Y0 + GRAF_H}" x2="{GRAF_X0 + GRAF_W}" '
        f'y2="{GRAF_Y0 + GRAF_H}"/><path class="garea" id="m{k}-area" d="{area}"/>'
        f'<path class="glinha" id="m{k}-linha" d="{d}" pathLength="1"/>{pts}{xs}'
        f'<circle class="gdest" id="m{k}-dest" cx="{dx}" cy="{dy}" r="20"/></svg>'
        f'<div class="gvalor" id="m{k}-valor" style="left: {dx:.0f}px; top: {GRAF_TOPO + dy - 34:.0f}px">'
        f"{_e(valor)}</div>"
    )


def fluxo(k: int, p: Fluxo) -> str:
    n = len(p.passos)
    passos = []
    for j, q in enumerate(p.passos):
        classe = "passo ativo" if j == p.ativo else "passo"
        seta = f'<div class="seta" id="m{k}-s{j}"></div>' if j < n - 1 else ""
        passos.append(
            f'<div class="{classe}" id="m{k}-p{j}"><div class="bola">{icone_svg(q.icone, "ic")}</div>'
            f'<div class="ptxt">{_e(q.texto)}</div></div>{seta}'
        )
    return f'<div class="fluxo n{n}">{"".join(passos)}</div>'


def timer(k: int, p: Timer) -> str:
    unidade = {"s": "segundos", "min": "minutos", "h": "horas"}[p.unidade]
    return (
        f'{cabecalho(p.rotulo)}<svg class="anel" viewBox="0 0 400 400"><circle class="anel-fundo" '
        f'cx="200" cy="200" r="170"/><circle class="anel-prog" id="m{k}-anel" cx="200" cy="200" '
        f'r="170" pathLength="1"/></svg><div class="relogio" id="m{k}-rel">00:00</div>'
        f'<div class="unidade">{_e(f"{p.valor} {unidade}")}</div>'
    )


def check(k: int, p: Check) -> str:
    marca = "M130 205 L180 255 L275 150" if p.sinal == "sim" else "M140 140 L260 260 M260 140 L140 260"
    classe = "check sim" if p.sinal == "sim" else "check nao"
    return (
        f'<div class="{classe}"><svg class="selo-check" viewBox="0 0 400 400">'
        f'<circle id="m{k}-circ" cx="200" cy="200" r="160" pathLength="1"/>'
        f'<path id="m{k}-marca" d="{marca}" pathLength="1"/></svg>'
        f'<div class="ctxt" id="m{k}-txt">{_e(p.texto)}</div></div>'
    )


def grade(k: int, p: Grade) -> str:
    cols = 2 if len(p.blocos) <= 4 else 3
    blocos = "".join(
        f'<div class="bloco" id="m{k}-b{j}">{icone_svg(q.icone, "ic")}'
        f'<div class="btxt">{_e(q.texto)}</div></div>'
        for j, q in enumerate(p.blocos)
    )
    return f'<div class="grade c{cols} n{len(p.blocos)}">{blocos}</div>'


def destaque(k: int, p: Destaque) -> str:
    alvo, feito, palavras = p.palavra.lower(), False, []
    for j, w in enumerate(p.frase.split()):
        on = not feito and alvo in w.lower()
        feito = feito or on
        palavras.append(f'<span class="w{" on" if on else ""}" id="m{k}-w{j}">{_e(w)}</span>')
    fs = 96 if len(p.frase) <= 28 else 78 if len(p.frase) <= 44 else 64
    return f'<div class="destaque" style="font-size: {fs}px">{" ".join(palavras)}</div>'


def planta(k: int, p: Planta) -> str:
    total = f"{formatar(p.total_m2)} m²" if p.total_m2 is not None else ""
    return f'{cabecalho("planta", total)}<div class="planta">{planta_svg(k, p)}</div>'


def ilustracao(k: int, p: Ilustracao, svg: str | None) -> str:
    desenho = svg if svg is not None else f'<div class="ilus-icone">{icone_svg(p.icone, "ic")}</div>'
    return (
        f'<div class="ilus" id="m{k}-ilus">{desenho}</div>'
        f'<div class="ilus-rot" id="m{k}-rot">{_e(p.rotulo)}</div>'
    )
