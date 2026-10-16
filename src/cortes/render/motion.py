"""f3 Motion, as cenas (plano 2026-10-03-motion; estilo denso: spec 2026-10-15-f3-denso): o Claude
lê a fala do corte e escolhe o tema e, para cada trecho, um componente e os parâmetros dele — JSON
validado por schema, nunca HTML. Daqui para a frente tudo é código: parâmetros conferidos por componente
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
from cortes.render.motion_ritmo import (
    DUR_MAX_S,
    DUR_MIN_S,
    RESPIRO_MAX_S,
    RESPIRO_MIN_S,
    Bruta,
    Descartada,
    emendar,
    ritmo,
)
from cortes.render.motion_sincronia import tempos_das_batidas
from cortes.render.motion_tema import TEMAS_LLM
from cortes.render.processo import ErroRender
from cortes.tipos import Palavra

CAPA_FIM_S = 2.0    # o gancho: rosto cheio com o título, de 0 a 2 s (pesquisa/05)
POR_BATIDAS = ("lista", "rota", "fluxo", "grade", "planta")   # o conteúdo entra item a item, na fala
LEITURA_S = 0.6     # a última batida fica pelo menos isto depois da palavra que a diz
ENCOSTA_GANCHO_S = 0.6   # cena que começa até isto antes do fim do gancho entra no fim dele (render real)


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
    tema: str


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
    ini, fala_fim = palavras[i].inicio, palavras[j].fim
    if CAPA_FIM_S - ENCOSTA_GANCHO_S <= ini < CAPA_FIM_S:
        ini = CAPA_FIM_S
    if item["componente"] == "respiro":
        return round(ini, 2), round(min(max(fala_fim, ini + RESPIRO_MIN_S), ini + RESPIRO_MAX_S, dur), 2)
    if item["componente"] in POR_BATIDAS:
        # o que importa é o último item / o destino: fica LEITURA_S depois da palavra e, se não
        # cabe no máximo, a cena entra mais tarde, numa palavra (render real: "Localização" ficava
        # 0,4 s na tela)
        fala_fim += LEITURA_S
        alvo = min(fala_fim, dur) - DUR_MAX_S
        ini = next((w.inicio for w in palavras[i:j + 1] if w.inicio >= alvo - 1e-6), palavras[j].inicio)
    fim = min(max(fala_fim, ini + DUR_MIN_S), ini + DUR_MAX_S, dur)
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
    primeira = chamar(prompt, SCHEMA_CENAS, SISTEMA_CENAS, modelo)
    tema = primeira.get("tema")
    if tema not in TEMAS_LLM:
        raise ErroLLM(f"tema {tema!r} fora de {TEMAS_LLM}")
    ficam, fora = _rodada(primeira, palavras, dur, [])
    vs = vaos(ficam, palavras, dur)
    if precisa_segunda(emendar(ficam, dur), vs, dur):   # a segunda e última chamada (cota)
        pedido = f"{prompt}\n\n{feedback(ficam, fora, vs, dur)}"
        ficam, fora2 = _rodada(chamar(pedido, SCHEMA_CENAS, SISTEMA_CENAS, modelo), palavras, dur, ficam)
        fora += fora2
    cenas = [Cena(k, b.componente, b.inicio, b.fim, b.params, b.batidas)
             for k, b in enumerate(emendar(ficam, dur), 1)]
    return Resultado(cenas, sorted(fora, key=lambda d: d.inicio), str(tema))


def _rodada(bruto: dict[str, Any], palavras: list[Palavra], dur: float,
            fixas: list[Bruta]) -> tuple[list[Bruta], list[Descartada]]:
    """Uma resposta do LLM conferida: as cenas que ficam (com as `fixas`) e as descartadas."""
    lidas = [_bruta(item, palavras, dur) for item in bruto["cenas"]]
    ficam, fora = ritmo([x for x in lidas if isinstance(x, Bruta)], dur, fixas)
    return ficam, [x for x in lidas if isinstance(x, Descartada)] + fora

