"""f3 Motion, o cache das cenas em `cortes/<n>/motion/cenas.json` e a etapa do corte (plano
2026-10-03-motion; estilo denso: spec 2026-10-15-f3-denso §6, §10).

A chave é a mesma do B-roll (render/ilustracao_cache.py): início, fim e o hash do texto das
palavras do prompt. Corrigir uma palavra da legenda muda o hash e chama o LLM de novo; refazer o
trecho apaga a pasta (pipeline). Guardam-se as cenas e as descartadas, com o motivo: o editor
mostra as duas. Sem nenhuma cena válida o render para com erro claro, e o próximo dá o mesmo erro
a partir do cache, sem gastar LLM.

Formato 2 (estilo denso): guarda também o tema que o LLM escolheu. Cache do formato 1 (o f3 antigo)
é ignorado e refeito na próxima prévia — o template novo não sabe desenhar as cenas antigas. A
etapa devolve o `Motion`: as cenas, o tema efetivo (o do editor, se houver) e o SVG de cada
ilustração, ou o motivo de não ter (render/motion_svg.py).
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cortes.detector import ChamarLLM
from cortes.episodio import ler_json, salvar_json
from cortes.llm import ErroLLM
from cortes.render.ilustracao_cache import Chave, chave_de
from cortes.render.motion import Cena, Resultado, cenas_do_corte
from cortes.render.motion_params import ErroParams, Ilustracao, ler_params, params_json
from cortes.render.motion_prompt import Contexto
from cortes.render.motion_ritmo import Descartada
from cortes.render.motion_svg import svg_da_cena
from cortes.render.motion_tema import TEMAS
from cortes.render.processo import ErroRender
from cortes.tipos import Palavra

PASTA = "motion"
ARQUIVO = "cenas.json"
FORMATO = 2
_SEM_PAINEL = ("capa", "respiro")
NENHUMA = "nada neste trecho vira painel — use outro formato"


@dataclass(frozen=True)
class Motion:
    """O que o template do f3 precisa: as cenas, o tema e os desenhos das ilustrações."""
    cenas: list[Cena]
    tema: str
    svgs: dict[int, str] = field(default_factory=dict)          # k da cena → SVG sanitizado
    falhas_svg: dict[int, str] = field(default_factory=dict)    # k da cena → por que não tem


@dataclass(frozen=True)
class CacheMotion:
    chave: Chave
    resultado: Resultado


def _cena_json(c: Cena) -> dict[str, Any]:
    return {"k": c.k, "componente": c.componente, "inicio": c.inicio, "fim": c.fim,
            "params": params_json(c.params), "batidas": list(c.batidas)}


def _descartada_json(d: Descartada) -> dict[str, Any]:
    return {"componente": d.componente, "inicio": d.inicio, "fim": d.fim, "params": d.params,
            "motivo": d.motivo}


def _cena(b: dict[str, Any]) -> Cena:
    return Cena(int(b["k"]), str(b["componente"]), float(b["inicio"]), float(b["fim"]),
                ler_params(str(b["componente"]), b["params"]), tuple(float(t) for t in b["batidas"]))


def _descartada(b: dict[str, Any]) -> Descartada:
    return Descartada(str(b["componente"]), float(b["inicio"]), float(b["fim"]), b["params"],
                      str(b["motivo"]))


def gravar_cenas(d_corte: Path, chave: Chave, r: Resultado) -> None:
    (d_corte / PASTA).mkdir(parents=True, exist_ok=True)
    salvar_json(d_corte / PASTA / ARQUIVO, {
        "formato": FORMATO, "chave": {"inicio": chave.inicio, "fim": chave.fim, "texto": chave.texto},
        "tema": r.tema,
        "cenas": [_cena_json(c) for c in r.cenas],
        "descartadas": [_descartada_json(d) for d in r.descartadas]})


def ler_cenas(d_corte: Path) -> CacheMotion | None:
    """O cache, ou None se não há (ou é de outro formato). Cache malformado é erro claro."""
    arq = d_corte / PASTA / ARQUIVO
    if not arq.exists():
        return None
    try:
        b = ler_json(arq)
        if not isinstance(b, dict) or b.get("formato") != FORMATO:
            return None
        ch = b["chave"]
        chave = Chave(float(ch["inicio"]), float(ch["fim"]), str(ch["texto"]))
        if b["tema"] not in TEMAS:
            raise ValueError(f"tema {b['tema']!r} desconhecido")
        return CacheMotion(chave, Resultado([_cena(c) for c in b["cenas"]],
                                            [_descartada(d) for d in b["descartadas"]], str(b["tema"])))
    except (KeyError, TypeError, ValueError, ErroParams) as e:
        raise ErroRender(f"{arq}: cache do motion inválido ({e!r}); refaça o motion") from e


def _sem_cena(r: Resultado) -> ErroRender:
    motivos = "; ".join(f"{d.componente} em {d.inicio:.1f}s: {d.motivo}" for d in r.descartadas)
    return ErroRender(NENHUMA + (f" (descartadas: {motivos})" if motivos else ""))


def _desenhos(d_corte: Path, cenas: list[Cena], palavras: list[Palavra], tema: str,
              chamar: ChamarLLM) -> tuple[dict[int, str], dict[int, str]]:
    svgs, falhas = {}, {}
    for c in cenas:
        if isinstance(c.params, Ilustracao):
            ditos = [w.texto for w in palavras if w.inicio < c.fim]
            svg, motivo = svg_da_cena(d_corte, c.k, c.params, tema, ditos, chamar)
            if svg is not None:
                svgs[c.k] = svg
            else:
                falhas[c.k] = motivo or "sem desenho"
    return svgs, falhas


def preparar_cenas(d_corte: Path, ini: float, fim: float, palavras: list[Palavra], dur: float,
                   chamar: ChamarLLM, contexto: Contexto, tema_editor: str | None = None) -> Motion:
    """As cenas do corte, do cache quando início, fim e texto não mudaram. `palavras` no tempo do
    trecho sem pausas, sem máscara; `dur` é a duração desse trecho. `tema_editor` (Edicoes.tema)
    vale sobre o do LLM e não muda as cenas — só o HTML e os desenhos."""
    chave = chave_de(ini, fim, palavras)
    lido = ler_cenas(d_corte)
    if lido is not None and lido.chave == chave:
        r = lido.resultado
    else:
        try:
            r = cenas_do_corte(palavras, dur, chamar, contexto)
        except ErroLLM as e:
            raise ErroRender(f"Motion: {e}") from e
        gravar_cenas(d_corte, chave, r)
    if not any(c.componente not in _SEM_PAINEL for c in r.cenas):
        raise _sem_cena(r)
    tema = tema_editor or r.tema
    svgs, falhas = _desenhos(d_corte, r.cenas, palavras, tema, chamar)
    return Motion(r.cenas, tema, svgs, falhas)


def contexto_do_meta(pasta_ep: Path) -> Contexto:
    """Título e canal do episódio (`meta.json`, gravado no download) para a capa do f3."""
    arq = pasta_ep / "meta.json"
    if not arq.exists():
        raise ErroRender(f"{arq} não existe: o f3 precisa do título e do canal do episódio")
    meta = ler_json(arq)
    campos = {k: meta.get(k) if isinstance(meta, dict) else None for k in ("titulo", "canal")}
    if not all(isinstance(v, str) and v.strip() for v in campos.values()):
        raise ErroRender(f"{arq}: 'titulo' e 'canal' deveriam ser texto, vieram {campos}")
    return Contexto(str(campos["titulo"]), str(campos["canal"]))
