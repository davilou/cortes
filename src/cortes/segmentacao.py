"""Agrupa palavras em frases: fecha na pontuação final ou numa pausa longa (spec §6.4.1).

Limitação conhecida: abreviações como "Sr." fecham a frase antes da hora
(raro em fala transcrita; aceito).
"""
from cortes.tipos import Frase, Palavra

FIM_DE_FRASE = (".", "?", "!", "…")
_FECHAMENTO = "\"'”’)»"
PAUSA_S = 0.8


def frases(palavras: list[Palavra], pausa_s: float = PAUSA_S) -> list[Frase]:
    saida: list[Frase] = []
    atual: list[Palavra] = []
    for i, w in enumerate(palavras):
        atual.append(w)
        prox = palavras[i + 1] if i + 1 < len(palavras) else None
        fecha_frase = w.texto.rstrip(_FECHAMENTO).endswith(FIM_DE_FRASE)
        if prox is None or fecha_frase or prox.inicio - w.fim >= pausa_s:
            saida.append(Frase(len(saida), " ".join(x.texto for x in atual), atual[0].inicio, atual[-1].fim))
            atual = []
    return saida
