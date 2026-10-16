"""f3 Motion, a ilustração em SVG livre (spec 2026-10-15-f3-denso §6).

Para cada cena `ilustracao`, uma chamada `claude -p` à parte desenha o que a `descricao` pede, nas
cores do tema. O SVG do LLM nunca vai para o HTML como veio: `sanitizar` (puro) lê o XML, recusa
o que sai da lista branca e escreve um SVG novo só com o permitido — ids prefixados por cena (dois
desenhos na mesma página não trocam gradiente), texto escapado, cores só da paleta. Texto com
número que a fala não disse recusa o desenho, como nos painéis.

Recusa ou erro do LLM nunca derrubam o corte: devolvem o motivo, e a cena mostra o ícone
(render/motion_componentes.py). Cache em `motion/svg/<k>.json` pela descrição e o tema; erro de LLM
não é guardado (a próxima prévia tenta de novo), recusa é (o mesmo pedido daria outra resposta,
mas gastaria LLM a cada prévia).
"""
import html
import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from cortes.detector import ChamarLLM
from cortes.episodio import ler_json, salvar_json
from cortes.llm import ErroLLM
from cortes.render.motion_numeros import nao_ditos, numeros_da_fala
from cortes.render.motion_params import Ilustracao
from cortes.render.motion_tema import cores_do_tema, paleta

PASTA = Path("motion") / "svg"
MODELO_SVG = "sonnet"
VIEWBOX = "0 0 1000 700"
MAX_BYTES = 8000
MAX_ELEMENTOS = 400
ELEMENTOS = frozenset({"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
                       "text", "tspan", "defs", "linearGradient", "radialGradient", "stop"})
_GEOMETRIA = {"d", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "width", "height",
              "points", "fx", "fy", "dx", "dy", "offset"}
_ESTILO = {"stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "opacity",
           "fill-opacity", "stroke-opacity", "stop-opacity", "font-size", "font-weight", "text-anchor",
           "dominant-baseline", "letter-spacing", "transform", "gradientUnits", "gradientTransform"}
_CORES = {"fill", "stroke", "stop-color"}
ATRIBUTOS = frozenset(_GEOMETRIA | _ESTILO | _CORES | {"id"})
_VALOR = re.compile(r"^[\w\s.,()#%+\-]*$")
_ID = re.compile(r"^[A-Za-z][\w-]{0,60}$")
_URL = re.compile(r"^url\(#([A-Za-z][\w-]{0,60})\)$")
_XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>")
# inofensivos e comuns no SVG de LLM: saem em silêncio em vez de recusar o desenho (revisão final);
# `class`/`font-family` sairiam do tema (o CSS do painel pegaria a classe; a fonte é a do tema)
_DESCARTA_ELEMENTOS = frozenset({"title", "desc", "metadata"})
_DESCARTA_ATRIBUTOS = frozenset({"version", "preserveAspectRatio", "font-family", "class"})
_DESCARTA_NA_RAIZ = frozenset({"viewBox", "width", "height", "x", "y"})

SISTEMA_SVG = ("Você desenha ilustrações simples em SVG para um painel de vídeo. Siga apenas as instruções "
               "desta tarefa e responda somente no schema pedido.")
SCHEMA_SVG: dict[str, Any] = {"type": "object", "additionalProperties": False, "required": ["svg"],
                              "properties": {"svg": {"type": "string", "minLength": 20}}}


class ErroSvg(ValueError):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _cor(nome: str, v: str, cores: frozenset[str], prefixo: str) -> str:
    if v == "none":
        return v
    if m := _URL.match(v):
        return f"url(#{prefixo}{m.group(1)})"
    if "url" in v:
        raise ErroSvg(f"{nome} com url fora do próprio desenho: {v[:60]!r}")
    if v.lower() not in cores:
        raise ErroSvg(f"cor '{v}' fora da paleta do tema em {nome}")
    return v.lower()


def _atributo(nome: str, v: str, cores: frozenset[str], prefixo: str) -> str:
    if nome not in ATRIBUTOS:
        raise ErroSvg(f"atributo '{nome}' não é permitido")
    if nome in _CORES:
        return _cor(nome, v.strip(), cores, prefixo)
    if nome == "id":
        if not _ID.match(v):
            raise ErroSvg(f"id inválido: {v[:40]!r}")
        return prefixo + v
    if not _VALOR.match(v) or "url" in v.lower():
        raise ErroSvg(f"valor estranho em '{nome}': {v[:60]!r}")
    return v


def _escrever(el: ET.Element, cores: frozenset[str], prefixo: str, raiz: bool = False) -> str:
    tag = _local(el.tag)
    if tag not in ELEMENTOS or (tag == "svg") != raiz:
        raise ErroSvg(f"elemento '{tag}' não é permitido aqui")
    attrs = {_local(k): v for k, v in el.attrib.items()
             if _local(k) not in _DESCARTA_ATRIBUTOS and not (raiz and _local(k) in _DESCARTA_NA_RAIZ)}
    partes = [f'{k}="{html.escape(_atributo(k, v, cores, prefixo), quote=True)}"' for k, v in attrs.items()]
    if raiz:
        partes = [f'viewBox="{VIEWBOX}"', 'xmlns="http://www.w3.org/2000/svg"', *partes]
    dentro = html.escape(el.text or "") if tag in ("text", "tspan") else ""
    filhos = "".join(_escrever(f, cores, prefixo) + (html.escape(f.tail or "") if tag == "text" else "")
                     for f in el if _local(f.tag) not in _DESCARTA_ELEMENTOS)
    return f"<{' '.join([tag, *partes])}>{dentro}{filhos}</{tag}>"


def _ler(svg: str) -> ET.Element:
    if len(svg.encode("utf-8")) > MAX_BYTES:
        raise ErroSvg(f"SVG com mais de {MAX_BYTES // 1000} KB")
    corpo = _XML_DECL.sub("", svg, count=1)
    if "<!" in corpo.replace("<!--", "", corpo.count("<!--")) or "<?" in corpo:
        raise ErroSvg("SVG com DOCTYPE, ENTITY ou instrução de processamento")
    try:
        raiz = ET.fromstring(corpo)
    except ET.ParseError as e:
        raise ErroSvg(f"XML inválido: {e}") from e
    if _local(raiz.tag) != "svg":
        raise ErroSvg(f"a raiz deveria ser svg, veio {_local(raiz.tag)!r}")
    if " ".join(raiz.get("viewBox", "").replace(",", " ").split()) != VIEWBOX:
        raise ErroSvg(f"viewBox deveria ser {VIEWBOX!r}, veio {raiz.get('viewBox')!r}")
    if sum(1 for _ in raiz.iter()) > MAX_ELEMENTOS:
        raise ErroSvg(f"SVG com mais de {MAX_ELEMENTOS} elementos")
    return raiz


def sanitizar(svg: str, cores: frozenset[str], prefixo: str) -> str:
    """O SVG reescrito só com o permitido, ou ErroSvg com o motivo."""
    return _escrever(_ler(svg), cores, prefixo, raiz=True)


def textos_svg(svg: str) -> list[str]:
    """O texto inteiro de cada <text>, com os <tspan> e o que vem depois deles (revisão final: um
    número depois do tspan escapava da regra)."""
    return [t for el in ET.fromstring(svg).iter() if _local(el.tag) == "text"
            for t in [" ".join("".join(el.itertext()).split())] if t]


def prompt_svg(il: Ilustracao, tema: str) -> str:
    p = paleta(tema)
    return f"""Desenhe em SVG: {il.descricao}

Regras:
- Raiz <svg viewBox="{VIEWBOX}">; o desenho ocupa o quadro com margem de 40.
- Estilo de ilustração plana e limpa, como um painel de aplicativo: formas grandes e legíveis num \
celular, traço de 4 a 10, cantos arredondados; esquemático, não fotográfico.
- Só estas cores (fill, stroke, stop-color): fundo do cartão {p.cartao}, linhas {p.linha}, texto \
{p.texto}, suave {p.suave}, destaque {p.acento}, alerta {p.perda}; ou "none". Gradiente só com \
<linearGradient>/<radialGradient> em <defs>, referenciado por url(#id).
- Elementos permitidos: g, path, rect, circle, ellipse, line, polyline, polygon, text, tspan, defs, \
linearGradient, radialGradient, stop. Nada de style, class, script, image, use, foreignObject, \
links ou eventos.
- Atributos permitidos: geometria (d, x, y, x1, y1, x2, y2, cx, cy, r, rx, ry, width, height, \
points, fx, fy, dx, dy, offset), fill, stroke, stop-color, stroke-width, stroke-linecap, \
stroke-linejoin, stroke-dasharray, opacity, fill-opacity, stroke-opacity, stop-opacity, font-size, \
font-weight, text-anchor, dominant-baseline, letter-spacing, transform, gradientUnits, \
gradientTransform, id (até 60 letras). Sem font-family (a fonte é a do vídeo).
- No máximo 3 textos curtos (até 20 caracteres) e SEM números.
- Até 60 elementos e 7 KB."""


def _numeros(svg: str, ditos: Sequence[str]) -> str | None:
    if faltam := nao_ditos(textos_svg(svg), numeros_da_fala(list(ditos))):
        return f"número que a fala não disse no desenho: {', '.join(faltam)}"
    return None


def _chave(il: Ilustracao, tema: str) -> dict[str, str]:
    return {"descricao": il.descricao, "tema": tema}


def falha_guardada(d_corte: Path, k: int, il: Ilustracao, tema: str) -> str | None:
    """O motivo guardado de a ilustração `k` não ter desenho (para o editor), só se o guardado é
    desta mesma descrição e tema; senão None."""
    arq = d_corte / PASTA / f"{k}.json"
    if not arq.exists() or (lido := ler_json(arq)).get("chave") != _chave(il, tema):
        return None
    motivo = lido.get("motivo")
    return str(motivo) if motivo is not None else None


def _desenhar(il: Ilustracao, k: int, tema: str, chamar: ChamarLLM) -> tuple[str | None, str | None]:
    cru = chamar(prompt_svg(il, tema), SCHEMA_SVG, SISTEMA_SVG, MODELO_SVG)["svg"]
    try:
        return sanitizar(str(cru), cores_do_tema(tema), f"s{k}-"), None
    except ErroSvg as e:
        return None, f"SVG recusado: {e}"


def svg_da_cena(d_corte: Path, k: int, il: Ilustracao, tema: str, ditos: Sequence[str],
                chamar: ChamarLLM) -> tuple[str | None, str | None]:
    """(svg, None) ou (None, motivo). `ditos`: as palavras faladas até o fim da cena. O cache guarda
    o desenho sanitizado (ou o motivo da recusa) pela descrição e o tema; os números são conferidos
    a cada vez contra a fala atual — corrigir a legenda não deixa passar número que deixou de ser dito."""
    arq = d_corte / PASTA / f"{k}.json"
    if arq.exists() and (lido := ler_json(arq)).get("chave") == _chave(il, tema):
        svg, motivo = lido["svg"], lido["motivo"]
    else:
        try:
            svg, motivo = _desenhar(il, k, tema, chamar)
        except ErroLLM as e:
            return None, f"LLM: {e}"
        arq.parent.mkdir(parents=True, exist_ok=True)
        salvar_json(arq, {"chave": _chave(il, tema), "svg": svg, "motivo": motivo})
    if svg is None:
        return None, motivo
    return (None, m) if (m := _numeros(svg, ditos)) else (svg, None)
