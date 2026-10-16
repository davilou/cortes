"""f10 Motion v2 — o "bolo de camadas": as mesmas cenas do f3 (render/motion.py, mesmo cache), num
layout que alterna dois fundos, com a cabeça de quem fala saindo por cima do card, legenda palavra a
palavra e um efeito sonoro em cada movimento. Puro. Spec 2026-10-15-f10-motion-v2.

Estados da tela (render/formatos/motion2.tpl), em transição curta (~0,25 s):
- `gancho`: fundo claro pontilhado, a capa (rótulo e título) em cima e o card embaixo;
- `escuro`: um painel sozinho no meio do fundo marinho, o rosto num avatar redondo no canto;
- `claro`: o painel em cima e o card embaixo, no fundo claro — e o vão entre cenas (sem painel,
  com o rótulo da capa na faixa);
- `respiro`: só o card, maior, no fundo claro.
Os painéis se revezam entre `escuro` e `claro`, começando pelo escuro — o ritmo do reel de
referência (pesquisa/05): o fundo troca a cada cena de 2–5 s.
"""
import json
from dataclasses import dataclass

from cortes.render.motion import Cena
from cortes.render.motion_ritmo import GANCHO_S

VAO_MIN_S = 0.05    # fresta menor que isso entre duas cenas não vira estado `claro` (piscaria)

# efeitos (biblioteca/sfx/, copiados para os assets do corte): nome → duração do arquivo, em s
SFX = {"whoosh": 0.55, "pop": 0.11}
VOLUME = {"whoosh": 0.35, "pop": 0.45}
ANTES_WHOOSH_S = 0.12    # o whoosh começa um pouco antes da troca, para o pico cair nela
SFX_DISTANCIA_S = 0.18   # dois efeitos mais perto que isso viram um (o primeiro)
_TRILHA_SFX = 11         # Studio: 11–12 (a voz é 10, a cama da trilha vem depois)


@dataclass(frozen=True)
class Plano:
    estados: list[tuple[float, str]]   # (início, estado), em ordem; o primeiro em 0
    solo: frozenset[int]                # k das cenas mostradas no estado `escuro`


def _fim_gancho(cenas: list[Cena]) -> float:
    capa = next((c for c in cenas if c.componente == "capa"), None)
    return round(capa.fim if capa else GANCHO_S, 2)


def plano(cenas: list[Cena], dur: float) -> Plano:
    """Os estados no tempo e quais painéis vão sozinhos. Vão entre cenas fica `claro`."""
    t = _fim_gancho(cenas)
    estados: list[tuple[float, str]] = [(0.0, "gancho")]
    solo: set[int] = set()
    escuro = True
    for c in sorted((c for c in cenas if c.componente != "capa"), key=lambda c: c.inicio):
        if c.inicio - t > VAO_MIN_S:
            estados.append((t, "claro"))
        if c.componente == "respiro":
            estado = "respiro"
        else:
            estado = "escuro" if escuro else "claro"
            if escuro:
                solo.add(c.k)
            escuro = not escuro
        estados.append((round(max(c.inicio, t), 2), estado))
        t = round(max(t, c.fim), 2)
    if dur - t > VAO_MIN_S:
        estados.append((t, "claro"))
    return Plano(_sem_repetir(estados), frozenset(solo))


def _sem_repetir(estados: list[tuple[float, str]]) -> list[tuple[float, str]]:
    """Dois painéis claros seguidos (um respiro no meio do revezamento) são um estado só; e no mesmo
    instante vale o último."""
    res: list[tuple[float, str]] = []
    for t, e in estados:
        if res and res[-1][0] == t:
            res[-1] = (t, e)
        elif not res or res[-1][1] != e:
            res.append((t, e))
    return res


def estados_json(p: Plano) -> str:
    return json.dumps([[t, e] for t, e in p.estados])


def _momentos(cenas: list[Cena], p: Plano) -> list[tuple[float, str]]:
    """Whoosh em cada troca de estado; pop na entrada de cada painel e em cada batida."""
    ms = [(max(0.0, t - ANTES_WHOOSH_S), "whoosh") for t, _ in p.estados[1:]]
    for c in cenas:
        if c.componente in ("capa", "respiro"):
            continue
        ms.append((c.inicio + 0.05, "pop"))
        ms += [(b, "pop") for b in c.batidas]
    return sorted(ms)


def sfx(cenas: list[Cena], p: Plano, dur: float) -> list[tuple[float, str]]:
    """(início, efeito) de cada som, sem dois iguais colados e sem passar do fim do Short. Um pop logo
    depois do whoosh fica: são sons diferentes e o pop marca o painel que entra."""
    res: list[tuple[float, str]] = []
    ultimo: dict[str, float] = {}
    for t, nome in _momentos(cenas, p):
        t = round(t, 2)
        if t + SFX[nome] > dur or t - ultimo.get(nome, -1.0) < SFX_DISTANCIA_S:
            continue
        res.append((t, nome))
        ultimo[nome] = t
    return res


def sfx_html(sons: list[tuple[float, str]]) -> str:
    return "\n".join(
        f'      <audio id="sfx-{i}" src="assets/sfx-{nome}.wav" data-start="{t}" '
        f'data-duration="{SFX[nome]}" data-track-index="{_TRILHA_SFX + i % 2}" data-volume="{VOLUME[nome]}">'
        f"</audio>"
        for i, (t, nome) in enumerate(sons))
