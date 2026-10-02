"""index.html do Short a partir do template do formato (puro; spec produção §4.1, §9)."""
import json
import re
from pathlib import Path

from cortes.render.legenda import Grupo, legenda_html
from cortes.render.processo import ErroRender
from cortes.render.rosto import Rosto, largura_quadro, trilha_fixa

FORMATOS = ("f7", "f1")   # ordem da tela; planos D e E acrescentam f4 e f3
_TEMPLATES = {"f7": "conversa", "f1": "falante"}
_PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")


def caminho_template(raiz: Path, formato: str) -> Path:
    if formato not in _TEMPLATES:
        raise ErroRender(f"formato '{formato}' sem template; use um de {FORMATOS}")
    return raiz / "render" / "formatos" / f"{_TEMPLATES[formato]}.tpl"


def montar_html(tpl: str, valores: dict[str, str]) -> str:
    html = tpl
    for k, v in valores.items():
        html = html.replace("{{" + k + "}}", v)
    if sobra := _PLACEHOLDER.findall(html):
        raise ErroRender(f"placeholders sem valor: {sorted(set(sobra))}")
    return html


def valores(dur: float, rosto: Rosto, grupos: list[Grupo], cortes: list[float]) -> dict[str, str]:
    return {"DUR": str(round(dur, 2)), "QW": str(largura_quadro(rosto)), "LEGENDAS": legenda_html(grupos),
            "TRILHA_CHEIO": json.dumps(trilha_fixa(rosto)), "CORTES": json.dumps(cortes)}
