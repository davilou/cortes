"""Enquadramento do Short: posição FIXA por plano de câmera (spec produção §4.1; testes/TEMPLATES.md).

Dentro de um plano a câmera virtual não se mexe (seguir o rosto o tempo todo deixou o espectador
tonto na rodada 1). A posição é a mediana do rosto no plano e muda com corte seco na troca de câmera.
A detecção roda fora deste Python: render/visao/rosto.py, no venv do ComfyUI (onnxruntime).
"""
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cortes.render.processo import ErroRender, Rodar, exigir

JANELA = (1080, 1920)
ALVO = (540, 700)   # onde o rosto fica na tela 9:16 (protótipo: CAM_CHEIO da rodada 1)


@dataclass(frozen=True)
class Ponto:
    t: float
    x: float
    y: float
    corte: bool


@dataclass(frozen=True)
class Rosto:
    largura: int
    altura: int
    pontos: tuple[Ponto, ...]
    cortes: tuple[float, ...] = ()   # instantes reais das trocas de câmera (cortes_de_camera)


def _ponto(p: Any) -> Ponto:
    if not isinstance(p, dict) or not isinstance(p.get("corte"), bool):
        raise ValueError(f"ponto inválido: {p!r}")
    return Ponto(float(p["t"]), float(p["x"]), float(p["y"]), p["corte"])


def _cortes(valores: Any) -> tuple[float, ...]:
    if not isinstance(valores, list) or not all(isinstance(v, (int, float)) for v in valores):
        raise ValueError(f"cortes inválido: {valores!r}")
    cortes = tuple(float(v) for v in valores)
    if any(v < 0 for v in cortes) or any(a >= b for a, b in zip(cortes, cortes[1:], strict=False)):
        raise ValueError(f"cortes deveria ser crescente e não-negativo: {cortes!r}")
    return cortes


def ler_rosto(arquivo: Path) -> Rosto:
    try:
        d = json.loads(arquivo.read_text(encoding="utf-8"))
        largura, altura = d["largura"], d["altura"]
        if not (isinstance(largura, int) and isinstance(altura, int) and largura > 0 and altura > 0):
            raise ValueError("largura/altura deveriam ser inteiros positivos")
        pontos = tuple(_ponto(p) for p in d["pontos"])
        if not pontos:
            raise ValueError("nenhum ponto de rosto")
        return Rosto(largura, altura, pontos, _cortes(d.get("cortes", [])))
    except (OSError, KeyError, TypeError, ValueError) as ex:
        raise ErroRender(f"{arquivo}: rosto inválido ({ex})") from ex


def escala(r: Rosto) -> float:
    return JANELA[1] / r.altura


def largura_quadro(r: Rosto) -> int:
    return round(r.largura * escala(r))


def _pontos_por_intervalo(r: Rosto) -> list[list[Ponto]]:
    """Um grupo de pontos por intervalo entre trocas reais de câmera: [0, c1), [c1, c2), ...,
    [cN, fim). O limite vem de `r.cortes` (o instante real), não do primeiro ponto amostrado
    depois do corte — a amostragem pode só pegar o rosto de novo um pouco depois."""
    limites = [0.0, *r.cortes, float("inf")]
    grupos: list[list[Ponto]] = [[] for _ in range(len(limites) - 1)]
    for p in r.pontos:
        for i in range(len(limites) - 1):
            if limites[i] <= p.t < limites[i + 1]:
                grupos[i].append(p)
                break
    return grupos


def trilha_fixa(r: Rosto) -> list[list[float]]:
    """[t, x, y, 1] no início de cada plano: deslocamento do quadro (≤ 0) que leva a mediana do
    rosto ao ALVO sem mostrar borda. Um plano por intervalo entre trocas reais de câmera; `t` é o
    início do intervalo (o instante real do corte), não o tempo do primeiro ponto nele. Plano sem
    nenhum ponto (a amostragem perdeu o rosto logo depois do corte) herda a posição do plano
    anterior; o primeiro, sem anterior, herda a do próximo que tiver ponto. Se nenhum plano tiver
    ponto, é erro — não há posição nenhuma para herdar. O 1 final pede corte seco ao template."""
    limites = [0.0, *r.cortes, float("inf")]
    grupos = _pontos_por_intervalo(r)
    medianas: list[tuple[float, float] | None] = [
        (statistics.median(p.x for p in g), statistics.median(p.y for p in g)) if g else None
        for g in grupos
    ]
    if all(m is None for m in medianas):
        raise ErroRender("nenhum plano de câmera tem ponto de rosto")
    for i in range(1, len(medianas)):
        medianas[i] = medianas[i] or medianas[i - 1]
    for i in range(len(medianas) - 2, -1, -1):
        medianas[i] = medianas[i] or medianas[i + 1]

    e = escala(r)
    jw, jh = JANELA
    qw, qh = r.largura * e, r.altura * e
    res: list[list[float]] = []
    for i, m in enumerate(medianas):
        assert m is not None
        x, y = m
        res.append([limites[i], round(min(0.0, max(jw - qw, ALVO[0] - x * e)), 1),
                    round(min(0.0, max(jh - qh, ALVO[1] - y * e)), 1), 1])
    return res


def medir_rosto(
    trecho: Path, destino: Path, script: Path, py_visao: Path, modelo: Path, rodar: Rodar,
) -> None:
    args = [str(py_visao), str(script), str(trecho), str(modelo), str(destino)]
    exigir(rodar, args, None, "detecção de rosto")
