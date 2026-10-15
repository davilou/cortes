"""f3 Motion, os componentes novos do estilo denso (spec 2026-10-15-f3-denso §5; pesquisa/05:
gráfico, fluxo, timer, check, grade, frase-chave, planta, ilustração e o respiro). Puro.

Cada um com os textos que vão para a tela (a base da regra dos números) e as batidas — os textos
que entram no instante em que são ditos.
"""
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cortes.render.motion_params_base import (
    ErroParams,
    escolha,
    formatar,
    icone,
    inteiro,
    lista,
    numero,
    objeto,
    texto,
)

UNIDADES = ("s", "min", "h")
# o relógio mostra o valor sem converter ("00:45", "08:00"): 90 s viraria "01:30", número não dito
TIMER_MAX = {"s": 59, "min": 59, "h": 99}
SINAIS = ("sim", "nao")


@dataclass(frozen=True)
class Ponto:
    x: str
    y: float


@dataclass(frozen=True)
class Grafico:
    rotulo: str
    pontos: tuple[Ponto, ...]
    ponto_destaque: int


@dataclass(frozen=True)
class Passo:
    icone: str
    texto: str


@dataclass(frozen=True)
class Fluxo:
    passos: tuple[Passo, ...]
    ativo: int


@dataclass(frozen=True)
class Timer:
    rotulo: str
    valor: int
    unidade: str


@dataclass(frozen=True)
class Check:
    texto: str
    sinal: str


@dataclass(frozen=True)
class Grade:
    blocos: tuple[Passo, ...]


@dataclass(frozen=True)
class Destaque:
    frase: str
    palavra: str


@dataclass(frozen=True)
class Comodo:
    nome: str
    m2: float | None


@dataclass(frozen=True)
class Planta:
    comodos: tuple[Comodo, ...]
    total_m2: float | None = None


@dataclass(frozen=True)
class Ilustracao:
    descricao: str   # o que desenhar (vai para a chamada do SVG, não para a tela)
    rotulo: str
    icone: str       # o que aparece se o SVG for recusado


@dataclass(frozen=True)
class Respiro:
    """Rosto cheio no meio do Short, sem painel."""


Novo = Grafico | Fluxo | Timer | Check | Grade | Destaque | Planta | Ilustracao | Respiro


def _grafico(d: dict[str, Any]) -> Grafico:
    pontos = tuple(Ponto(texto(p, "x", "ponto_x"), numero(p, "y"))
                   for p in (objeto(x, "ponto") for x in lista(d, "pontos", 2, 6)))
    return Grafico(texto(d, "rotulo", "rotulo"), pontos,
                   inteiro(d, "ponto_destaque", 0, len(pontos) - 1))


def _passos(d: dict[str, Any], campo: str, n_min: int, n_max: int) -> tuple[Passo, ...]:
    return tuple(Passo(icone(p), texto(p, "texto", "passo"))
                 for p in (objeto(x, "passo") for x in lista(d, campo, n_min, n_max)))


def _fluxo(d: dict[str, Any]) -> Fluxo:
    passos = _passos(d, "passos", 2, 4)
    return Fluxo(passos, inteiro(d, "ativo", 0, len(passos) - 1))


def _timer(d: dict[str, Any]) -> Timer:
    unidade = escolha(d, "unidade", UNIDADES)
    return Timer(texto(d, "rotulo", "rotulo"), inteiro(d, "valor", 1, TIMER_MAX[unidade]), unidade)


def _check(d: dict[str, Any]) -> Check:
    return Check(texto(d, "texto", "check"), escolha(d, "sinal", SINAIS))


def _grade(d: dict[str, Any]) -> Grade:
    return Grade(_passos(d, "blocos", 2, 6))


def _destaque(d: dict[str, Any]) -> Destaque:
    frase, palavra = texto(d, "frase", "frase"), texto(d, "palavra", "palavra")
    if palavra.lower() not in re.findall(r"\w+", frase.lower()):
        raise ErroParams(f"palavra {palavra!r} não está na frase {frase!r}")
    return Destaque(frase, palavra)


def _comodo(c: Any) -> Comodo:
    c = objeto(c, "cômodo")
    m2 = numero(c, "m2", opcional=True)
    if m2 is not None and m2 <= 0:
        raise ErroParams(f"'m2' deveria ser maior que zero, veio {m2}")
    return Comodo(texto(c, "nome", "comodo"), m2)


def _planta(d: dict[str, Any]) -> Planta:
    total = numero(d, "total_m2", opcional=True)
    return Planta(tuple(_comodo(c) for c in lista(d, "comodos", 2, 6)), total)


def _ilustracao(d: dict[str, Any]) -> Ilustracao:
    return Ilustracao(texto(d, "descricao", "descricao"), texto(d, "rotulo", "rotulo"), icone(d))


def _respiro(d: dict[str, Any]) -> Respiro:
    if d:
        raise ErroParams(f"respiro não tem parâmetros, vieram {sorted(d)}")
    return Respiro()


LEITORES_NOVOS: dict[str, Callable[[dict[str, Any]], Novo]] = {
    "grafico": _grafico, "fluxo": _fluxo, "timer": _timer, "check": _check, "grade": _grade,
    "destaque": _destaque, "planta": _planta, "ilustracao": _ilustracao, "respiro": _respiro,
}


def textos_novo(p: Novo) -> list[str]:
    match p:
        case Grafico():
            return [p.rotulo, *(t for q in p.pontos for t in (q.x, formatar(q.y)))]
        case Fluxo() | Grade():
            return [q.texto for q in (p.passos if isinstance(p, Fluxo) else p.blocos)]
        case Timer():
            return [p.rotulo, f"{p.valor} {p.unidade}"]
        case Check():
            return [p.texto]
        case Destaque():
            return [p.frase]
        case Planta():
            areas = [f"{formatar(c.m2)} m²" for c in p.comodos if c.m2 is not None]
            total = [f"{formatar(p.total_m2)} m²"] if p.total_m2 is not None else []
            return [*(c.nome for c in p.comodos), *areas, *total]
        case Ilustracao():
            return [p.rotulo]
        case Respiro():
            return []


def batidas_novo(p: Novo) -> list[str]:
    match p:
        case Grafico():
            return [p.pontos[p.ponto_destaque].x]
        case Fluxo():
            return [q.texto for q in p.passos]
        case Grade():
            return [q.texto for q in p.blocos]
        case Check():
            return [p.texto]
        case Destaque():
            return [p.palavra]
        case Planta():
            return [c.nome for c in p.comodos]
        case Ilustracao():
            return [p.rotulo]
        case Timer() | Respiro():
            return []
