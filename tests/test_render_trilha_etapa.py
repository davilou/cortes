import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from cortes.render.corte import Edicoes, novo_corte
from cortes.render.trilha import Medida
from cortes.render.trilha_etapa import TrilhaUsada, preparar_trilha
from cortes.render.trilha_mood import SCHEMA
from tests.test_render_trilha_biblioteca import biblioteca

C = novo_corte(0, {"inicio": 1.0, "fim": 11.0, "titulo": "T"}, "f7")


def tensao(prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
    assert schema is SCHEMA
    return {"mood": "tensao", "motivo": "perdeu dinheiro"}


def nunca(prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
    raise AssertionError("escolha manual não chama o LLM")


def medir(arq: Path) -> Medida:
    return Medida(-16.0, 10.0) if arq.name == "trecho.mp4" else Medida(-30.0, 90.0)


def corte_dir(tmp: Path) -> Path:
    d = tmp / "cortes" / "0"
    (d / "projeto" / "assets").mkdir(parents=True)
    (d / "projeto" / "assets" / "trecho.mp4").write_bytes(b"mp4")
    return d


def test_automatica_usa_o_mood_e_copia_a_cama(tmp_path: Path) -> None:
    bib, d = biblioteca(tmp_path / "bib"), corte_dir(tmp_path)
    html, usada = preparar_trilha(d, C, "perdi tudo", 10.0, bib, tensao, medir)
    assert usada == TrilhaUsada("B", "auto", "perdeu dinheiro", round(10 ** (-4 / 20), 6))
    assert (d / "projeto" / "assets" / "trilha.m4a").read_bytes() == b"m4a"
    assert html.count("<audio") == 1 and 'data-volume="0.630957"' in html


def test_manual_nao_chama_o_llm(tmp_path: Path) -> None:
    bib, d = biblioteca(tmp_path / "bib"), corte_dir(tmp_path)
    _, usada = preparar_trilha(d, replace(C, edicoes=Edicoes(trilha="C")), "x", 10.0, bib, nunca, medir)
    assert (usada.cama, usada.origem, usada.motivo) == ("C", "manual", None)


def test_sem_trilha_apaga_o_asset_e_nao_gera_audio(tmp_path: Path) -> None:
    bib, d = biblioteca(tmp_path / "bib"), corte_dir(tmp_path)
    preparar_trilha(d, C, "x", 10.0, bib, tensao, medir)
    html, usada = preparar_trilha(d, replace(C, edicoes=Edicoes(trilha="nenhuma")), "x", 10.0, bib,
                                  nunca, medir)
    assert html == "" and usada == TrilhaUsada(None, "manual", None, None)
    assert not (d / "projeto" / "assets" / "trilha.m4a").exists()


def test_cache_da_cama_fica_na_biblioteca(tmp_path: Path) -> None:
    bib, d = biblioteca(tmp_path / "bib"), corte_dir(tmp_path)
    preparar_trilha(d, C, "x", 10.0, bib, tensao, medir)
    assert set(json.loads((bib / "medidas.json").read_text(encoding="utf-8"))) == {"B"}
