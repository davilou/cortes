"""Fixtures compartilhadas: a raiz falsa do painel (nicho, contas, formatos, skill, retrato)."""
import json
from datetime import date, datetime
from pathlib import Path

import pytest

from cortes.painel.retratos import Retrato, VideoRetrato, salvar_retrato
from cortes.painel.servidor import Config

PERFIL = """nicho: financas
filtro_tema: "x"
rubrica: {gancho_3s: 0.3, autocontido: 0.25, espanto: 0.2, historia_ou_virada: 0.1, fechamento: 0.15}
bonus: {humor: "faz rir"}
penalidade: {}
duracao_s: {min: 20, max: 90}
"""
CONTAS = 'contas:\n  - {id: grana, nome: Grana, handle: "@grana", nicho: financas, perfil_studio: grana}\n'


@pytest.fixture
def cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setattr("shutil.which", lambda _: "C:/fake/node.exe")
    nicho = tmp_path / "nichos" / "financas"
    (nicho / "exemplos").mkdir(parents=True)
    (nicho / "perfil.yaml").write_text(PERFIL, encoding="utf-8")
    for arq in ("bons.jsonl", "ruins.jsonl"):
        (nicho / "exemplos" / arq).write_text("", encoding="utf-8")
    (tmp_path / "contas").mkdir()
    (tmp_path / "contas" / "contas.yaml").write_text(CONTAS, encoding="utf-8")
    (tmp_path / "contas" / "formatos.yaml").write_text(
        "formatos:\n  f7: {nome: Conversa}\n", encoding="utf-8")
    (tmp_path / "testes" / "f7-conversa-comediante").mkdir(parents=True)
    estatico = tmp_path / "web"
    estatico.mkdir()
    (estatico / "index.html").write_text("<h1>painel</h1>", encoding="utf-8")
    skill = tmp_path / "skill"
    (skill / "src").mkdir(parents=True)
    (skill / "src" / "cli.mjs").write_text("", encoding="utf-8")
    (skill / "node_modules").mkdir()
    nomes = ("falante", "conversa", "hormozi", "gameplay", "desfoque", "broll", "motion")
    tpls = [f"render/formatos/{n}.tpl" for n in nomes]
    for arq in (*tpls, "render/visao/rosto.py", "visao/python.exe", "visao/rosto.onnx"):
        (tmp_path / arq).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / arq).write_text("", encoding="utf-8")
    bib = tmp_path / "biblioteca" / "trilhas"
    (bib / "final").mkdir(parents=True)
    fases = [{"id": "A", "mood": "neutro", "bpm": 76}, {"id": "B", "mood": "tensao", "bpm": 70},
             {"id": "C", "mood": "leve", "bpm": 84}]
    (bib / "plano.json").write_text(json.dumps({"fases": fases}), encoding="utf-8")
    for f in fases:
        (bib / "final" / f"{f['id']}.m4a").write_bytes(b"m4a")
    c = Config(raiz=tmp_path, skill_dir=skill, estatico=estatico, py_visao=tmp_path / "visao" / "python.exe",
               modelo_rosto=tmp_path / "visao" / "rosto.onnx")
    videos = tuple(
        VideoRetrato(f"vid{i}xxxxxxx", f"O comediante {i}", date(2026, 10, 1), 30.0, 100 * i, 80.0, 24.0, 1)
        for i in range(1, 4))
    salvar_retrato(c.retratos, Retrato("grana", datetime(2026, 10, 9, 9), videos))   # dia 7 + 1: medido
    return c
