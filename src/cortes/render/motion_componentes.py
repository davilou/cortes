"""f3 Motion, os componentes: o HTML e a animação GSAP de cada cena (plano 2026-10-03-motion). Puro.

Portados dos painéis feitos à mão em testes/short-400mil-dinamica/modelo.tpl (o CSS está em
render/formatos/motion.tpl). Todo texto vem do LLM e passa por `html.escape`; o JavaScript só leva
ids gerados aqui e números, nunca texto do LLM. Sem zoom lento nem flash (Davi, 2026-10-02): ficam
só as entradas dos elementos (descer de cima, barra crescendo, contagem, pino no mapa).
"""
import html
import json

from cortes.render.motion import Cena
from cortes.render.motion_params import (
    ESTADO,
    Capa,
    Chat,
    Comparacao,
    Contador,
    Lista,
    Params,
    Rota,
    ValorCheio,
    formatar,
)

TRILHA_DIV, TRILHA_CAPA, TRILHA_CHEIO = 2, 4, 5   # a legenda (20) fica por cima de tudo
BARRA_MAX_PX = 540     # a coluna mais alta da comparação (protótipo: #vperdi-c2)


def _e(t: str) -> str:
    return html.escape(t, quote=True)


def _t(x: float) -> str:
    return f"{round(x, 2)}"


def _fonte_contagem(texto: str, maximo: int) -> int:
    """Cabe numa linha de ~1000 px: um algarismo em Montserrat 900 ocupa ~0,62 em."""
    return min(maximo, int(1000 / (0.62 * max(len(texto), 1))))


def _contagem(k: int, prefixo: str, de: float, valor: float, sufixo: str, maximo: int) -> str:
    final = f"{prefixo} {formatar(valor)} {sufixo}".strip()
    fs = _fonte_contagem(final, maximo)
    pre = f'<span class="afixo">{_e(prefixo)}</span>' if prefixo else ""
    suf = f'<span class="afixo">{_e(sufixo)}</span>' if sufixo else ""
    return (f'<div class="contagem" id="m{k}-c" style="font-size: {fs}px">{pre}'
            f'<span class="num" id="m{k}-n">{formatar(de)}</span>{suf}</div>')


def _contador(k: int, p: Contador) -> str:
    marcos = ""
    if p.marcos:
        marcos = (f'<div class="linha"><div class="prog" id="m{k}-prog"></div></div>'
                  f'<div class="marcos"><span>{_e(p.marcos[0])}</span><span>{_e(p.marcos[1])}</span></div>')
    classe = "contador com-marcos" if p.marcos else "contador"
    return (f'<div class="{classe}"><div class="rotulo">{_e(p.rotulo)}</div>'
            f'{_contagem(k, p.prefixo, 0.0, p.valor, p.sufixo, 190)}{marcos}</div>')


def _valor_cheio(k: int, p: ValorCheio) -> str:
    selo = f'<div class="selo"><span id="m{k}-selo">{_e(p.selo)}</span></div>' if p.selo else ""
    return (f'<div class="valor-cheio"><div class="rotulo" id="m{k}-rot">{_e(p.rotulo)}</div>'
            f'{_contagem(k, p.prefixo, p.de or 0.0, p.valor, p.sufixo, 240)}{selo}</div>')


def _comparacao(k: int, p: Comparacao) -> str:
    alturas = [round(BARRA_MAX_PX * c.altura_rel) for c in p.colunas]
    cols = "".join(
        f'<div class="coluna c{j}"><div class="valor" style="bottom: {h + 20}px">{_e(c.valor_texto)}</div>'
        f'<div class="barra" style="height: {h}px"></div><div class="rotulo">{_e(c.rotulo)}</div></div>'
        for j, (c, h) in enumerate(zip(p.colunas, alturas, strict=True)))
    carimbo = ""
    if p.carimbo:
        carimbo = f'<div class="carimbo"><span id="m{k}-carimbo">{_e(p.carimbo)}</span></div>'
    return f'<div class="comparacao">{carimbo}<div class="base"></div>{cols}</div>'


def _chat(k: int, p: Chat) -> str:
    longa = " longa" if len(p.pergunta) > 50 else ""
    return (f'<div class="chat"><div class="rotulo">{_e(p.app)}</div>'
            f'<div class="pergunta{longa}" id="m{k}-perg">{_e(p.pergunta)}</div>'
            f'<div class="digitando" id="m{k}-dig"><i></i><i></i><i></i></div></div>')


def _lista(k: int, p: Lista) -> str:
    n = len(p.itens)
    alt = min(150, (400 - (n - 1) * 24) // n)
    itens = "".join(
        f'<div class="item" id="m{k}-i{j}" style="top: {250 + j * (alt + 24)}px; height: {alt}px">'
        f'<div class="n" style="width: {int(alt * 0.6)}px; height: {int(alt * 0.6)}px; '
        f'font-size: {int(alt * 0.33)}px">{j + 1}</div>'
        f'<div class="txt" style="font-size: {min(int(alt * 0.45), int(1200 / max(len(t), 1)))}px">'
        f'{_e(t)}</div></div>'
        for j, t in enumerate(p.itens))
    return f'<div class="lista"><div class="titulo">{_e(p.titulo)}</div>{itens}</div>'


def _rota(k: int, p: Rota) -> str:
    selo = f'<div class="selo-rota" id="m{k}-selo">{_e(p.selo)}</div>' if p.selo else ""
    return (f'<div class="rota"><svg class="mapa" viewBox="0 0 1080 680"><path id="m{k}-rota" '
            f'd="M200 410 C 380 430, 520 380, 640 320 S 820 260, 870 260" /></svg>'
            f'<div class="pino p1" id="m{k}-p1"><i></i></div><div class="pino p2" id="m{k}-p2"><i></i></div>'
            f'<div class="cidade n1" id="m{k}-n1">{_e(p.origem)}</div>'
            f'<div class="cidade n2" id="m{k}-n2">{_e(p.destino)}</div>{selo}</div>')


def _capa(k: int, p: Capa) -> str:
    palavras, feito = [], False
    for w in p.titulo.split():
        if not feito and p.destaque.lower() in w.lower():
            palavras.append(f"<b>{_e(w)}</b>")
            feito = True
        else:
            palavras.append(_e(w))
    fs = 104 if len(p.titulo) <= 30 else 86
    return (f'<div class="escurece"></div><div class="rotulo">{_e(p.rotulo)}</div>'
            f'<div class="titulo" style="font-size: {fs}px">{" ".join(palavras)}</div>')


def _corpo(k: int, p: Params) -> str:
    match p:
        case Capa():
            return _capa(k, p)
        case Contador():
            return _contador(k, p)
        case ValorCheio():
            return _valor_cheio(k, p)
        case Comparacao():
            return _comparacao(k, p)
        case Chat():
            return _chat(k, p)
        case Lista():
            return _lista(k, p)
        case Rota():
            return _rota(k, p)


def cena_html(c: Cena) -> str:
    """O clipe da cena: faixa em cima (div), cartão em tela cheia ou a capa."""
    attrs = f'data-start="{_t(c.inicio)}" data-duration="{_t(c.fim - c.inicio)}"'
    corpo = _corpo(c.k, c.params)
    abre = f'      <div id="m{c.k}" {attrs}'
    if c.componente == "capa":
        return f'{abre} class="clip capa" data-track-index="{TRILHA_CAPA}">{corpo}</div>'
    if ESTADO[c.componente] == "div":
        return (f'{abre} class="clip faixa" data-track-index="{TRILHA_DIV}">'
                f'<div class="conteudo">{corpo}</div><div class="costura"></div></div>')
    return f'{abre} class="clip cartao" data-track-index="{TRILHA_CHEIO}">{corpo}</div>'


def cenas_html(cenas: list[Cena]) -> str:
    return "\n".join(cena_html(c) for c in cenas)


def estados(cenas: list[Cena]) -> str:
    """[t, "div"|"cheio"]: a câmera troca para a janela de baixo durante a cena div, em corte seco."""
    res: list[list[object]] = [[0, "cheio"]]
    for c in cenas:
        if ESTADO[c.componente] == "div":
            res += [[round(c.inicio, 2), "div"], [round(c.fim, 2), "cheio"]]
    return json.dumps(res)

