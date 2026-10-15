"""f3 Motion, o que os parâmetros de todos os componentes usam: o erro, os limites de texto e os
leitores de campo (spec 2026-10-15-f3-denso §5). Puro.

Os limites de texto vêm do layout: passou deles, o texto quebra em linhas demais e invade o
vizinho ou sai do cartão. Os do layout novo (painel de 1000 × 740 px na faixa de cima) ficam junto
dos antigos, que continuam valendo para os componentes redesenhados.
"""
import math
from typing import Any

from cortes.render.motion_icones import NOMES_ICONES

LIMITES = {"rotulo": 28, "titulo": 42, "destaque": 16, "prefixo": 4, "sufixo": 8, "marco": 10,
           "selo": 24, "valor_texto": 14, "carimbo": 18, "app": 16, "pergunta": 90,
           "titulo_lista": 34, "item": 24, "lugar": 14,
           "ponto_x": 10, "passo": 16, "check": 40, "frase": 60, "palavra": 24, "comodo": 14,
           "descricao": 140}
VALOR_MAX = 1e12


class ErroParams(ValueError):
    pass


def texto(d: dict[str, Any], campo: str, limite: str, opcional: bool = False) -> Any:
    v = d.get(campo)
    if v is None and opcional:
        return None
    if not isinstance(v, str) or not v.strip():
        raise ErroParams(f"'{campo}' deveria ser texto não vazio, veio {v!r}")
    v = " ".join(v.split())
    if len(v) > LIMITES[limite]:
        raise ErroParams(f"'{campo}' com {len(v)} caracteres (máximo {LIMITES[limite]}): {v!r}")
    return v


def afixo(d: dict[str, Any], campo: str) -> str:
    v = d.get(campo, "")
    if not isinstance(v, str) or len(v) > LIMITES[campo]:
        raise ErroParams(f"'{campo}' deveria ser texto de até {LIMITES[campo]} caracteres, veio {v!r}")
    return v


def numero(d: dict[str, Any], campo: str, opcional: bool = False) -> Any:
    v = d.get(campo)
    if v is None and opcional:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ErroParams(f"'{campo}' deveria ser número, veio {v!r}")
    if not 0 <= v <= VALOR_MAX:
        raise ErroParams(f"'{campo}' fora de 0 a {VALOR_MAX:.0e}: {v!r}")
    return float(v)


def inteiro(d: dict[str, Any], campo: str, minimo: int, maximo: int) -> int:
    v = d.get(campo)
    if isinstance(v, bool) or not isinstance(v, int) or not minimo <= v <= maximo:
        raise ErroParams(f"'{campo}' deveria ser inteiro de {minimo} a {maximo}, veio {v!r}")
    return v


def lista(d: dict[str, Any], campo: str, n_min: int, n_max: int) -> list[Any]:
    v = d.get(campo)
    if not isinstance(v, list) or not n_min <= len(v) <= n_max:
        raise ErroParams(f"'{campo}' deveria ser lista de {n_min} a {n_max} itens, veio {v!r}")
    return v


def objeto(v: Any, o_que: str) -> dict[str, Any]:
    if not isinstance(v, dict):
        raise ErroParams(f"{o_que} deveria ser objeto, veio {v!r}")
    return v


def escolha(d: dict[str, Any], campo: str, opcoes: tuple[str, ...]) -> str:
    v = d.get(campo)
    if v not in opcoes:
        raise ErroParams(f"'{campo}' deveria ser um de {opcoes}, veio {v!r}")
    return str(v)


def icone(d: dict[str, Any]) -> str:
    v = d.get("icone")
    if v not in NOMES_ICONES:
        raise ErroParams(f"ícone {v!r} não existe; use um de {NOMES_ICONES}")
    return str(v)


def formatar(v: float) -> str:
    """Como o número aparece na tela (pt-BR): 1500 → "1.500", 37.5 → "37,5"."""
    inteiro_ = f"{int(v):,}".replace(",", ".")
    frac = f"{v:.2f}".split(".")[1].rstrip("0")
    return f"{inteiro_},{frac}" if frac else inteiro_


def casas(v: float) -> int:
    return len(f"{v:.2f}".split(".")[1].rstrip("0"))
