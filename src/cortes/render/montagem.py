"""index.html do Short a partir do template do formato (puro; spec produção §4.1, §9)."""
import html
import json
import re
from collections.abc import Sequence
from pathlib import Path

from cortes.producao.estado import ErroProducao
from cortes.render.conversa import trilha_conversa
from cortes.render.ilustracao_cache import Ilustracao, Midia, nome_asset
from cortes.render.legenda import Grupo, legenda_html
from cortes.render.motion2 import estados_json, plano, sfx, sfx_html
from cortes.render.motion_animacao import animacoes
from cortes.render.motion_cache import Motion
from cortes.render.motion_componentes import cenas_html, estados
from cortes.render.motion_estilo import COMPONENTES_CSS, MOTION_JS
from cortes.render.motion_params import Capa
from cortes.render.motion_tema import TEMA_F10, css_do_tema
from cortes.render.processo import ErroRender
from cortes.render.rosto import (
    ALVO_AVATAR,
    ALVO_CARD,
    ALVO_DIV,
    ALVO_METADE,
    JANELA_AVATAR,
    JANELA_CARD,
    JANELA_DIV,
    JANELA_METADE,
    Rosto,
    escala_avatar,
    escala_div,
    escala_metade,
    largura_quadro,
    quadro_avatar,
    quadro_div,
    quadro_metade,
    trilha_cabeca,
    trilha_fixa,
)

FORMATOS = ("f7", "f1", "f6", "f5", "f8", "f4", "f3", "f10")   # ordem da tela
_TEMPLATES = {"f7": "conversa", "f1": "falante", "f6": "hormozi", "f5": "gameplay", "f8": "desfoque",
              "f4": "broll", "f3": "motion", "f10": "motion2"}
MOTIONS = ("f3", "f10")   # os formatos com as cenas do Claude (render/motion_cache.py)
# o f9 Ilustrado (cartão de foto) virou o f4 B-roll automático (plano 2026-10-03-broll-automatico):
# corte.json antigo em f9 dá este erro, sem conversão silenciosa
F9_SAIU = "o formato f9 virou o f4 B-roll; renderize de novo em f4"
_POR_PALAVRA = ("f6", "f10")
_PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")
CLIPE_MIN_S = 0.3   # clipe que sobra menos que isso antes do fim do Short só pisca: não entra
_PLACEHOLDERS_ROSTO = {"QW", "TRILHA_CHEIO", "TRILHA_CONVERSA", "QM_W", "QM_H", "TRILHA_METADE", "QD_W",
                       "QD_H", "TRILHA_DIV", "TRILHA_CARD", "TRILHA_CABECA", "QA_W", "QA_H", "TRILHA_AVATAR"}


def validar_formato(formato: str) -> None:
    """O formato pedido (episódio novo, render ou edição) renderiza; o f9 diz que virou o f4."""
    if formato == "f9":
        raise ErroProducao(F9_SAIU)
    if formato not in FORMATOS:
        raise ErroProducao(f"formato '{formato}' ainda não renderiza; use um de {FORMATOS}")


def caminho_template(raiz: Path, formato: str) -> Path:
    if formato == "f9":
        raise ErroRender(F9_SAIU)
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


def _clipe(i: Ilustracao, midia: Midia, ini: float, dur: float) -> str:
    attrs = f'id="broll-{i.k}" data-start="{ini}" data-duration="{dur}" data-track-index="15"'
    src = f"assets/{nome_asset(i.k, midia)}"
    if midia == "video":
        return (f'      <video class="clip broll" {attrs} data-media-start="0" src="{src}" muted '
                f'playsinline></video>')
    return (f'      <div class="clip broll" {attrs}><img src="{src}" '
            f'alt="{html.escape(i.deixa.coisa, quote=True)}"></div>')


def broll_html(ilustracoes: Sequence[Ilustracao], dur: float) -> str:
    """Um clipe em tela cheia por deixa com vídeo ou foto (f4). A deixa sem visual não vira clipe,
    nem a que sobra menos de CLIPE_MIN_S antes do fim do Short; a que passa do fim é cortada nele."""
    clipes = []
    for i in ilustracoes:
        ini = round(i.deixa.inicio, 2)
        dur_clipe = round(min(i.deixa.fim, dur) - ini, 2)
        if i.midia is not None and dur_clipe >= CLIPE_MIN_S:
            clipes.append(_clipe(i, i.midia, ini, dur_clipe))
    return "\n".join(clipes)


def _camera(usa: set[str], rosto: Rosto, escolhas: dict[int, int], grupos: list[Grupo],
            dur: float) -> dict[str, str]:
    """Quadro e trilha de cada janela que o template usa: cheia (fixa, ou alternando entre as
    pessoas no f7 — render/conversa.py), metade (f5) e div (f3)."""
    out: dict[str, str] = {}
    if "QW" in usa:
        out["QW"] = str(largura_quadro(rosto))
    if "TRILHA_CHEIO" in usa:
        out["TRILHA_CHEIO"] = json.dumps(trilha_fixa(rosto, escolhas))
    if "TRILHA_CONVERSA" in usa:
        out["TRILHA_CONVERSA"] = json.dumps(trilha_conversa(rosto, escolhas, grupos, dur))
    if "QM_W" in usa or "QM_H" in usa:
        qm_w, qm_h = quadro_metade(rosto)
        out["QM_W"], out["QM_H"] = str(qm_w), str(qm_h)
    if "TRILHA_METADE" in usa:
        metade = trilha_fixa(rosto, escolhas, JANELA_METADE, ALVO_METADE, escala_metade(rosto))
        out["TRILHA_METADE"] = json.dumps(metade)
    if "QD_W" in usa or "QD_H" in usa:
        qd_w, qd_h = quadro_div(rosto)
        out["QD_W"], out["QD_H"] = str(qd_w), str(qd_h)
    if "TRILHA_DIV" in usa:
        out["TRILHA_DIV"] = json.dumps(trilha_fixa(rosto, escolhas, JANELA_DIV, ALVO_DIV, escala_div(rosto)))
    return out | _camera_f10(usa, rosto, escolhas)


def _camera_f10(usa: set[str], rosto: Rosto, escolhas: dict[int, int]) -> dict[str, str]:
    """O card (e a faixa da cabeça por cima dele, com a mesma trilha) e o avatar redondo."""
    out: dict[str, str] = {}
    if "TRILHA_CARD" in usa or "TRILHA_CABECA" in usa:
        card = trilha_fixa(rosto, escolhas, JANELA_CARD, ALVO_CARD, escala_div(rosto))
        out["TRILHA_CARD"], out["TRILHA_CABECA"] = json.dumps(card), json.dumps(trilha_cabeca(card))
    if "QA_W" in usa or "QA_H" in usa:
        qa_w, qa_h = quadro_avatar(rosto)
        out["QA_W"], out["QA_H"] = str(qa_w), str(qa_h)
    if "TRILHA_AVATAR" in usa:
        av = trilha_fixa(rosto, escolhas, JANELA_AVATAR, ALVO_AVATAR, escala_avatar(rosto))
        out["TRILHA_AVATAR"] = json.dumps(av)
    return out


_PLACEHOLDERS_MOTION = {"CENAS", "ESTADOS", "ANIMACOES", "TEMA_CSS", "ROTULO_BASE", "COMPONENTES_CSS",
                        "MOTION_JS", "SFX"}


def _motion(usa: set[str], motion: Motion | None, titulo: str, formato: str, dur: float) -> dict[str, str]:
    """As cenas, o tema e a faixa de base do f3 e do f10 (render/motion_componentes.py, motion2.py;
    spec 2026-10-15-f3-denso). A faixa de base mostra o rótulo da capa quando não há painel; sem
    capa, o título do corte."""
    if not usa & _PLACEHOLDERS_MOTION:
        return {}
    if motion is None:
        raise ErroRender("o template do f3/f10 precisa das cenas do motion, e nenhuma foi preparada")
    capa = next((c.params for c in motion.cenas if isinstance(c.params, Capa)), None)
    rotulo = capa.rotulo if capa else titulo
    comum = {"ANIMACOES": animacoes(motion.cenas), "ROTULO_BASE": html.escape(rotulo),
             "COMPONENTES_CSS": COMPONENTES_CSS, "MOTION_JS": MOTION_JS}
    if formato == "f10":
        p = plano(motion.cenas, dur)
        return comum | {"CENAS": cenas_html(motion.cenas, motion.svgs, p.solo), "ESTADOS": estados_json(p),
                        "TEMA_CSS": css_do_tema(TEMA_F10), "SFX": sfx_html(sfx(motion.cenas, p, dur))}
    return comum | {"CENAS": cenas_html(motion.cenas, motion.svgs), "ESTADOS": estados(motion.cenas),
                    "TEMA_CSS": css_do_tema(motion.tema)}


def valores(tpl: str, dur: float, rosto: Rosto | None, grupos: list[Grupo], escolhas: dict[int, int],
            formato: str, titulo: str, ilustracoes: Sequence[Ilustracao] = (),
            motion: Motion | None = None, trilha: str = "") -> dict[str, str]:
    """Só os placeholders que `tpl` realmente usa: f8 (desfoque) não tem câmera nem metade, e
    calcular `TRILHA_CHEIO`/`TRILHA_METADE` ali exigiria rosto e escolhas válidas à toa — custo e
    chance de erro que o template nunca usa (revisão formatos novos, item 1). `rosto=None` só vale
    quando `usa_rosto(tpl)` é falso — o chamador (pipeline._html) garante isso. `trilha` é o HTML
    dos `<audio>` da cama (render/trilha.py); vazio = sem trilha."""
    usa = _placeholders(tpl)
    out = {"DUR": str(round(dur, 2)), "LEGENDAS": legenda_html(grupos, por_palavra=formato in _POR_PALAVRA),
           "TITULO": html.escape(titulo), "TRILHA": trilha}
    if "BROLL" in usa:
        out["BROLL"] = broll_html(ilustracoes, dur)
    out |= _motion(usa, motion, titulo, formato, dur)
    if usa & _PLACEHOLDERS_ROSTO:
        if rosto is None:
            raise ErroRender(f"formato '{formato}' usa rosto no template mas nenhum foi medido")
        out |= _camera(usa, rosto, escolhas, grupos, dur)
    return out
