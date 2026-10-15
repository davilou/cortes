"""f3 Motion, o ritmo das cenas (spec 2026-10-15-f3-denso §4; pesquisa/05: cenas de 2 a 5 s, tela
dividida quase o tempo todo). Puro.

As regras vão no prompt e são aplicadas de novo aqui — o LLM erra a conta:
- a `capa` (gancho) só uma, de 0 a 2 s; nenhuma outra cena antes de GANCHO_S, que é do rosto;
- painel de DUR_MIN_S a DUR_MAX_S (o tempo já vem cortado assim de render/motion.py; a que ficou
  curta é a que bateu no fim da fala); painéis se encostam, sem rosto entre eles — o falante já
  está no card de baixo;
- cenas não se sobrepõem: a que invade acaba antes da seguinte (a nova ou a anterior, nunca a capa
  nem as fixas) se ainda dura o mínimo; senão a nova sai;
- `respiro` (rosto cheio no meio): de RESPIRO_MIN_S a RESPIRO_MAX_S, no máximo RESPIROS_MAX, nunca
  antes de RESPIRO_DEPOIS_S nem colado em outro respiro;
- no máximo ILUSTRACOES_MAX ilustrações (cada uma é uma chamada de LLM a mais).

Sai do f3 a regra da pesquisa 03 (0,6–0,8 trocas por 10 s) e o teto de 70% de motion: Davi trocou
o estilo pelo do reel de referência (2026-10-14). `emendar` estica o painel até o seguinte quando o
vão é curto, para a faixa de cima não piscar o fundo entre dois painéis.
"""
from dataclasses import dataclass, replace
from typing import Any

from cortes.render.motion_params import Params, params_json
from cortes.render.motion_sincronia import FOLGA_FIM_S

GANCHO_S = 2.0
DUR_MIN_S = 2.0
DUR_MAX_S = 5.0
RESPIRO_MIN_S = 1.5
RESPIRO_MAX_S = 3.0
RESPIROS_MAX = 2
RESPIRO_DEPOIS_S = 6.0
ILUSTRACOES_MAX = 3
COBERTURA_MIN = 0.85   # painel no tempo fora do gancho e dos respiros (alvo e gatilho da 2ª chamada)
EMENDA_S = 1.0
_EPS = 1e-6


@dataclass(frozen=True)
class Bruta:
    """Cena que passou nos parâmetros e nos números; falta o ritmo."""
    componente: str
    inicio: float
    fim: float
    params: Params
    batidas: tuple[float, ...]


@dataclass(frozen=True)
class Descartada:
    componente: str
    inicio: float
    fim: float
    params: Any     # como o LLM mandou (pode ser o que não passou na validação)
    motivo: str


def _fora(b: Bruta, motivo: str) -> Descartada:
    return Descartada(b.componente, b.inicio, b.fim, params_json(b.params), motivo)


def _vizinhos(b: Bruta, ficam: list[Bruta]) -> tuple[Bruta | None, Bruta | None]:
    antes = [f for f in ficam if f.inicio <= b.inicio]
    depois = [f for f in ficam if f.inicio > b.inicio]
    return (antes[-1] if antes else None), (depois[0] if depois else None)


def _minimo(b: Bruta) -> float:
    return RESPIRO_MIN_S if b.componente == "respiro" else DUR_MIN_S


def _ate(c: Bruta, seguinte: Bruta) -> Bruta | None:
    """`c` acabando onde `seguinte` começa, se ainda dura o mínimo e precisa mudar; None se não."""
    fim = round(seguinte.inicio, 2)
    if c.componente == "capa" or fim >= c.fim or fim - c.inicio < _minimo(c) - _EPS:
        return None
    return replace(c, fim=fim, batidas=tuple(min(t, round(fim - FOLGA_FIM_S, 2)) for t in c.batidas))


def _aparar(b: Bruta, ficam: list[Bruta], fixas: list[Bruta]) -> tuple[Bruta, list[Bruta]] | None:
    antes, depois = _vizinhos(b, ficam)
    nova = _ate(b, depois) if depois is not None else None
    b2 = nova or b
    velha = _ate(antes, b2) if antes is not None and antes not in fixas else None
    if nova is None and velha is None:
        return None
    return b2, [velha if velha is not None and f is antes else f for f in ficam]


def _sobrepoe(a: Bruta, b: Bruta, outra: Bruta) -> str | None:
    if b.inicio - a.fim < -_EPS:
        return f"ritmo: sobrepõe a cena {outra.componente} ({outra.inicio:.2f}–{outra.fim:.2f} s)"
    return None


def _respiro(b: Bruta, ficam: list[Bruta]) -> str | None:
    dur = b.fim - b.inicio
    if not RESPIRO_MIN_S - _EPS <= dur <= RESPIRO_MAX_S + _EPS:
        return f"ritmo: respiro de {dur:.1f} s (de {RESPIRO_MIN_S:.1f} a {RESPIRO_MAX_S:.1f} s)"
    if b.inicio < RESPIRO_DEPOIS_S - _EPS:
        return f"ritmo: respiro antes de {RESPIRO_DEPOIS_S:.0f} s"
    if sum(f.componente == "respiro" for f in ficam) >= RESPIROS_MAX:
        return f"ritmo: no máximo {RESPIROS_MAX} respiros"
    for f in _vizinhos(b, ficam):
        if f is not None and f.componente == "respiro" and min(abs(b.inicio - f.fim), abs(f.inicio - b.fim)) \
                < DUR_MIN_S - _EPS:
            return f"ritmo: respiro colado em outro respiro ({f.inicio:.2f}–{f.fim:.2f} s)"
    return None


def _proprio(b: Bruta, ficam: list[Bruta]) -> str | None:
    """O que a cena não pode por si (sem olhar sobreposição)."""
    if b.componente == "capa":
        return "ritmo: só uma capa, no gancho" if any(f.componente == "capa" for f in ficam) else None
    if b.inicio < GANCHO_S - _EPS:
        return f"ritmo: começa no gancho (antes de {GANCHO_S:.1f} s), que é do rosto"
    if b.componente == "respiro":
        return _respiro(b, ficam)
    if b.fim - b.inicio < DUR_MIN_S - _EPS:
        return f"ritmo: só {b.fim - b.inicio:.1f} s até o fim da fala (mínimo {DUR_MIN_S:.1f} s)"
    if b.componente == "ilustracao" and sum(f.componente == "ilustracao" for f in ficam) >= ILUSTRACOES_MAX:
        return f"ritmo: no máximo {ILUSTRACOES_MAX} ilustrações por Short"
    if b.componente == "destaque" and (m := _destaque_colado(b, ficam)):
        return m
    return None


def _destaque_colado(b: Bruta, ficam: list[Bruta]) -> str | None:
    """Frase-chave é o último recurso: duas seguidas viram o Short num karaokê (render real: 5 de 8
    cenas eram destaque e o "PERDI DINHEIRO" e a rota sumiram)."""
    for f in _vizinhos(b, ficam):
        vao = min(abs(b.inicio - f.fim), abs(f.inicio - b.fim)) if f is not None else 0.0
        if f is not None and f.componente == "destaque" and vao < DUR_MIN_S - _EPS:
            return f"ritmo: dois destaques seguidos ({f.inicio:.2f}–{f.fim:.2f} s)"
    return None


def _vizinhanca(b: Bruta, ficam: list[Bruta]) -> str | None:
    antes, depois = _vizinhos(b, ficam)
    if antes is not None and (m := _sobrepoe(antes, b, antes)):
        return m
    return _sobrepoe(b, depois, depois) if depois is not None else None


def ritmo(cenas: list[Bruta], dur: float,
          fixas: list[Bruta] | None = None) -> tuple[list[Bruta], list[Descartada]]:
    """As cenas que ficam (com as `fixas`), em ordem, e as que saem, com o motivo."""
    ficam: list[Bruta] = sorted(fixas or [], key=lambda b: b.inicio)
    fora: list[Descartada] = []
    for b in sorted(cenas, key=lambda b: (b.inicio, b.componente != "capa")):
        motivo = _proprio(b, ficam)
        if motivo is None and (motivo := _vizinhanca(b, ficam)) is not None:
            if (aparadas := _aparar(b, ficam, fixas or [])) is not None:
                b2, ficam2 = aparadas
                if _proprio(b2, ficam2) is None and _vizinhanca(b2, ficam2) is None:
                    b, ficam, motivo = b2, ficam2, None
        if motivo is None:
            ficam = sorted([*ficam, b], key=lambda x: x.inicio)
        else:
            fora.append(_fora(b, motivo))
    return ficam, fora


def emendar(cenas: list[Bruta], dur: float) -> list[Bruta]:
    """Painel que acaba até EMENDA_S antes da cena seguinte (ou do fim do Short) fica até ela."""
    res = sorted(cenas, key=lambda b: b.inicio)
    for k, c in enumerate(res):
        if c.componente in ("capa", "respiro"):
            continue
        prox = res[k + 1].inicio if k + 1 < len(res) else dur
        if 0 < prox - c.fim <= EMENDA_S + _EPS:
            res[k] = replace(c, fim=round(prox, 2))
    return res


def trocas_por_10s(cenas: list[Bruta], dur: float) -> float:
    """Trocas de plano: cada entrada e cada saída de painel; duas cenas coladas trocam uma vez só;
    a entrada em 0 e a saída no fim do Short não contam."""
    bordas = {round(t, 2) for b in cenas for t in (b.inicio, b.fim)}
    return 10 * len([t for t in bordas if _EPS < t < dur - _EPS]) / dur
