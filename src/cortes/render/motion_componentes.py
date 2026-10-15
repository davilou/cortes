"""f3 Motion, o HTML de cada cena e os estados da tela (spec 2026-10-15-f3-denso §3, §5). Puro.

Estado `div`: o painel (`.faixa` > `.painel`, um cartão de 1000 × 724 px na faixa de cima) e o
falante no card de baixo. Estado `cheio`: o rosto em tela cheia — no gancho, com a capa por cima;
no respiro, sozinho (o respiro não tem HTML). O CSS está em render/formatos/motion.tpl; os
componentes novos, em render/motion_componentes_novos.py. Todo texto vem do LLM e passa por
`html.escape`; o JavaScript só leva ids gerados aqui e números, nunca texto do LLM.
"""

import html
import json

from cortes.render.motion import Cena
from cortes.render.motion_componentes_novos import (
    cabecalho,
    check,
    destaque,
    fluxo,
    grade,
    grafico,
    ilustracao,
    planta,
    timer,
)
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
    Params,
    Planta,
    Rota,
    Timer,
    Valor,
    formatar,
)
from cortes.render.motion_ritmo import GANCHO_S

TRILHA_DIV, TRILHA_CAPA = 2, 4  # a legenda (20) fica por cima de tudo
BARRA_MAX_PX = 300  # a coluna mais alta da comparação, dentro do painel


def _e(t: str) -> str:
    return html.escape(t, quote=True)


def _t(x: float) -> str:
    return f"{round(x, 2)}"


def _fonte_contagem(texto: str, maximo: int) -> int:
    """Cabe numa linha de ~900 px: um algarismo em Montserrat 800 ocupa ~0,62 em."""
    return min(maximo, int(900 / (0.62 * max(len(texto), 1))))


def _contagem(k: int, prefixo: str, de: float, valor: float, sufixo: str, maximo: int) -> str:
    final = f"{prefixo} {formatar(valor)} {sufixo}".strip()
    fs = _fonte_contagem(final, maximo)
    pre = f'<span class="afixo">{_e(prefixo)}</span>' if prefixo else ""
    suf = f'<span class="afixo">{_e(sufixo)}</span>' if sufixo else ""
    return (
        f'<div class="contagem" id="m{k}-c" style="font-size: {fs}px">{pre}'
        f'<span class="num" id="m{k}-n">{formatar(de)}</span>{suf}</div>'
    )


def _contador(k: int, p: Contador) -> str:
    marcos = ""
    if p.marcos:
        marcos = (
            f'<div class="linha"><div class="prog" id="m{k}-prog"></div></div>'
            f'<div class="marcos"><span>{_e(p.marcos[0])}</span><span>{_e(p.marcos[1])}</span></div>'
        )
    classe = "contador com-marcos" if p.marcos else "contador"
    return (
        f'{cabecalho(p.rotulo)}<div class="{classe}">'
        f"{_contagem(k, p.prefixo, 0.0, p.valor, p.sufixo, 190)}{marcos}</div>"
    )


def _valor(k: int, p: Valor) -> str:
    selo = f'<div class="selo"><span id="m{k}-selo">{_e(p.selo)}</span></div>' if p.selo else ""
    return (
        f'{cabecalho(p.rotulo)}<div class="valor">'
        f"{_contagem(k, p.prefixo, p.de or 0.0, p.valor, p.sufixo, 230)}{selo}</div>"
    )


def _comparacao(k: int, p: Comparacao) -> str:
    alturas = [round(BARRA_MAX_PX * c.altura_rel) for c in p.colunas]
    cols = "".join(
        f'<div class="coluna c{j}"><div class="cval" style="bottom: {h + 18}px">{_e(c.valor_texto)}</div>'
        f'<div class="barra" style="height: {h}px"></div><div class="crot">{_e(c.rotulo)}</div></div>'
        for j, (c, h) in enumerate(zip(p.colunas, alturas, strict=True))
    )
    carimbo = (
        f'<div class="carimbo"><span id="m{k}-carimbo">{_e(p.carimbo)}</span></div>' if p.carimbo else ""
    )
    return f'<div class="comparacao">{carimbo}<div class="base"></div>{cols}</div>'


def _chat(k: int, p: Chat) -> str:
    longa = " longa" if len(p.pergunta) > 50 else ""
    return (
        f'{cabecalho(p.app)}<div class="chat"><div class="pergunta{longa}" id="m{k}-perg">'
        f'{_e(p.pergunta)}</div><div class="digitando" id="m{k}-dig"><i></i><i></i><i></i></div></div>'
    )


def _lista(k: int, p: Lista) -> str:
    n = len(p.itens)
    alt = min(120, (470 - (n - 1) * 20) // n)
    itens = "".join(
        f'<div class="item" id="m{k}-i{j}" style="top: {190 + j * (alt + 20)}px; height: {alt}px">'
        f'<div class="n" style="width: {int(alt * 0.62)}px; height: {int(alt * 0.62)}px; '
        f'font-size: {int(alt * 0.32)}px">{j + 1}</div>'
        f'<div class="txt" style="font-size: {min(int(alt * 0.42), int(1100 / max(len(t), 1)))}px">'
        f"{_e(t)}</div></div>"
        for j, t in enumerate(p.itens)
    )
    return f'<div class="lista"><div class="titulo">{_e(p.titulo)}</div>{itens}</div>'


def _rota(k: int, p: Rota) -> str:
    selo = f'<div class="selo-rota" id="m{k}-selo">{_e(p.selo)}</div>' if p.selo else ""
    return (
        f'<div class="rota"><svg class="mapa" viewBox="0 0 1000 724"><path id="m{k}-rota" '
        f'd="M190 470 C 360 490, 480 430, 600 360 S 760 290, 810 280" pathLength="1"/></svg>'
        f'<div class="pino p1" id="m{k}-p1"><i></i></div><div class="pino p2" id="m{k}-p2"><i></i></div>'
        f'<div class="cidade n1" id="m{k}-n1">{_e(p.origem)}</div>'
        f'<div class="cidade n2" id="m{k}-n2">{_e(p.destino)}</div>{selo}</div>'
    )


def _capa(k: int, p: Capa) -> str:
    palavras, feito = [], False
    for w in p.titulo.split():
        if not feito and p.destaque.lower() in w.lower():
            palavras.append(f"<b>{_e(w)}</b>")
            feito = True
        else:
            palavras.append(_e(w))
    fs = 104 if len(p.titulo) <= 30 else 86
    return (
        f'<div class="escurece"></div><div class="rotulo">{_e(p.rotulo)}</div>'
        f'<div class="titulo" style="font-size: {fs}px">{" ".join(palavras)}</div>'
    )


def _corpo(k: int, p: Params, svgs: dict[int, str]) -> str:
    match p:
        case Contador():
            return _contador(k, p)
        case Valor():
            return _valor(k, p)
        case Comparacao():
            return _comparacao(k, p)
        case Chat():
            return _chat(k, p)
        case Lista():
            return _lista(k, p)
        case Rota():
            return _rota(k, p)
        case Grafico():
            return grafico(k, p)
        case Fluxo():
            return fluxo(k, p)
        case Timer():
            return timer(k, p)
        case Check():
            return check(k, p)
        case Grade():
            return grade(k, p)
        case Destaque():
            return destaque(k, p)
        case Planta():
            return planta(k, p)
        case Ilustracao():
            return ilustracao(k, p, svgs.get(k))
        case _:
            raise ValueError(f"componente sem HTML no painel: {type(p).__name__}")


def cena_html(c: Cena, svgs: dict[int, str]) -> str:
    """O clipe da cena: a capa por cima do rosto cheio ou o painel na faixa de cima. O respiro não
    tem clipe — é só o estado `cheio`."""
    if c.componente == "respiro":
        return ""
    attrs = f'id="m{c.k}" data-start="{_t(c.inicio)}" data-duration="{_t(c.fim - c.inicio)}"'
    if isinstance(c.params, Capa):
        corpo = _capa(c.k, c.params)
        return f'      <div {attrs} class="clip capa" data-track-index="{TRILHA_CAPA}">{corpo}</div>'
    return (
        f'      <div {attrs} class="clip faixa" data-track-index="{TRILHA_DIV}">'
        f'<div class="painel {c.componente}-p">{_corpo(c.k, c.params, svgs)}</div></div>'
    )


def cenas_html(cenas: list[Cena], svgs: dict[int, str]) -> str:
    return "\n".join(h for c in cenas if (h := cena_html(c, svgs)))


def estados(cenas: list[Cena]) -> str:
    """[t, "div"|"cheio"]: rosto cheio no gancho (até o fim da capa, ou GANCHO_S sem capa), tela
    dividida depois, e cheio de novo em cada respiro — tudo em corte seco."""
    capa = next((c for c in cenas if c.componente == "capa"), None)
    res: list[list[object]] = [[0, "cheio"], [round(capa.fim if capa else GANCHO_S, 2), "div"]]
    for c in sorted((c for c in cenas if c.componente == "respiro"), key=lambda c: c.inicio):
        res += [[round(c.inicio, 2), "cheio"], [round(c.fim, 2), "div"]]
    return json.dumps(res)
