"""Perfil de nicho: o que cortar (spec §4.1)."""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CRITERIOS = ("gancho_3s", "autocontido", "espanto", "historia_ou_virada", "fechamento")


@dataclass(frozen=True)
class Perfil:
    nicho: str
    filtro_tema: str
    rubrica: dict[str, float]
    bonus: list[str]
    penalidade: list[str]
    duracao_min: float
    duracao_max: float
    exemplos_bons: list[dict[str, Any]]
    exemplos_ruins: list[dict[str, Any]]


def _jsonl(caminho: Path) -> list[dict[str, Any]]:
    linhas = caminho.read_text(encoding="utf-8").splitlines()  # ausente → FileNotFoundError
    return [json.loads(linha) for linha in linhas if linha.strip()]


def carregar_perfil(pasta_nicho: Path) -> Perfil:
    d = yaml.safe_load((pasta_nicho / "perfil.yaml").read_text(encoding="utf-8"))
    rubrica = {k: float(v) for k, v in d["rubrica"].items()}
    if set(rubrica) != set(CRITERIOS):
        raise ValueError(f"critérios da rubrica devem ser {CRITERIOS}, vieram {sorted(rubrica)}")
    if abs(sum(rubrica.values()) - 1.0) > 1e-6:
        raise ValueError(f"pesos da rubrica somam {sum(rubrica.values())}, deveriam somar 1")
    dur = d["duracao_s"]
    if not 0 < dur["min"] < dur["max"]:
        raise ValueError(f"duração inválida: {dur}")
    return Perfil(
        nicho=d["nicho"], filtro_tema=d["filtro_tema"], rubrica=rubrica,
        bonus=list(d["bonus"]), penalidade=list(d["penalidade"]),
        duracao_min=float(dur["min"]), duracao_max=float(dur["max"]),
        exemplos_bons=_jsonl(pasta_nicho / "exemplos" / "bons.jsonl"),
        exemplos_ruins=_jsonl(pasta_nicho / "exemplos" / "ruins.jsonl"),
    )
