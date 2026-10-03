"""f3 Motion, as cenas (plano 2026-10-03-motion; spec produção §7): o Claude lê a fala do corte e
escolhe, para os momentos que dá para mostrar, um componente e os parâmetros dele — JSON validado
por schema, nunca HTML. Daqui para a frente tudo é código: parâmetros conferidos por componente
(render/motion_params.py), números só os ditos (render/motion_numeros.py) e o ritmo.

Cena recusada (parâmetro inválido, número não dito, ritmo) fica em `descartadas`, com o motivo,
visível no editor. Índice de palavra inválido é a resposta errada inteira: erro, como nas deixas
do f4.
"""
from dataclasses import dataclass
from typing import Any

from cortes.detector import ChamarLLM
from cortes.llm import ErroLLM
from cortes.render.ilustracao import fala_numerada
from cortes.render.motion_numeros import nao_ditos, numeros_da_fala
from cortes.render.motion_params import ErroParams, Params, ler_params, textos_da_tela
from cortes.render.motion_prompt import (
    SCHEMA_CENAS,
    SISTEMA_CENAS,
    Contexto,
    contexto_do_episodio,
    regras,
)
from cortes.render.motion_ritmo import DUR_MAX_S, DUR_MIN_S, Bruta, Descartada, ritmo
from cortes.render.motion_sincronia import tempos_das_batidas
from cortes.render.processo import ErroRender
from cortes.tipos import Palavra

CAPA_FIM_S = 2.2    # a capa fica de 0 a 2,2 s (protótipo), dentro da janela do gancho (0–2,5 s)


@dataclass(frozen=True)
class Cena:
    k: int
    componente: str
    inicio: float                  # s, no tempo do trecho sem pausas
    fim: float
    params: Params
    batidas: tuple[float, ...]     # instante de cada texto de `motion_params.batidas`


@dataclass(frozen=True)
class Resultado:
    cenas: list[Cena]
    descartadas: list[Descartada]


def prompt_cenas(palavras: list[Palavra], contexto: Contexto) -> str:
    return (f"{regras()}\n\n{contexto_do_episodio(contexto)}\n\n"
            f"Fala do Short (palavras numeradas):\n{fala_numerada(palavras)}")


def _tempos(item: dict[str, Any], palavras: list[Palavra], dur: float) -> tuple[float, float]:
    i, j = item["inicio_palavra"], item["fim_palavra"]
    if not (0 <= i <= j < len(palavras)):
        raise ErroLLM(f"cena '{item['componente']}' com palavras {i} a {j} inválidas "
                      f"(o corte tem {len(palavras)} palavras, 0 a {len(palavras) - 1})")
    if item["componente"] == "capa":
        return 0.0, round(min(CAPA_FIM_S, dur), 2)
    ini = palavras[i].inicio
    fim = min(max(palavras[j].fim, ini + DUR_MIN_S), ini + DUR_MAX_S, dur)
    return round(ini, 2), round(fim, 2)


def _bruta(item: dict[str, Any], palavras: list[Palavra], dur: float) -> Bruta | Descartada:
    """A cena com tempo e parâmetros conferidos, ou a descartada com o motivo."""
    ini, fim = _tempos(item, palavras, dur)
    comp, cru = item["componente"], item["params"]
    try:
        p = ler_params(comp, cru)
    except ErroParams as e:
        return Descartada(comp, ini, fim, cru, f"parâmetro inválido: {e}")
    ditas = [w.texto for w in palavras if w.inicio < fim]   # dito até o fim da cena
    faltam = nao_ditos(textos_da_tela(p), numeros_da_fala(ditas))
    if faltam:
        return Descartada(comp, ini, fim, cru, f"número que a fala não disse: {', '.join(faltam)}")
    return Bruta(comp, ini, fim, p, tempos_das_batidas(p, palavras, ini, fim))


def cenas_do_corte(palavras: list[Palavra], dur: float, chamar: ChamarLLM, contexto: Contexto,
                   modelo: str = "sonnet") -> Resultado:
    """`palavras` no tempo do trecho sem pausas, sem máscara (as mesmas das deixas do f4); `dur` é
    a duração desse trecho, a base do limite de motion."""
    if not palavras:
        raise ErroRender("corte sem palavras: não há fala para virar painel")
    if dur <= 0:
        raise ErroRender(f"duração do corte inválida para o motion: {dur}")
    bruto = chamar(prompt_cenas(palavras, contexto), SCHEMA_CENAS, SISTEMA_CENAS, modelo)
    lidas = [_bruta(item, palavras, dur) for item in bruto["cenas"]]
    descartadas = [x for x in lidas if isinstance(x, Descartada)]
    ficam, fora = ritmo([x for x in lidas if isinstance(x, Bruta)], dur)
    cenas = [Cena(k, b.componente, b.inicio, b.fim, b.params, b.batidas) for k, b in enumerate(ficam, 1)]
    return Resultado(cenas, sorted(descartadas + fora, key=lambda d: d.inicio))

