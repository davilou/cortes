"""f3 Motion, as cenas (plano 2026-10-03-motion; spec produção §7): o Claude lê a fala do corte e
escolhe, para os momentos que dá para mostrar, um componente e os parâmetros dele — JSON validado
por schema, nunca HTML. Daqui para a frente tudo é código: parâmetros conferidos por componente
(render/motion_params.py), números só os ditos (render/motion_numeros.py) e o ritmo.

Cena recusada (parâmetro inválido, número não dito, ritmo) fica em `descartadas`, com o motivo,
visível no editor. Índice de palavra inválido é a resposta errada inteira: erro, como nas deixas
do f4. Cobertura baixa ou vão longo com algo mostrável depois da primeira resposta: uma segunda
chamada, com as aceitas fixas e os vãos (render/motion_cobertura.py, plano 2026-10-03-melhora-f3).
"""
from dataclasses import dataclass
from typing import Any

from cortes.detector import ChamarLLM
from cortes.llm import ErroLLM
from cortes.render.ilustracao import fala_numerada
from cortes.render.motion_cobertura import feedback, precisa_segunda, vaos
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
            f"Fala do Short (palavras numeradas; as palavras vão de [0] a [{len(palavras) - 1}]):\n"
            f"{fala_numerada(palavras)}")


def _tempos(item: dict[str, Any], palavras: list[Palavra], dur: float) -> tuple[float, float]:
    i, j = item["inicio_palavra"], item["fim_palavra"]
    if i < j == len(palavras):   # fim exclusivo na cena que vai até o fim (render real): a última
        j -= 1
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
    # dito até o fim da cena; a capa é a promessa do corte e vale com o que o corte inteiro diz
    ditas = [w.texto for w in palavras if w.inicio < fim or comp == "capa"]
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
    prompt = prompt_cenas(palavras, contexto)
    ficam, fora = _rodada(chamar(prompt, SCHEMA_CENAS, SISTEMA_CENAS, modelo), palavras, dur, [])
    vs = vaos(ficam, palavras, dur)
    if precisa_segunda(ficam, vs, dur):   # a segunda e última chamada (cota)
        pedido = f"{prompt}\n\n{feedback(ficam, fora, vs, dur)}"
        ficam, fora2 = _rodada(chamar(pedido, SCHEMA_CENAS, SISTEMA_CENAS, modelo), palavras, dur, ficam)
        fora += fora2
    cenas = [Cena(k, b.componente, b.inicio, b.fim, b.params, b.batidas) for k, b in enumerate(ficam, 1)]
    return Resultado(cenas, sorted(fora, key=lambda d: d.inicio))


def _rodada(bruto: dict[str, Any], palavras: list[Palavra], dur: float,
            fixas: list[Bruta]) -> tuple[list[Bruta], list[Descartada]]:
    """Uma resposta do LLM conferida: as cenas que ficam (com as `fixas`) e as descartadas."""
    lidas = [_bruta(item, palavras, dur) for item in bruto["cenas"]]
    ficam, fora = ritmo([x for x in lidas if isinstance(x, Bruta)], dur, fixas)
    return ficam, [x for x in lidas if isinstance(x, Descartada)] + fora

