"""Transforma a resposta do LLM em candidatos pontuados; descartes ficam registrados com motivo."""
from typing import Any

from cortes.perfil import Perfil
from cortes.regra_inicio import comeca_no_meio
from cortes.sinais import JANELA_S
from cortes.tipos import Candidato, Frase

PONTOS_BONUS = 5.0
PONTOS_PENALIDADE = 5.0
PONTOS_ENERGIA = 3.0
PERCENTIL_ENERGIA = 0.75
ABERTURA_S = 3.0


def nota_ponderada(notas: dict[str, int], rubrica: dict[str, float]) -> float:
    """Notas 1-5 → 0-100, pesadas pela rubrica."""
    return round(sum(peso * (notas[c] - 1) / 4 for c, peso in rubrica.items()) * 100, 1)


def percentil(valores: list[float], p: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(int(len(ordenados) * p), len(ordenados) - 1)]


def abertura_energetica(inicio: float, energia: list[float], limiar: float) -> bool:
    i0 = int(inicio / JANELA_S)
    trecho = energia[i0: i0 + int(ABERTURA_S / JANELA_S)]
    return bool(trecho) and sum(trecho) / len(trecho) >= limiar


def _motivo_descarte(b: dict[str, Any], frases: list[Frase], perfil: Perfil) -> str | None:
    ini, fim = b["frase_inicio"], b["frase_fim"]
    if not 0 <= ini <= fim < len(frases):
        return f"índices inválidos {ini}-{fim}"
    if not b["dentro_do_tema"]:
        return "fora do tema"
    if comeca_no_meio(frases[ini].texto):
        return f"começa no meio: '{frases[ini].texto}'"
    dur = frases[fim].fim - frases[ini].inicio
    if not perfil.duracao_min <= dur <= perfil.duracao_max:
        return f"duração {dur:.0f}s fora de {perfil.duracao_min:.0f}-{perfil.duracao_max:.0f}s"
    return None


def converter(bruto: dict[str, Any], frases: list[Frase], perfil: Perfil,
              energia: list[float]) -> tuple[list[Candidato], list[dict[str, Any]]]:
    limiar = percentil(energia, PERCENTIL_ENERGIA)
    aceitos: list[Candidato] = []
    descartes: list[dict[str, Any]] = []
    for b in bruto["candidatos"]:
        motivo = _motivo_descarte(b, frases, perfil)
        if motivo:
            descartes.append({"frase_inicio": b["frase_inicio"], "frase_fim": b["frase_fim"],
                              "motivo": motivo})
            continue
        inicio, fim = frases[b["frase_inicio"]].inicio, frases[b["frase_fim"]].fim
        nota = (nota_ponderada(b["notas"], perfil.rubrica)
                + PONTOS_BONUS * len(b["bonus"]) - PONTOS_PENALIDADE * len(b["penalidades"])
                + (PONTOS_ENERGIA if abertura_energetica(inicio, energia, limiar) else 0.0))
        aceitos.append(Candidato(b["frase_inicio"], b["frase_fim"], inicio, fim, b["notas"], b["bonus"],
                                 b["penalidades"], b["justificativa"], b["titulo"], round(nota, 1)))
    aceitos.sort(key=lambda c: -c.nota_final)
    return aceitos, descartes
