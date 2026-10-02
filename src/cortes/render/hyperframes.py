"""Projeto HyperFrames de um corte e o render em MP4 (spec produção §4.1).

O MP4 sai primeiro como `.parcial.mp4` e só vira `short-v<k>.mp4` se o render terminar: um render
que falha mantém a versão anterior intacta (spec §8).
"""
from pathlib import Path

from cortes.episodio import salvar_json, salvar_texto
from cortes.render.processo import CAUDA, ErroRender, Rodar

HYPERFRAMES = "hyperframes@0.8.104"   # a versão dos protótipos aprovados (testes/*/package.json)
_CONFIG = {
    "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
    "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
    "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
    "media": {"autoProxy": True},
}


def criar_projeto(proj: Path, html: str) -> None:
    proj.mkdir(parents=True, exist_ok=True)
    salvar_json(proj / "hyperframes.json", _CONFIG)
    salvar_texto(proj / "index.html", html)


def renderizar(proj: Path, saida: Path, npx: str, rodar: Rodar) -> None:
    """`parcial` é absoluto: o processo roda com `cwd=proj`, então um `saida` relativo (relativo ao
    cwd do app, não do processo) escreveria no lugar errado se ficasse relativo."""
    parcial = saida.resolve().with_name(saida.stem + ".parcial.mp4")
    try:
        codigo, log = rodar([npx, "--yes", HYPERFRAMES, "render", "--output", str(parcial)], proj)
        salvar_texto(proj / "render.log", log)
        if codigo != 0:
            raise ErroRender(f"render falhou (código {codigo}): {log[-CAUDA:]}")
        if not parcial.exists() or parcial.stat().st_size == 0:
            raise ErroRender(f"render terminou sem gerar {parcial.name}: {log[-CAUDA:]}")
    except ErroRender:
        parcial.unlink(missing_ok=True)
        raise
    parcial.replace(saida)
