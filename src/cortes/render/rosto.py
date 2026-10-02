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


def _ponto(p: Any) -> Ponto:
    if not isinstance(p, dict) or not isinstance(p.get("corte"), bool):
        raise ValueError(f"ponto inválido: {p!r}")
    return Ponto(float(p["t"]), float(p["x"]), float(p["y"]), p["corte"])


def ler_rosto(arquivo: Path) -> Rosto:
    try:
        d = json.loads(arquivo.read_text(encoding="utf-8"))
        largura, altura = d["largura"], d["altura"]
        if not (isinstance(largura, int) and isinstance(altura, int) and largura > 0 and altura > 0):
            raise ValueError("largura/altura deveriam ser inteiros positivos")
        pontos = tuple(_ponto(p) for p in d["pontos"])
        if not pontos:
            raise ValueError("nenhum ponto de rosto")
        return Rosto(largura, altura, pontos)
    except (OSError, KeyError, TypeError, ValueError) as ex:
        raise ErroRender(f"{arquivo}: rosto inválido ({ex})") from ex


def escala(r: Rosto) -> float:
    return JANELA[1] / r.altura


def largura_quadro(r: Rosto) -> int:
    return round(r.largura * escala(r))


def planos(pontos: tuple[Ponto, ...]) -> list[list[Ponto]]:
    res: list[list[Ponto]] = [[]]
    for p in pontos:
        if p.corte and res[-1]:
            res.append([])
        res[-1].append(p)
    return res


def trilha_fixa(r: Rosto) -> list[list[float]]:
    """[t, x, y, 1] no início de cada plano: deslocamento do quadro (≤ 0) que leva a mediana do
    rosto ao ALVO sem mostrar borda. O 1 final pede corte seco ao template."""
    e = escala(r)
    jw, jh = JANELA
    qw, qh = r.largura * e, r.altura * e
    res: list[list[float]] = []
    for k, pl in enumerate(planos(r.pontos)):
        x = statistics.median(p.x for p in pl)
        y = statistics.median(p.y for p in pl)
        t = 0.0 if k == 0 else pl[0].t
        res.append([t, round(min(0.0, max(jw - qw, ALVO[0] - x * e)), 1),
                    round(min(0.0, max(jh - qh, ALVO[1] - y * e)), 1), 1])
    return res


def medir_rosto(
    trecho: Path, destino: Path, script: Path, py_visao: Path, modelo: Path, rodar: Rodar,
) -> None:
    args = [str(py_visao), str(script), str(trecho), str(modelo), str(destino)]
    exigir(rodar, args, None, "detecção de rosto")
