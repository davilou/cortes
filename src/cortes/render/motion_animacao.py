"""f3 Motion, a animação de cada cena: linhas de GSAP na timeline `tl` do motion.tpl (plano
2026-10-03-motion). Puro.

Só ids gerados em render/motion_componentes.py e números entram no JavaScript, nunca texto do LLM.
Tempos e curvas vêm do protótipo (testes/short-400mil-dinamica/modelo.tpl), sem o zoom lento da
capa (Davi, 2026-10-02). A contagem usa `contar(...)` do template, que escreve um valor por quadro
(determinística, como o count-up do registry do HyperFrames).
"""
from cortes.render.motion import Cena
from cortes.render.motion_params import (
    ESTADO,
    Capa,
    Chat,
    Comparacao,
    Contador,
    Lista,
    Rota,
    ValorCheio,
    casas,
)

CONTA_S = 1.7     # count-up do registry: 1,72 s


def _t(x: float) -> str:
    return f"{round(x, 2)}"


def _de(sel: str, de: str, ate: str, dur: float, ease: str, t: float) -> str:
    return f'tl.fromTo("{sel}", {{ {de} }}, {{ {ate}, duration: {dur}, ease: "{ease}" }}, {_t(t)});'


def _conta(k: int, de: float, valor: float, t0: float, dur_cena: float) -> list[str]:
    dur = round(min(CONTA_S, max(0.4, dur_cena - 0.5)), 2)
    c = max(casas(de), casas(valor))
    return [f'contar("#m{k}-n", {de}, {valor}, {c}, {_t(t0)}, {dur});',
            f'tl.to("#m{k}-c", {{ scale: 1.07, duration: 0.16, ease: "power3.out" }}, {_t(t0 + dur)});',
            f'tl.to("#m{k}-c", {{ scale: 1, duration: 0.16, ease: "power2.out" }}, {_t(t0 + dur + 0.16)});']


def _entrada(c: Cena) -> list[str]:
    s, t = f"#m{c.k}", c.inicio
    if c.componente == "capa":
        return [_de(f"{s} .rotulo", "x: -60, opacity: 0", "x: 0, opacity: 1", 0.3, "power3.out", t),
                _de(f"{s} .titulo", "y: 60, opacity: 0", "y: 0, opacity: 1", 0.35, "expo.out", t + 0.05)]
    if ESTADO[c.componente] == "div":
        return [_de(f"{s} .conteudo", "y: -40, opacity: 0", "y: 0, opacity: 1", 0.3, "power3.out", t),
                _de(f"{s} .costura", "scaleX: 0", "scaleX: 1", 0.35, "power3.out", t)]
    return []


def _contador(c: Cena, p: Contador) -> list[str]:
    linhas = _conta(c.k, 0.0, p.valor, c.inicio + 0.05, c.fim - c.inicio)
    if p.marcos:
        t = c.batidas[0]
        dur = round(max(0.3, min(0.8, c.fim - t - 0.1)), 2)
        linhas.append(_de(f"#m{c.k}-prog", "scaleX: 0", "scaleX: 1", dur, "power2.inOut", t))
    return linhas


def _valor_cheio(c: Cena, p: ValorCheio) -> list[str]:
    linhas = [_de(f"#m{c.k}-rot", "y: -20, opacity: 0", "y: 0, opacity: 1", 0.3, "power2.out", c.inicio),
              *_conta(c.k, p.de or 0.0, p.valor, c.inicio + 0.1, c.fim - c.inicio)]
    if p.selo:
        linhas.append(_de(f"#m{c.k}-selo", "scale: 0, rotation: -12", "scale: 1, rotation: 0", 0.4,
                          "back.out(2)", c.batidas[0]))
    return linhas


def _comparacao(c: Cena, p: Comparacao) -> list[str]:
    s, t = f"#m{c.k}", c.inicio
    linhas = [_de(f"{s} .base", "scaleX: 0", "scaleX: 1", 0.25, "power2.out", t),
              _de(f"{s} .c0 .barra", "scaleY: 0", "scaleY: 1", 0.35, "power3.out", t + 0.02),
              _de(f"{s} .c1 .barra", "scaleY: 0", "scaleY: 1", 0.45, "power3.out", t + 0.08),
              _de(f"{s} .valor, {s} .coluna .rotulo", "opacity: 0", "opacity: 1", 0.2, "none", t + 0.2)]
    if p.carimbo:
        linhas.append(_de(f"#m{c.k}-carimbo", "scale: 2.4, opacity: 0, rotation: -20",
                          "scale: 1, opacity: 1, rotation: -6", 0.25, "power4.in",
                          max(c.batidas[0], t + 0.15)))
    return linhas


def _chat(c: Cena) -> list[str]:
    k, t = c.k, c.inicio
    dig = t + min(1.0, max(0.5, (c.fim - t) * 0.4))
    pula = 'y: -14, duration: 0.25, ease: "sine.inOut", stagger: 0.12, yoyo: true, repeat: 3'
    return [_de(f"#m{k}-perg", "scale: 0.75, opacity: 0", "scale: 1, opacity: 1", 0.18, "power2.out",
                t + 0.15),
            _de(f"#m{k}-dig", "scale: 0", "scale: 1", 0.3, "back.out(2)", dig),
            f'tl.fromTo("#m{k}-dig i", {{ y: 0 }}, {{ {pula} }}, {_t(dig + 0.2)});']


def _lista(c: Cena, p: Lista) -> list[str]:
    linhas = []
    for j, t in enumerate(c.batidas):
        linhas += [_de(f"#m{c.k}-i{j}", "x: -120, opacity: 0", "x: 0, opacity: 1", 0.4, "expo.out", t),
                   _de(f"#m{c.k}-i{j} .n", "scale: 0", "scale: 1", 0.3, "back.out(2.2)", t + 0.15)]
    return linhas


def _rota(c: Cena, p: Rota) -> list[str]:
    k, t = c.k, c.inicio
    t2 = max(c.batidas[0], t + 0.5)
    linhas = [_de(f"#m{k}-p1", "y: -80, opacity: 0", "y: 0, opacity: 1", 0.4, "bounce.out", t + 0.05),
              _de(f"#m{k}-n1", "opacity: 0", "opacity: 1", 0.3, "none", t + 0.2),
              _de(f"#m{k}-rota", "strokeDashoffset: 900, opacity: 0", "strokeDashoffset: 0, opacity: 1",
                  round(max(0.3, t2 - t - 0.2), 2), "power1.inOut", t + 0.2),
              _de(f"#m{k}-p2", "y: -80, opacity: 0", "y: 0, opacity: 1", 0.4, "bounce.out", t2),
              _de(f"#m{k}-n2", "opacity: 0", "opacity: 1", 0.3, "none", t2 + 0.2)]
    if p.selo:
        linhas.append(_de(f"#m{k}-selo", "scale: 0.6, opacity: 0", "scale: 1, opacity: 1", 0.35,
                          "back.out(2)", min(max(c.batidas[1], t2 + 0.3), c.fim - 0.4)))
    return linhas


def _proprias(c: Cena) -> list[str]:
    p = c.params
    match p:
        case Contador():
            return _contador(c, p)
        case ValorCheio():
            return _valor_cheio(c, p)
        case Comparacao():
            return _comparacao(c, p)
        case Chat():
            return _chat(c)
        case Lista():
            return _lista(c, p)
        case Rota():
            return _rota(c, p)
        case Capa():
            return []


def animacoes(cenas: list[Cena]) -> str:
    return "\n".join(f"      {linha}" for c in cenas for linha in (*_entrada(c), *_proprias(c)))
