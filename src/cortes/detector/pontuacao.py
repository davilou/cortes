"""Transforma a resposta do LLM em candidatos pontuados; descartes ficam registrados com motivo."""
from typing import Any

import numpy as np

from cortes.perfil import Perfil
from cortes.regra_inicio import comeca_no_meio
from cortes.sinais import JANELA_S
from cortes.tipos import Candidato, Frase

PONTOS_BONUS = 5.0
PONTOS_PENALIDADE = 5.0
PONTOS_ENERGIA = 3.0
PERCENTIL_ENERGIA = 0.75
ABERTURA_S = 3.0
SOBREPOSICAO_MAX = 0.5   # fração do menor trecho que pode coincidir com um já aceito
_PONTUACAO = str.maketrans("", "", ".,;:!?…\"'“”")


def nota_ponderada(notas: dict[str, int], rubrica: dict[str, float]) -> float:
    """Notas 1-5 → 0-100, pesadas pela rubrica."""
    return round(sum(peso * (notas[c] - 1) / 4 for c, peso in rubrica.items()) * 100, 1)


def percentil(valores: list[float], p: float) -> float:
    if not valores:
        raise ValueError("energia vazia")
    return float(np.percentile(valores, p * 100))


def abertura_energetica(inicio: float, energia: list[float], limiar: float) -> bool:
    i0 = int(inicio / JANELA_S)
    if i0 >= len(energia):
        raise ValueError("energia mais curta que o episódio: sinais.json é de outro áudio?")
    trecho = energia[i0: i0 + int(ABERTURA_S / JANELA_S)]
    return sum(trecho) / len(trecho) >= limiar


def _normalizar(texto: str) -> str:
    return " ".join(texto.translate(_PONTUACAO).lower().split())


def _motivo_descarte(b: dict[str, Any], frases: list[Frase], perfil: Perfil) -> str | None:
    ini, fim = b["frase_inicio"], b["frase_fim"]
    if not 0 <= ini <= fim < len(frases):
        return f"índices inválidos {ini}-{fim}"
    if not _normalizar(frases[ini].texto).startswith(_normalizar(b["abre_com"])):
        return f"abre_com não bate com F{ini}: '{b['abre_com']}'"
    if not b["dentro_do_tema"]:
        return "fora do tema"
    if comeca_no_meio(frases[ini].texto):
        return f"começa no meio: '{frases[ini].texto}'"
    dur = frases[fim].fim - frases[ini].inicio
    if not perfil.duracao_min <= dur <= perfil.duracao_max:
        return f"duração {dur:.0f}s fora de {perfil.duracao_min:.0f}-{perfil.duracao_max:.0f}s"
    return None


def _pontuar(b: dict[str, Any], frases: list[Frase], perfil: Perfil, energia: list[float],
             limiar: float) -> Candidato:
    inicio, fim = frases[b["frase_inicio"]].inicio, frases[b["frase_fim"]].fim
    bonus, penalidades = list(dict.fromkeys(b["bonus"])), list(dict.fromkeys(b["penalidades"]))
    nota = (nota_ponderada(b["notas"], perfil.rubrica)
            + PONTOS_BONUS * len(bonus) - PONTOS_PENALIDADE * len(penalidades)
            + (PONTOS_ENERGIA if abertura_energetica(inicio, energia, limiar) else 0.0))
    return Candidato(b["frase_inicio"], b["frase_fim"], inicio, fim, b["notas"], bonus, penalidades,
                     b["justificativa"], b["titulo"], round(min(max(nota, 0.0), 100.0), 1))


def _sobreposto(c: Candidato, aceitos: list[Candidato]) -> Candidato | None:
    """Primeiro aceito que coincide com `c` em mais de SOBREPOSICAO_MAX do menor dos dois."""
    for a in aceitos:
        intersecao = min(c.fim, a.fim) - max(c.inicio, a.inicio)
        if intersecao > SOBREPOSICAO_MAX * min(c.fim - c.inicio, a.fim - a.inicio):
            return a
    return None


def converter(bruto: dict[str, Any], frases: list[Frase], perfil: Perfil,
              energia: list[float]) -> tuple[list[Candidato], list[dict[str, Any]]]:
    limiar = percentil(energia, PERCENTIL_ENERGIA)
    pontuados: list[tuple[Candidato, dict[str, Any]]] = []
    descartes: list[dict[str, Any]] = []
    for b in bruto["candidatos"]:
        motivo = _motivo_descarte(b, frases, perfil)
        if motivo:
            descartes.append({**b, "motivo": motivo})
        else:
            pontuados.append((_pontuar(b, frases, perfil, energia, limiar), b))
    pontuados.sort(key=lambda par: -par[0].nota_final)
    aceitos: list[Candidato] = []
    for c, b in pontuados:
        if (a := _sobreposto(c, aceitos)) is not None:
            descartes.append({**b, "motivo": f"sobrepõe F{a.frase_inicio}-F{a.frase_fim}"})
        else:
            aceitos.append(c)
    return aceitos, descartes
