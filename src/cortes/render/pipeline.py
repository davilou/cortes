"""Render de um corte, do trecho ao MP4 (spec produção §4.1).

Trecho e rosto são caros e só dependem de início/fim: ficam gravados com `recorte.json` como
marcador, que é escrito por último. Se início/fim mudarem (editor, plano C), os dois são refeitos,
e os assets do formato (fundo do f8, gameplay do f5; render/assets.py) são apagados e refeitos.
O f9 (Ilustrado) tem ainda a etapa de ilustração (render/ilustracao_etapa.py), com cache em
`ilustracao/`, apagada junto quando o trecho é refeito.
`montar_projeto` (trecho + rosto + index.html com as edições) é o que a prévia do editor mostra;
`renderizar_corte` chama `montar_projeto` e depois gera o MP4.
"""
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cortes.detector import ChamarLLM, chamar_llm_real
from cortes.episodio import ler_json, salvar_json
from cortes.render.assets import apagar_assets, preparar_assets
from cortes.render.corte import Corte, pasta_corte
from cortes.render.edicao import palavras_editadas
from cortes.render.hyperframes import criar_projeto, renderizar
from cortes.render.ilustracao_conferencia import ChamarComRead, chamar_com_read_real
from cortes.render.ilustracao_etapa import PASTA as PASTA_ILUSTRACAO
from cortes.render.ilustracao_etapa import DepIlustracao, Ilustracao, ilustrar
from cortes.render.ilustracao_imagens import BuscaImagens, ddgs_real, rodar_download_real
from cortes.render.legenda import grupos, palavras_do_corte
from cortes.render.montagem import caminho_template, montar_html, usa_rosto, valores
from cortes.render.processo import ErroRender, Rodar, rodar_processo
from cortes.render.recorte import (
    LerAudio,
    Segmento,
    duracao,
    ler_trecho_wav,
    palavras_sem_pausa,
    recortar,
    segmentos_sem_pausa,
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
    chamar_llm: ChamarLLM = chamar_llm_real                    # deixas do f9
    chamar_llm_com_read: ChamarComRead = chamar_com_read_real  # conferência visual do f9
    ddgs: Callable[[], BuscaImagens] = ddgs_real               # busca de imagens do f9
    rodar_download: Rodar = rodar_download_real                # download das imagens do f9 (30 s)


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
    # quadros e ilustrações do trecho anterior: o trecho mudou, eles não valem mais
    for velha in (d / "miniaturas", d / PASTA_ILUSTRACAO):
        if velha.exists():
            shutil.rmtree(velha)
    apagar_assets(trecho.parent)   # fundo e gameplay saem do trecho (e da duração) anterior
    recortar(pasta_ep / "video.mp4", trecho, ini, segs, dep.rodar)
    _medir_rosto_se_possivel(trecho, d / "rosto.json", raiz, c.formato, dep)
    salvar_json(marca, {"inicio": ini, "fim": fim, "segmentos": segs})
    return segs


def _medir_rosto_se_possivel(trecho: Path, destino: Path, raiz: Path, formato: str, dep: DepRender) -> None:
    """Mede sempre que der: o editor deixa trocar de formato depois, e o rosto já medido evita
    remedir nessa troca. Só quando o formato atual não depende de rosto (hoje, f8) é que uma
    falha na medição não impede o Short de render — sem `rosto.json`, o próximo render tenta medir
    de novo (o cache em `_cache_valido` exige o arquivo)."""
    tpl = caminho_template(raiz, formato).read_text(encoding="utf-8")
    try:
        medir_rosto(trecho, destino, raiz / SCRIPT_ROSTO, dep.py_visao, dep.modelo_rosto, dep.rodar)
    except ErroRender:
        if usa_rosto(tpl):
            raise


def _palavras_trecho(pasta_ep: Path, c: Corte, segs: list[Segmento]) -> list[Palavra]:
    """As palavras do corte, com as edições, no tempo do trecho sem pausas (legenda e deixas)."""
    ini, fim = janela(c)
    todas = palavras_editadas([Palavra(**p) for p in ler_json(pasta_ep / "palavras.json")], c.edicoes)
    return palavras_sem_pausa(palavras_do_corte(todas, ini, fim), segs)


def _html(pasta_ep: Path, c: Corte, raiz: Path, segs: list[Segmento], ilus: list[Ilustracao]) -> str:
    ws = _palavras_trecho(pasta_ep, c, segs)
    dur = duracao(segs)
    tpl = caminho_template(raiz, c.formato).read_text(encoding="utf-8")
    rosto = ler_rosto(pasta_corte(pasta_ep, c.indice) / "rosto.json") if usa_rosto(tpl) else None
    return montar_html(tpl, valores(tpl, dur, rosto, grupos(ws, dur), c.edicoes.rostos, c.formato, c.titulo,
                                    ilustracoes=ilus))


def _ilustrar(pasta_ep: Path, c: Corte, segs: list[Segmento], dep: DepRender) -> list[Ilustracao]:
    """Só o f9. Erro de LLM, de folha ou "nada ilustrável" vira ErroRender e o corte fica em erro."""
    if c.formato != "f9":
        return []
    d = pasta_corte(pasta_ep, c.indice)
    ini, fim = janela(c)
    deps = DepIlustracao(dep.chamar_llm, dep.chamar_llm_com_read, dep.ddgs, dep.rodar,
                         dep.rodar_download)
    return ilustrar(d, ini, fim, _palavras_trecho(pasta_ep, c, segs), d / "projeto" / "assets", deps)


def montar_projeto(pasta_ep: Path, c: Corte, raiz: Path, dep: DepRender) -> None:
    """Trecho + rosto (com cache) e o index.html com as edições — o que a prévia do editor mostra
    e o render grava em MP4. Rápido quando início/fim não mudaram (só regera o HTML)."""
    segs = preparar_trecho(pasta_ep, c, raiz, dep)
    proj = pasta_corte(pasta_ep, c.indice) / "projeto"
    preparar_assets(proj / "assets", c.formato, c.indice, duracao(segs), raiz, dep.rodar)
    ilus = _ilustrar(pasta_ep, c, segs, dep)
    criar_projeto(proj, _html(pasta_ep, c, raiz, segs, ilus))


def renderizar_corte(pasta_ep: Path, c: Corte, raiz: Path, dep: DepRender) -> None:
    """Gera cortes/<indice>/short-v<versao+1>.mp4. Falha alto (ErroRender) em qualquer passo."""
    montar_projeto(pasta_ep, c, raiz, dep)
    d = pasta_corte(pasta_ep, c.indice)
    renderizar(d / "projeto", d / f"short-v{c.versao + 1}.mp4", dep.npx, dep.rodar)
