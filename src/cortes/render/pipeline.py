"""Render de um corte, do trecho ao MP4 (spec produção §4.1).

Trecho e rosto são caros e só dependem de início/fim: ficam gravados com `recorte.json` como
marcador, que é escrito por último. Se início/fim mudarem (editor, plano C), os dois são refeitos.
"""
from dataclasses import dataclass
from pathlib import Path

from cortes.episodio import ler_json, salvar_json
from cortes.render.corte import Corte, pasta_corte
from cortes.render.hyperframes import criar_projeto, renderizar
from cortes.render.legenda import grupos, palavras_do_corte
from cortes.render.montagem import caminho_template, montar_html, valores
from cortes.render.processo import ErroRender, Rodar, rodar_processo
from cortes.render.recorte import (
    LerAudio,
    Segmento,
    duracao,
    ler_trecho_wav,
    palavras_sem_pausa,
    recortar,
    segmentos_sem_pausa,
    tempos_de_corte,
)
from cortes.render.rosto import ler_rosto, medir_rosto
from cortes.tipos import Palavra

FOLGA_INICIO = 0.3   # s: folga para o início de palavra estimado. Episódio antigo, com
# palavras.json vindo da legenda do YouTube, começa a palavra ~0,2-0,4 s tarde; com o Whisper
# local é só respiro — o silêncio extra é aparado pela regra de bordas de segmentos_sem_pausa.
SCRIPT_ROSTO = Path("render") / "visao" / "rosto.py"


@dataclass(frozen=True)
class DepRender:
    py_visao: Path
    modelo_rosto: Path
    npx: str
    rodar: Rodar = rodar_processo
    ler_audio: LerAudio = ler_trecho_wav


def janela(c: Corte) -> tuple[float, float]:
    return max(0.0, round(c.inicio - FOLGA_INICIO, 3)), c.fim


def _cache_valido(d: Path, marca: Path, ini: float, fim: float) -> list[Segmento] | None:
    """`recorte.json` só vale como cache se o que ele promete gravar ainda existir: sem
    `trecho.mp4` ou `rosto.json`, um render anterior falhou ou os apagaram, e reaproveitar
    o marcador deixaria o render seguinte sem rosto para ler. Um `rosto.json` de formato velho
    (formato 1, do plano B) também obriga a medir de novo — o editor (plano C) precisa das
    pessoas por plano, que só existem no formato atual."""
    if not marca.exists():
        return None
    if not (d / "projeto" / "assets" / "trecho.mp4").exists() or not (d / "rosto.json").exists():
        return None
    try:
        ler_rosto(d / "rosto.json")
    except ErroRender:
        return None
    r = ler_json(marca)
    if r["inicio"] != ini or r["fim"] != fim:
        return None
    return [(float(a), float(b)) for a, b in r["segmentos"]]


def preparar_trecho(pasta_ep: Path, c: Corte, raiz: Path, dep: DepRender) -> list[Segmento]:
    d = pasta_corte(pasta_ep, c.indice)
    ini, fim = janela(c)
    marca = d / "recorte.json"
    if (segs := _cache_valido(d, marca, ini, fim)) is not None:
        return segs
    segs = segmentos_sem_pausa(dep.ler_audio(pasta_ep / "audio.wav", ini, fim - ini))
    trecho = d / "projeto" / "assets" / "trecho.mp4"
    trecho.parent.mkdir(parents=True, exist_ok=True)
    recortar(pasta_ep / "video.mp4", trecho, ini, segs, dep.rodar)
    medir_rosto(trecho, d / "rosto.json", raiz / SCRIPT_ROSTO, dep.py_visao, dep.modelo_rosto, dep.rodar)
    salvar_json(marca, {"inicio": ini, "fim": fim, "segmentos": segs})
    return segs


def _html(pasta_ep: Path, c: Corte, raiz: Path, segs: list[Segmento]) -> str:
    ini, fim = janela(c)
    todas = [Palavra(**p) for p in ler_json(pasta_ep / "palavras.json")]
    ws = palavras_sem_pausa(palavras_do_corte(todas, ini, fim), segs)
    dur = duracao(segs)
    rosto = ler_rosto(pasta_corte(pasta_ep, c.indice) / "rosto.json")
    tpl = caminho_template(raiz, c.formato).read_text(encoding="utf-8")
    return montar_html(tpl, valores(dur, rosto, grupos(ws, dur), tempos_de_corte(segs), {}))


def renderizar_corte(pasta_ep: Path, c: Corte, raiz: Path, dep: DepRender) -> None:
    """Gera cortes/<indice>/short-v<versao+1>.mp4. Falha alto (ErroRender) em qualquer passo."""
    segs = preparar_trecho(pasta_ep, c, raiz, dep)
    proj = pasta_corte(pasta_ep, c.indice) / "projeto"
    criar_projeto(proj, _html(pasta_ep, c, raiz, segs))
    renderizar(proj, pasta_corte(pasta_ep, c.indice) / f"short-v{c.versao + 1}.mp4", dep.npx, dep.rodar)
