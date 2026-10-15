"""f3 Motion, a cobertura e a segunda chamada ao LLM (spec 2026-10-15-f3-denso §4). Puro.

No estilo denso a faixa de cima mostra painel quase o tempo todo: depois da validação da primeira
resposta, se a cobertura ficou abaixo de COBERTURA_MIN ou sobrou um vão sem painel maior que
VAO_LONGO_S, o LLM recebe de volta as cenas aceitas, as recusadas com o motivo e os vãos com as
palavras deles, e devolve cenas só para os vãos — trecho de opinião vira `destaque` (a frase-chave
da própria fala), não painel inventado. No máximo 2 chamadas por corte (cota): quem decide é
render/motion.py.
"""
import json
from collections.abc import Sequence
from dataclasses import dataclass

from cortes.render.motion_params import params_json
from cortes.render.motion_ritmo import COBERTURA_MIN, DUR_MAX_S, DUR_MIN_S, GANCHO_S, Bruta, Descartada
from cortes.tipos import Palavra

VAO_LONGO_S = 3.0
_SEM_PAINEL = ("capa", "respiro")


@dataclass(frozen=True)
class Vao:
    inicio: float
    fim: float
    i: int          # primeira e última palavra dentro do vão
    j: int
    texto: str


def cobertura(cenas: Sequence[Bruta], dur: float) -> float:
    """Tempo com painel sobre o tempo que deveria ter painel (fora do gancho e dos respiros)."""
    paineis = sum(c.fim - c.inicio for c in cenas if c.componente not in _SEM_PAINEL)
    respiros = sum(c.fim - c.inicio for c in cenas if c.componente == "respiro")
    base = dur - GANCHO_S - respiros
    return round(paineis / base, 3) if base > 0 else 1.0


def _livres(cenas: Sequence[Bruta], dur: float) -> list[tuple[float, float]]:
    livres, t = [], GANCHO_S
    for c in sorted(cenas, key=lambda c: c.inicio):
        if c.inicio > t:
            livres.append((t, c.inicio))
        t = max(t, c.fim)
    return [*livres, (t, dur)] if dur > t else livres


def vaos(cenas: Sequence[Bruta], palavras: list[Palavra], dur: float) -> list[Vao]:
    """Os trechos sem cena depois do gancho em que cabe um painel, com a fala deles."""
    res = []
    for a, b in _livres(cenas, dur):
        idx = [k for k, w in enumerate(palavras) if a - 1e-6 <= w.inicio < b]
        if b - a >= DUR_MIN_S - 1e-6 and idx:
            texto = " ".join(palavras[k].texto for k in idx)
            res.append(Vao(round(a, 2), round(b, 2), idx[0], idx[-1], texto))
    return res


def precisa_segunda(cenas: Sequence[Bruta], vs: Sequence[Vao], dur: float) -> bool:
    """Só com vão para cobrir: sem ele, a segunda chamada só convidaria o LLM a inventar painel.
    `cenas` já emendadas (motion_ritmo.emendar), como vão para a tela."""
    if not vs:
        return False
    return cobertura(cenas, dur) < COBERTURA_MIN or any(v.fim - v.inicio > VAO_LONGO_S for v in vs)


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
    partes += [f"A cobertura ficou em {cobertura(aceitas, dur):.0%} (alvo: {COBERTURA_MIN:.0%} ou mais "
               "do tempo depois do gancho com painel). Cubra estes trechos sem painel, com cenas de "
               f"{DUR_MIN_S:.0f} a {DUR_MAX_S:.0f} s coladas umas nas outras; onde a fala é opinião "
               'sem número, lista ou lugar, use "destaque" com a frase-chave da própria fala — nunca '
               "invente dado:",
               *(f'- [{v.inicio:.2f}–{v.fim:.2f} s] palavras [{v.i}] a [{v.j}]: "{v.texto}"' for v in vs)]
    if not any(c.componente == "capa" for c in aceitas):
        partes.append("Sem capa: mande também a capa do gancho (0 a 2 s).")
    partes.append("Devolva SÓ as cenas novas, com as mesmas regras e o mesmo tema.")
    return "\n".join(partes)
