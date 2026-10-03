"""f3 Motion, quando cada parte do painel entra (plano 2026-10-03-motion). Puro.

A cena entra quando a fala chega nela (o LLM aponta a palavra). Dentro da cena, cada "batida" — um
item da lista, o destino da rota, o selo — entra na palavra que a diz: a âncora é o número escrito
na batida ou, sem número, a palavra mais longa dela, procurada na fala da própria cena. Batida que
a fala não diz com essas letras (ex.: "Saquarema" transcrito "saco arema") entra no passo regular,
depois da anterior, nunca junto: o tempo é estimado, o texto não muda.
"""
import re
import unicodedata

from cortes.render.motion_params import Params, batidas
from cortes.tipos import Palavra

ENTRADA_S = 0.2     # a primeira batida sem âncora entra logo depois do painel
PASSO_MAX_S = 0.8   # e as seguintes, a este passo no máximo
FOLGA_FIM_S = 0.4   # nenhuma batida entra tão perto do fim que não dê para ler


def _norm(t: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def ancoras(texto: str) -> list[str]:
    """Onde procurar a batida na fala, em ordem: o número, se tiver; senão as palavras de 4 letras
    ou mais, da mais longa para a mais curta ("MEIA-NOITE" transcrita "meia -noite" cai no "SEIS")."""
    tokens = [_norm(p) for p in texto.split() if _norm(p)]
    digitos = [t for t in tokens if t.isdigit()]
    if digitos:
        return digitos[:1]
    longas = sorted((t for t in tokens if len(t) >= 4), key=len, reverse=True)
    return longas or [max(tokens, key=len, default="")]


def ancora(texto: str) -> str:
    return ancoras(texto)[0]


def _bate(falada: str, a: str) -> bool:
    if a.isdigit():
        return falada == a
    return falada == a or (len(a) >= 3 and falada.startswith(a))


def _achar(a: str, palavras: list[Palavra], ini: float, fim: float, depois: float) -> float | None:
    for w in palavras:
        if ini - 0.05 <= w.inicio < fim and w.inicio >= depois and _bate(_norm(w.texto), a):
            return w.inicio
    return None


def tempos_das_batidas(p: Params, palavras: list[Palavra], ini: float, fim: float) -> tuple[float, ...]:
    """Um instante por texto de `batidas(p)`, crescente, dentro de [ini, fim − FOLGA_FIM_S]."""
    textos = batidas(p)
    limite = max(ini, fim - FOLGA_FIM_S)
    passo = min(PASSO_MAX_S, (limite - ini - ENTRADA_S) / max(len(textos), 1))
    res: list[float] = []
    for n, texto in enumerate(textos):
        depois = res[-1] if res else ini
        achado = next((t for a in ancoras(texto) if (t := _achar(a, palavras, ini, fim, depois)) is not None),
                      None)
        regular = ini + ENTRADA_S + n * max(passo, 0.0)
        t = achado if achado is not None else max(regular, depois + passo if res else regular)
        res.append(round(min(max(t, depois, ini), limite), 2))
    return tuple(res)
