"""f3 Motion, os parâmetros de cada componente: tipados, validados e com o texto que vai para a tela
(base da regra dos números). Puro.

O schema do LLM não sabe qual campo cada componente exige; quem confere é `ler_params`, que recusa
com o motivo (campo ausente, tipo errado, texto longo demais para o layout). Os componentes do f3
original (plano 2026-10-03-motion) ficam aqui; os do estilo denso (spec 2026-10-15-f3-denso §5), em
render/motion_params_novos.py; leitores e limites comuns, em render/motion_params_base.py.

Estados (spec §3): `gancho` (capa, rosto cheio com o título), `div` (painel em cima, card do falante
embaixo) e `cheio` (respiro, rosto cheio sem painel). `valor_cheio` virou `valor`, em `div`.
"""
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Literal

from cortes.render.motion_params_base import (
    LIMITES,
    ErroParams,
    afixo,
    casas,
    formatar,
    lista,
    numero,
    objeto,
    texto,
)
from cortes.render.motion_params_novos import (
    LEITORES_NOVOS,
    Check,
    Comodo,
    Destaque,
    Fluxo,
    Grade,
    Grafico,
    Ilustracao,
    Novo,
    Passo,
    Planta,
    Ponto,
    Respiro,
    Timer,
    batidas_novo,
    textos_novo,
)

__all__ = ["LIMITES", "ErroParams", "casas", "formatar", "Check", "Comodo", "Destaque", "Fluxo",
           "Grade", "Grafico", "Ilustracao", "Passo", "Planta", "Ponto", "Respiro", "Timer"]

Estado = Literal["gancho", "div", "cheio"]
COMPONENTES: tuple[str, ...] = ("capa", "contador", "valor", "comparacao", "chat", "lista", "rota",
                                *LEITORES_NOVOS)
ESTADO: dict[str, Estado] = {c: ("gancho" if c == "capa" else "cheio" if c == "respiro" else "div")
                             for c in COMPONENTES}
ITENS_MIN, ITENS_MAX = 2, 4


@dataclass(frozen=True)
class Capa:
    rotulo: str      # quem fala ou o tema, em cima
    titulo: str
    destaque: str    # uma palavra do título, na cor da marca


@dataclass(frozen=True)
class Contador:
    rotulo: str
    valor: float
    prefixo: str = ""
    sufixo: str = ""
    marcos: tuple[str, str] | None = None   # ex.: ("ANO 0", "ANO 10"), com barra de progresso


@dataclass(frozen=True)
class Valor:
    rotulo: str
    valor: float
    de: float | None = None   # a contagem começa aqui (ex.: de 400 a 550); None = 0
    prefixo: str = ""
    sufixo: str = ""
    selo: str | None = None


@dataclass(frozen=True)
class Coluna:
    rotulo: str
    valor_texto: str
    altura_rel: float   # 0 < x ≤ 1: altura da barra relativa à maior


@dataclass(frozen=True)
class Comparacao:
    colunas: tuple[Coluna, Coluna]
    carimbo: str | None = None


@dataclass(frozen=True)
class Chat:
    app: str
    pergunta: str


@dataclass(frozen=True)
class Lista:
    titulo: str
    itens: tuple[str, ...]


@dataclass(frozen=True)
class Rota:
    origem: str
    destino: str
    selo: str | None = None


Params = Capa | Contador | Valor | Comparacao | Chat | Lista | Rota | Novo


def _capa(d: dict[str, Any]) -> Capa:
    titulo, destaque = texto(d, "titulo", "titulo"), texto(d, "destaque", "destaque")
    if destaque.lower() not in re.findall(r"\w+", titulo.lower()):
        raise ErroParams(f"destaque {destaque!r} não é uma palavra do título {titulo!r}")
    return Capa(texto(d, "rotulo", "rotulo"), titulo, destaque)


def _contador(d: dict[str, Any]) -> Contador:
    marcos = None
    if d.get("marcos") is not None:
        de, ate = lista(d, "marcos", 2, 2)
        marcos = (texto({"marco": de}, "marco", "marco"), texto({"marco": ate}, "marco", "marco"))
    return Contador(texto(d, "rotulo", "rotulo"), numero(d, "valor"), afixo(d, "prefixo"),
                    afixo(d, "sufixo"), marcos)


def _valor(d: dict[str, Any]) -> Valor:
    v, de = numero(d, "valor"), numero(d, "de", opcional=True)
    if de is not None and de >= v:
        raise ErroParams(f"'de' ({de}) deveria ser menor que 'valor' ({v})")
    return Valor(texto(d, "rotulo", "rotulo"), v, de, afixo(d, "prefixo"), afixo(d, "sufixo"),
                 texto(d, "selo", "selo", opcional=True))


def _coluna(c: Any) -> Coluna:
    c = objeto(c, "coluna")
    alt = numero(c, "altura_rel")
    if not 0 < alt <= 1:
        raise ErroParams(f"'altura_rel' deveria estar em (0, 1], veio {alt}")
    return Coluna(texto(c, "rotulo", "rotulo"), texto(c, "valor_texto", "valor_texto"), alt)


def _comparacao(d: dict[str, Any]) -> Comparacao:
    a, b = (_coluna(c) for c in lista(d, "colunas", 2, 2))
    return Comparacao((a, b), texto(d, "carimbo", "carimbo", opcional=True))


def _lista(d: dict[str, Any]) -> Lista:
    itens = lista(d, "itens", ITENS_MIN, ITENS_MAX)
    return Lista(texto(d, "titulo", "titulo_lista"), tuple(texto({"item": i}, "item", "item") for i in itens))


def _chat(d: dict[str, Any]) -> Chat:
    return Chat(texto(d, "app", "app"), texto(d, "pergunta", "pergunta"))


def _rota(d: dict[str, Any]) -> Rota:
    return Rota(texto(d, "origem", "lugar"), texto(d, "destino", "lugar"),
                texto(d, "selo", "selo", opcional=True))


_LEITORES: dict[str, Callable[[dict[str, Any]], Params]] = {
    "capa": _capa, "contador": _contador, "valor": _valor, "comparacao": _comparacao,
    "chat": _chat, "lista": _lista, "rota": _rota, **LEITORES_NOVOS,
}


def ler_params(componente: str, d: Any) -> Params:
    """Os parâmetros do componente, ou ErroParams com o motivo."""
    if componente not in _LEITORES:
        raise ErroParams(f"componente {componente!r} não existe; use um de {COMPONENTES}")
    if not isinstance(d, dict):
        raise ErroParams(f"parâmetros deveriam ser objeto, vieram {d!r}")
    return _LEITORES[componente](d)


def params_json(p: Params) -> dict[str, Any]:
    """Para o cache e o editor: tuplas viram listas, como volta do JSON."""
    d: dict[str, Any] = json.loads(json.dumps(asdict(p), ensure_ascii=False))
    return d


def _com_afixos(prefixo: str, v: float, sufixo: str) -> str:
    return f"{prefixo} {formatar(v)} {sufixo}".strip()


def textos_da_tela(p: Params) -> list[str]:
    """Tudo que aparece escrito: é o que a regra dos números confere."""
    match p:
        case Capa():
            return [p.rotulo, p.titulo]
        case Contador():
            return [p.rotulo, _com_afixos(p.prefixo, p.valor, p.sufixo), *(p.marcos or ())]
        case Valor():
            de = [_com_afixos(p.prefixo, p.de, p.sufixo)] if p.de is not None else []
            return [p.rotulo, _com_afixos(p.prefixo, p.valor, p.sufixo), *de, *([p.selo] if p.selo else [])]
        case Comparacao():
            cols = [t for c in p.colunas for t in (c.rotulo, c.valor_texto)]
            return [*cols, *([p.carimbo] if p.carimbo else [])]
        case Chat():
            return [p.app, p.pergunta]
        case Lista():
            return [p.titulo, *p.itens]
        case Rota():
            return [p.origem, p.destino, *([p.selo] if p.selo else [])]
        case _:
            return textos_novo(p)


def batidas(p: Params) -> list[str]:
    """Os textos que entram no instante em que são ditos (um item da lista, o destino da rota, o
    selo); o resto entra com a cena."""
    match p:
        case Contador():
            return [p.marcos[1]] if p.marcos else []
        case Valor():
            return [p.selo] if p.selo else []
        case Comparacao():
            return [p.carimbo] if p.carimbo else []
        case Lista():
            return list(p.itens)
        case Rota():
            return [p.destino, *([p.selo] if p.selo else [])]
        case Capa() | Chat():
            return []
        case _:
            return batidas_novo(p)
