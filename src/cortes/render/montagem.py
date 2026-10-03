"""index.html do Short a partir do template do formato (puro; spec produção §4.1, §9)."""
import html
import json
import re
from collections.abc import Sequence
from pathlib import Path

from cortes.render.ilustracao_etapa import Ilustracao, nome_asset
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

FORMATOS = ("f7", "f1", "f6", "f5", "f8", "f9")   # ordem da tela; planos D e E acrescentam f4 e f3
_TEMPLATES = {"f7": "conversa", "f1": "falante", "f6": "hormozi", "f5": "gameplay", "f8": "desfoque",
              "f9": "ilustrado"}
_POR_PALAVRA = ("f6",)
_PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")
FADE_CARTAO_S = 0.15   # a entrada e a saída do cartão no ilustrado.tpl
_PLACEHOLDERS_ROSTO = {"QW", "TRILHA_CHEIO", "QM_W", "QM_H", "TRILHA_METADE"}


def caminho_template(raiz: Path, formato: str) -> Path:
    if formato not in _TEMPLATES:
        raise ErroRender(f"formato '{formato}' sem template; use um de {FORMATOS}")
    return raiz / "render" / "formatos" / f"{_TEMPLATES[formato]}.tpl"


def _placeholders(tpl: str) -> set[str]:
    return {m[2:-2] for m in _PLACEHOLDER.findall(tpl)}


def usa_rosto(tpl: str) -> bool:
    """Se o template usa algum placeholder de câmera ou metade — os únicos que dependem de rosto
    medido. f8 (desfoque) não usa nenhum: medir rosto para ele é custo (e risco de falha) à toa."""
    return bool(_placeholders(tpl) & _PLACEHOLDERS_ROSTO)


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


def imagens_html(ilustracoes: Sequence[Ilustracao], dur: float) -> str:
    """Um cartão por ilustração com imagem (f9). A deixa sem imagem não vira cartão, nem a que não
    cabe antes do fim do Short (menos que a entrada e a saída de 0,15 s cada)."""
    cartoes = []
    for i in ilustracoes:
        ini = round(i.deixa.inicio, 2)
        dur_cartao = round(min(i.deixa.fim, dur) - ini, 2)
        if i.imagem is None or dur_cartao < 2 * FADE_CARTAO_S:
            continue
        cartoes.append(
            f'      <div class="clip ilus" id="ilus-{i.k}" data-start="{ini}" data-duration="{dur_cartao}" '
            f'data-track-index="15"><img src="assets/{nome_asset(i.k)}" '
            f'alt="{html.escape(i.deixa.coisa, quote=True)}"></div>')
    return "\n".join(cartoes)


def valores(tpl: str, dur: float, rosto: Rosto | None, grupos: list[Grupo], escolhas: dict[int, int],
            formato: str, titulo: str, ilustracoes: Sequence[Ilustracao] = ()) -> dict[str, str]:
    """Só os placeholders que `tpl` realmente usa: f8 (desfoque) não tem câmera nem metade, e
    calcular `TRILHA_CHEIO`/`TRILHA_METADE` ali exigiria rosto e escolhas válidas à toa — custo e
    chance de erro que o template nunca usa (revisão formatos novos, item 1). `rosto=None` só vale
    quando `usa_rosto(tpl)` é falso — o chamador (pipeline._html) garante isso."""
    usa = _placeholders(tpl)
    out = {"DUR": str(round(dur, 2)), "LEGENDAS": legenda_html(grupos, por_palavra=formato in _POR_PALAVRA),
           "TITULO": html.escape(titulo)}
    if "IMAGENS" in usa:
        out["IMAGENS"] = imagens_html(ilustracoes, dur)
    if usa & _PLACEHOLDERS_ROSTO:
        if rosto is None:
            raise ErroRender(f"formato '{formato}' usa rosto no template mas nenhum foi medido")
        if "QW" in usa:
            out["QW"] = str(largura_quadro(rosto))
        if "TRILHA_CHEIO" in usa:
            out["TRILHA_CHEIO"] = json.dumps(trilha_fixa(rosto, escolhas))
        if "QM_W" in usa or "QM_H" in usa:
            qm_w, qm_h = quadro_metade(rosto)
            out["QM_W"], out["QM_H"] = str(qm_w), str(qm_h)
        if "TRILHA_METADE" in usa:
            metade = trilha_fixa(rosto, escolhas, JANELA_METADE, ALVO_METADE, escala_metade(rosto))
            out["TRILHA_METADE"] = json.dumps(metade)
    return out
