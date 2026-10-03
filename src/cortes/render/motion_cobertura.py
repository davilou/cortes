"""f3 Motion, a cobertura e a segunda chamada ao LLM (plano 2026-10-03-melhora-f3). Puro.

No teste cego, uma chamada só devolveu cenas para 30–40% do Short (o manual tem ~60%), mesmo com
o prompt pedindo. Depois da validação da primeira resposta, se a cobertura ficou abaixo de
COBERTURA_MIN ou sobrou um vão de rosto maior que VAO_LONGO_S com algo mostrável (número,
comparação, lista ou lugar), o LLM recebe de volta as cenas aceitas, as recusadas com o motivo e os
vãos com as palavras deles, e devolve cenas só para os vãos. No máximo 2 chamadas por corte (cota):
quem decide é render/motion.py.
"""
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

from cortes.render.motion_numeros import numeros
from cortes.render.motion_params import params_json
from cortes.render.motion_prompt import COBERTURA_MIN
from cortes.render.motion_ritmo import DUR_MIN_S, FRACAO_MAX, GANCHO_S, ROSTO_MIN_S, Bruta, Descartada
from cortes.tipos import Palavra

VAO_MIN_S = DUR_MIN_S + 2 * ROSTO_MIN_S   # 3,5 s: cabe uma cena com rosto dos dois lados
VAO_LONGO_S = 6.0
# contraste, perda/ganho, enumeração e ida a um lugar; nomes próprios no meio da frase
_SINAIS = re.compile(
    r"\b(mais|menos|contra|perd[ie]u?|ganh(ei|ou|a)|rend(eu|eria|e)|melhor|pior|caro|barato|"
    r"lucro|preju[ií]zo|primeiro|segundo|terceiro|"
    r"(ir|indo|vai|vou|fui|foi|voltar?)\s+(em|pra|para|at[eé]|no|na|a))\b", re.IGNORECASE)
_FIM_DE_FRASE = re.compile(r"[.!?…]$")


@dataclass(frozen=True)
class Vao:
    inicio: float
    fim: float
    i: int          # primeira e última palavra dentro do vão
    j: int
    texto: str


def cobertura(cenas: Sequence[Bruta], dur: float) -> float:
    return round(sum(c.fim - c.inicio for c in cenas) / dur, 3)


def _livres(cenas: Sequence[Bruta], dur: float) -> list[tuple[float, float]]:
    livres, t = [], GANCHO_S
    for c in sorted(cenas, key=lambda c: c.inicio):
        if c.inicio > t:
            livres.append((t, c.inicio))
        t = max(t, c.fim)
    return [*livres, (t, dur)] if dur > t else livres


def vaos(cenas: Sequence[Bruta], palavras: list[Palavra], dur: float) -> list[Vao]:
    """Os trechos só de rosto depois do gancho em que cabe uma cena, com a fala deles."""
    res = []
    for a, b in _livres(cenas, dur):
        idx = [k for k, w in enumerate(palavras) if a - 1e-6 <= w.inicio < b]
        if b - a >= VAO_MIN_S - 1e-6 and idx:
            texto = " ".join(palavras[k].texto for k in idx)
            res.append(Vao(round(a, 2), round(b, 2), idx[0], idx[-1], texto))
    return res


def _nome_proprio(texto: str) -> bool:
    ws = texto.split()
    return any(w[:1].isupper() and not _FIM_DE_FRASE.search(ws[k - 1]) for k, w in enumerate(ws) if k)


def mostravel(texto: str) -> bool:
    """Tem número, comparação, lista ou lugar: dá para virar painel."""
    return (any(n.valor for n in numeros(texto)) or bool(_SINAIS.search(texto))
            or _nome_proprio(texto))


def precisa_segunda(cenas: Sequence[Bruta], vs: Sequence[Vao], dur: float) -> bool:
    return cobertura(cenas, dur) < COBERTURA_MIN or any(
        v.fim - v.inicio > VAO_LONGO_S and mostravel(v.texto) for v in vs)


def _cena(c: Bruta) -> str:
    return (f"- [{c.inicio:.2f}–{c.fim:.2f} s] {c.componente}: "
            f"{json.dumps(params_json(c.params), ensure_ascii=False)}")


def feedback(aceitas: Sequence[Bruta], recusadas: Sequence[Descartada], vs: Sequence[Vao],
             dur: float) -> str:
    """O pedido da segunda chamada, que vai depois do prompt da primeira."""
    partes = ["Você já respondeu uma vez. Cenas aceitas (ficam; não repita nem sobreponha):",
              *([_cena(c) for c in aceitas] or ["- nenhuma"])]
    if recusadas:
        partes += ["Recusadas (não repita o erro):",
                   *(f"- [{d.inicio:.2f}–{d.fim:.2f} s] {d.componente}: {d.motivo}" for d in recusadas)]
    partes += [f"A cobertura ficou em {cobertura(aceitas, dur):.0%} (alvo de {COBERTURA_MIN:.0%} a "
               f"{FRACAO_MAX:.0%}). Trechos só com o rosto — ponha cenas APENAS dentro deles, para o "
               "que neles é mostrável (valor, comparação, lista, lugar, pergunta a um app):",
               *(f'- [{v.inicio:.2f}–{v.fim:.2f} s] palavras [{v.i}] a [{v.j}]: "{v.texto}"' for v in vs),
               "Devolva SÓ as cenas novas, com as mesmas regras. Se nada nesses trechos vira painel, "
               "devolva a lista vazia."]
    return "\n".join(partes)
