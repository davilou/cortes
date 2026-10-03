"""Enquadramento do Short: posição FIXA por plano de câmera, na pessoa escolhida
(spec produção §4.1 e §5 "quem aparece"; testes/TEMPLATES.md).

Dentro de um plano a câmera virtual não se mexe (seguir o rosto o tempo todo deixou o espectador
tonto na rodada 1). Em cada plano — intervalo entre trocas reais de câmera — os rostos detectados
viram pessoas pela posição x (câmera parada: cada pessoa fica no seu lugar). O enquadramento usa
a pessoa escolhida no editor ou, por padrão, a mais confiável (mais detecções, depois maior
confiança). A detecção roda fora deste Python: render/visao/rosto.py, no venv do ComfyUI.
"""
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cortes.render.processo import ErroRender, Rodar, exigir

FORMATO_ROSTO = 2          # rosto.json com até 3 rostos por amostra (render/visao/rosto.py)
JANELA = (1080, 1920)
ALVO = (540, 700)          # onde o rosto fica na tela 9:16 (protótipo: CAM_CHEIO da rodada 1)
# f5 (gameplay): quem fala na metade de cima. Protótipo: corte.trilha(d, 1.0, (1080, 960), (540, 380)),
# com a fonte a 1080 de altura (escala 1,0 em 1080p) para sobrar margem de enquadramento na janela.
JANELA_METADE = (1080, 960)
ALVO_METADE = (540, 380)
ALTURA_QUADRO_METADE = 1080
PASSO_S = 0.25             # passo da amostragem em render/visao/rosto.py
SEPARA = 0.08              # rostos a mais que isso (fração da largura) no eixo x são pessoas diferentes
RUIDO = 0.2                # pessoa com menos que isso × as detecções da maior é ruído do detector
MAX_PESSOAS = 3


@dataclass(frozen=True)
class Face:
    x: float
    y: float
    r: float
    conf: float


@dataclass(frozen=True)
class Amostra:
    t: float
    rostos: tuple[Face, ...]


@dataclass(frozen=True)
class Rosto:
    largura: int
    altura: int
    amostras: tuple[Amostra, ...]
    cortes: tuple[float, ...]   # instantes reais das trocas de câmera


@dataclass(frozen=True)
class Pessoa:
    x: float
    y: float
    r: float
    n: int
    conf: float


@dataclass(frozen=True)
class Plano:
    k: int
    ini: float
    fim: float
    pessoas: tuple[Pessoa, ...]   # da esquerda para a direita
    padrao: int | None            # índice da mais confiável; None sem rosto


def _numero(v: Any, nome: str) -> float:
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        raise ValueError(f"{nome} deveria ser número, veio {v!r}")
    return float(v)


def _face(f: Any) -> Face:
    if not isinstance(f, dict):
        raise ValueError(f"rosto inválido: {f!r}")
    return Face(*(_numero(f[c], c) for c in ("x", "y", "r", "conf")))


def _amostra(a: Any) -> Amostra:
    if not isinstance(a, dict) or not isinstance(a.get("rostos"), list):
        raise ValueError(f"amostra inválida: {a!r}")
    return Amostra(_numero(a["t"], "t"), tuple(_face(f) for f in a["rostos"]))


def _cortes(valores: Any) -> tuple[float, ...]:
    if not isinstance(valores, list):
        raise ValueError(f"cortes inválido: {valores!r}")
    cortes = tuple(_numero(v, "corte") for v in valores)
    if any(v < 0 for v in cortes) or any(a >= b for a, b in zip(cortes, cortes[1:], strict=False)):
        raise ValueError(f"cortes deveria ser crescente e não-negativo: {cortes!r}")
    return cortes


def ler_rosto(arquivo: Path) -> Rosto:
    try:
        d = json.loads(arquivo.read_text(encoding="utf-8"))
        if d.get("formato") != FORMATO_ROSTO:
            raise ValueError(f"formato {d.get('formato')!r}, esperado {FORMATO_ROSTO}: meça o rosto de novo")
        largura, altura = d["largura"], d["altura"]
        if not (isinstance(largura, int) and isinstance(altura, int) and largura > 0 and altura > 0):
            raise ValueError("largura/altura deveriam ser inteiros positivos")
        cortes = _cortes(d["cortes"])
        amostras = tuple(_amostra(a) for a in d["amostras"])
        if not any(a.rostos for a in amostras):
            raise ValueError("nenhuma amostra com rosto")
        return Rosto(largura, altura, amostras, cortes)
    except (OSError, KeyError, TypeError, ValueError) as ex:
        raise ErroRender(f"{arquivo}: rosto inválido ({ex})") from ex


def escala_cheio(r: Rosto) -> float:
    return JANELA[1] / r.altura


def largura_quadro(r: Rosto) -> int:
    return round(r.largura * escala_cheio(r))


def escala_metade(r: Rosto) -> float:
    return ALTURA_QUADRO_METADE / r.altura


def quadro_metade(r: Rosto) -> tuple[int, int]:
    e = escala_metade(r)
    return round(r.largura * e), round(r.altura * e)


def pessoas(faces: list[Face], largura: int) -> tuple[Pessoa, ...]:
    """Agrupa os rostos de um plano pela posição x; descarta o ruído; até MAX_PESSOAS."""
    if not faces:
        return ()
    fs = sorted(faces, key=lambda f: f.x)
    grupos: list[list[Face]] = [[fs[0]]]
    for f in fs[1:]:
        # Vão medido contra o PRIMEIRO rosto do grupo (não o último): single-linkage deixava uma
        # cadeia de detecções intermediárias emendar duas pessoas que nunca ficaram próximas entre si.
        if f.x - grupos[-1][0].x > SEPARA * largura:
            grupos.append([f])
        else:
            grupos[-1].append(f)
    ps = [Pessoa(statistics.median(f.x for f in g), statistics.median(f.y for f in g),
                 statistics.median(f.r for f in g), len(g), round(statistics.fmean(f.conf for f in g), 3))
          for g in grupos]
    maior = max(p.n for p in ps)
    ps = sorted((p for p in ps if p.n >= RUIDO * maior), key=lambda p: (-p.n, -p.conf))[:MAX_PESSOAS]
    return tuple(sorted(ps, key=lambda p: p.x))


def _padrao(ps: tuple[Pessoa, ...]) -> int | None:
    if not ps:
        return None
    return max(range(len(ps)), key=lambda i: (ps[i].n, ps[i].conf))


def planos(r: Rosto) -> list[Plano]:
    """Um plano por intervalo entre trocas reais de câmera: [0, c1), [c1, c2), …, [cN, fim)."""
    limites = [0.0, *r.cortes]
    fim_total = r.amostras[-1].t + PASSO_S if r.amostras else 0.0
    res: list[Plano] = []
    for k, ini in enumerate(limites):
        fim = limites[k + 1] if k + 1 < len(limites) else max(fim_total, ini)
        faces = [f for a in r.amostras if ini <= a.t < fim for f in a.rostos]
        ps = pessoas(faces, r.largura)
        res.append(Plano(k, ini, round(fim, 2), ps, _padrao(ps)))
    return res


def _escolhida(p: Plano, escolhas: dict[int, int]) -> Pessoa | None:
    if not p.pessoas:
        return None
    j = escolhas.get(p.k, p.padrao)
    if j is None or not 0 <= j < len(p.pessoas):
        raise ErroRender(
            f"plano {p.k}: pessoa {j} não existe (há {len(p.pessoas)}) — escolha de novo no editor")
    return p.pessoas[j]


def trilha_fixa(r: Rosto, escolhas: dict[int, int], janela: tuple[int, int] = JANELA,
                alvo: tuple[int, int] = ALVO, escala: float | None = None) -> list[list[float]]:
    """[t, x, y, 1] no início de cada plano: deslocamento do quadro (≤ 0) que leva a pessoa do plano
    ao `alvo` da `janela` sem mostrar borda. Sem `escala`, vale a da tela cheia (fonte a 1920 de
    altura). Plano sem rosto herda a posição do anterior (o primeiro, a do próximo com rosto);
    nenhum plano com rosto é erro. O 1 final pede corte seco ao template."""
    pls = planos(r)
    invalidos = set(escolhas) - {p.k for p in pls if p.pessoas}
    if invalidos:
        raise ErroRender(f"plano {sorted(invalidos)[0]} não existe ou não tem pessoa para escolher — "
                         "escolha de novo no editor")
    alvos = [_escolhida(p, escolhas) for p in pls]
    if all(a is None for a in alvos):
        raise ErroRender("nenhum plano de câmera tem rosto")
    for i in range(1, len(alvos)):
        alvos[i] = alvos[i] or alvos[i - 1]
    for i in range(len(alvos) - 2, -1, -1):
        alvos[i] = alvos[i] or alvos[i + 1]
    e = escala_cheio(r) if escala is None else escala
    jw, jh = janela
    qw, qh = r.largura * e, r.altura * e
    res: list[list[float]] = []
    for p, a in zip(pls, alvos, strict=True):
        assert a is not None
        res.append([p.ini, round(min(0.0, max(jw - qw, alvo[0] - a.x * e)), 1),
                    round(min(0.0, max(jh - qh, alvo[1] - a.y * e)), 1), 1])
    return res


def medir_rosto(
    trecho: Path, destino: Path, script: Path, py_visao: Path, modelo: Path, rodar: Rodar,
) -> None:
    args = [str(py_visao), str(script), str(trecho), str(modelo), str(destino)]
    exigir(rodar, args, None, "detecção de rosto")
