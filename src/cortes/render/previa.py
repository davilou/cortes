"""Prévia do editor no navegador: o index.html do corte com o runtime do HyperFrames, como o
`hyperframes play` serve (testado em 2026-10-02: a única diferença do arquivo servido é essa linha).
O player (`<hyperframes-player>`) vem do mesmo pacote, versão fixa em web/static/index.html."""
from cortes.render.hyperframes import HYPERFRAMES
from cortes.render.processo import ErroRender

_VERSAO = HYPERFRAMES.split("@")[1]
RUNTIME = f"https://cdn.jsdelivr.net/npm/@hyperframes/core@{_VERSAO}/dist/hyperframe.runtime.iife.js"


def com_runtime(html: str) -> str:
    if "<head>" not in html:
        raise ErroRender("index.html sem <head>: não dá para injetar o runtime da prévia")
    return html.replace("<head>", f'<head>\n<script src="{RUNTIME}"></script>', 1)
