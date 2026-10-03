"""f3 Motion, os parâmetros de cada componente (plano 2026-10-03-motion): tipados, validados e com
o texto que vai para a tela (base da regra dos números). Puro.

O schema do LLM não sabe qual campo cada componente exige; quem confere é `ler_params`, que recusa
com o motivo (campo ausente, tipo errado, texto longo demais para o layout). Os limites de texto
vêm do layout do protótipo (testes/short-400mil-dinamica/modelo.tpl): passou deles, o texto
quebra em linhas demais e invade a legenda ou o rosto.
"""
import json
import math
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Literal

Estado = Literal["cheio", "div"]
COMPONENTES: tuple[str, ...] = ("capa", "contador", "valor_cheio", "comparacao", "chat", "lista", "rota")
# div: o painel numa faixa em cima e o rosto embaixo; cheio: o cartão na tela inteira (a capa fica
# por cima do rosto escurecido, também em tela cheia)
ESTADO: dict[str, Estado] = {"capa": "cheio", "contador": "div", "valor_cheio": "cheio",
                             "comparacao": "cheio", "chat": "div", "lista": "div", "rota": "div"}
LIMITES = {"rotulo": 28, "titulo": 42, "destaque": 16, "prefixo": 4, "sufixo": 8, "marco": 10,
           "selo": 24, "valor_texto": 14, "carimbo": 18, "app": 16, "pergunta": 90,
           "titulo_lista": 34, "item": 20, "lugar": 14}
ITENS_MIN, ITENS_MAX = 2, 4
VALOR_MAX = 1e12


class ErroParams(ValueError):
    pass


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
class ValorCheio:
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


Params = Capa | Contador | ValorCheio | Comparacao | Chat | Lista | Rota


def _texto(d: dict[str, Any], campo: str, limite: str, opcional: bool = False) -> Any:
    v = d.get(campo)
    if v is None and opcional:
        return None
    if not isinstance(v, str) or not v.strip():
        raise ErroParams(f"'{campo}' deveria ser texto não vazio, veio {v!r}")
    v = " ".join(v.split())
    if len(v) > LIMITES[limite]:
        raise ErroParams(f"'{campo}' com {len(v)} caracteres (máximo {LIMITES[limite]}): {v!r}")
    return v


def _afixo(d: dict[str, Any], campo: str) -> str:
    v = d.get(campo, "")
    if not isinstance(v, str) or len(v) > LIMITES[campo]:
        raise ErroParams(f"'{campo}' deveria ser texto de até {LIMITES[campo]} caracteres, veio {v!r}")
    return v


def _numero(d: dict[str, Any], campo: str, opcional: bool = False) -> Any:
    v = d.get(campo)
    if v is None and opcional:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ErroParams(f"'{campo}' deveria ser número, veio {v!r}")
    if not 0 <= v <= VALOR_MAX:
        raise ErroParams(f"'{campo}' fora de 0 a {VALOR_MAX:.0e}: {v!r}")
    return float(v)


def _lista(d: dict[str, Any], campo: str, n_min: int, n_max: int) -> list[Any]:
    v = d.get(campo)
    if not isinstance(v, list) or not n_min <= len(v) <= n_max:
        raise ErroParams(f"'{campo}' deveria ser lista de {n_min} a {n_max} itens, veio {v!r}")
    return v


def _capa(d: dict[str, Any]) -> Capa:
    titulo, destaque = _texto(d, "titulo", "titulo"), _texto(d, "destaque", "destaque")
    if destaque.lower() not in re.findall(r"\w+", titulo.lower()):
        raise ErroParams(f"destaque {destaque!r} não é uma palavra do título {titulo!r}")
    return Capa(_texto(d, "rotulo", "rotulo"), titulo, destaque)


def _contador(d: dict[str, Any]) -> Contador:
    m = d.get("marcos")
    marcos = None
    if m is not None:
        de, ate = _lista(d, "marcos", 2, 2)
        marcos = (_texto({"marco": de}, "marco", "marco"), _texto({"marco": ate}, "marco", "marco"))
    return Contador(_texto(d, "rotulo", "rotulo"), _numero(d, "valor"), _afixo(d, "prefixo"),
                    _afixo(d, "sufixo"), marcos)


def _valor_cheio(d: dict[str, Any]) -> ValorCheio:
    valor, de = _numero(d, "valor"), _numero(d, "de", opcional=True)
    if de is not None and de >= valor:
        raise ErroParams(f"'de' ({de}) deveria ser menor que 'valor' ({valor})")
    return ValorCheio(_texto(d, "rotulo", "rotulo"), valor, de, _afixo(d, "prefixo"), _afixo(d, "sufixo"),
                      _texto(d, "selo", "selo", opcional=True))


def _coluna(c: Any) -> Coluna:
    if not isinstance(c, dict):
        raise ErroParams(f"coluna deveria ser objeto, veio {c!r}")
    alt = _numero(c, "altura_rel")
    if not 0 < alt <= 1:
        raise ErroParams(f"'altura_rel' deveria estar em (0, 1], veio {alt}")
    return Coluna(_texto(c, "rotulo", "rotulo"), _texto(c, "valor_texto", "valor_texto"), alt)


def _comparacao(d: dict[str, Any]) -> Comparacao:
    a, b = (_coluna(c) for c in _lista(d, "colunas", 2, 2))
    return Comparacao((a, b), _texto(d, "carimbo", "carimbo", opcional=True))


def _lista_c(d: dict[str, Any]) -> Lista:
    itens = _lista(d, "itens", ITENS_MIN, ITENS_MAX)
    return Lista(_texto(d, "titulo", "titulo_lista"),
                 tuple(_texto({"item": i}, "item", "item") for i in itens))


def _chat(d: dict[str, Any]) -> Chat:
    return Chat(_texto(d, "app", "app"), _texto(d, "pergunta", "pergunta"))


def _rota(d: dict[str, Any]) -> Rota:
    return Rota(_texto(d, "origem", "lugar"), _texto(d, "destino", "lugar"),
                _texto(d, "selo", "selo", opcional=True))


_LEITORES: dict[str, Callable[[dict[str, Any]], Params]] = {
    "capa": _capa, "contador": _contador, "valor_cheio": _valor_cheio, "comparacao": _comparacao,
    "chat": _chat, "lista": _lista_c, "rota": _rota,
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


def formatar(v: float) -> str:
    """Como o número aparece na tela (pt-BR): 1500 → "1.500", 37.5 → "37,5"."""
    inteiro = f"{int(v):,}".replace(",", ".")
    frac = f"{v:.2f}".split(".")[1].rstrip("0")
    return f"{inteiro},{frac}" if frac else inteiro


def casas(v: float) -> int:
    return len(f"{v:.2f}".split(".")[1].rstrip("0"))


def _com_afixos(prefixo: str, v: float, sufixo: str) -> str:
    return f"{prefixo} {formatar(v)} {sufixo}".strip()


def textos_da_tela(p: Params) -> list[str]:
    """Tudo que aparece escrito: é o que a regra dos números confere."""
    match p:
        case Capa():
            return [p.rotulo, p.titulo]
        case Contador():
            return [p.rotulo, _com_afixos(p.prefixo, p.valor, p.sufixo), *(p.marcos or ())]
        case ValorCheio():
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


def batidas(p: Params) -> list[str]:
    """Os textos que entram no instante em que são ditos (um item da lista, o destino da rota, o
    selo); o resto entra com a cena."""
    match p:
        case Contador():
            return [p.marcos[1]] if p.marcos else []
        case ValorCheio():
            return [p.selo] if p.selo else []
        case Comparacao():
            return [p.carimbo] if p.carimbo else []
        case Lista():
            return list(p.itens)
        case Rota():
            return [p.destino, *([p.selo] if p.selo else [])]
        case _:
            return []
