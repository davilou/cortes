"""index.html do Short a partir do template do formato (puro; spec produção §4.1, §9)."""
import html
import json
import re
from pathlib import Path

from cortes.render.legenda import Grupo, legenda_html
from cortes.render.processo import ErroRender
from cortes.render.rosto import (
    ALVO_METADE,
    JANELA_METADE,
    Rosto,
    escala_metade,
    largura_quadro,
    quadro_metade,
    trilha_fixa,
)

FORMATOS = ("f7", "f1", "f6", "f5", "f8")   # ordem da tela; planos D e E acrescentam f4 e f3
_TEMPLATES = {"f7": "conversa", "f1": "falante", "f6": "hormozi", "f5": "gameplay", "f8": "desfoque"}
_POR_PALAVRA = ("f6",)
_PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")


def caminho_template(raiz: Path, formato: str) -> Path:
    if formato not in _TEMPLATES:
        raise ErroRender(f"formato '{formato}' sem template; use um de {FORMATOS}")
    return raiz / "render" / "formatos" / f"{_TEMPLATES[formato]}.tpl"


def montar_html(tpl: str, valores: dict[str, str]) -> str:
    """Uma passada só: o texto de um valor (ex.: legenda com `{{` literal) não é reprocessado
    como placeholder, diferente de substituir chave por chave em sequência."""
    faltando: set[str] = set()

    def _troca(m: re.Match[str]) -> str:
        chave = m.group(0)[2:-2]
        if chave not in valores:
            faltando.add(m.group(0))
            return m.group(0)
        return valores[chave]

    saida = _PLACEHOLDER.sub(_troca, tpl)
    if faltando:
        raise ErroRender(f"placeholders sem valor: {sorted(faltando)}")
    return saida


def valores(dur: float, rosto: Rosto, grupos: list[Grupo], escolhas: dict[int, int], formato: str,
            titulo: str) -> dict[str, str]:
    """Superconjunto dos placeholders de todos os templates: valor sobrando não é erro, só o que
    falta (`montar_html`)."""
    qm_w, qm_h = quadro_metade(rosto)
    metade = trilha_fixa(rosto, escolhas, JANELA_METADE, ALVO_METADE, escala_metade(rosto))
    return {"DUR": str(round(dur, 2)), "QW": str(largura_quadro(rosto)),
            "LEGENDAS": legenda_html(grupos, por_palavra=formato in _POR_PALAVRA),
            "TRILHA_CHEIO": json.dumps(trilha_fixa(rosto, escolhas)), "TRILHA_METADE": json.dumps(metade),
            "QM_W": str(qm_w), "QM_H": str(qm_h), "TITULO": html.escape(titulo)}
