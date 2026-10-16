"""f10 (Motion v2) pelo pipeline, com o LLM falso: as cenas do f3 no layout novo, o recorte da cabeça
e os efeitos sonoros nos assets."""
import json
import re
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

from cortes.render.corte import Edicoes
from cortes.render.pipeline import montar_projeto
from tests.test_render_motion_etapa import LLM, _episodio
from tests.test_render_pipeline import REPO, C, Falso

C10 = replace(C, formato="f10", fim=16.0)


def _montar(tmp: Path, llm: LLM, c: Any = C10) -> tuple[Path, str, Falso]:
    pasta = tmp / "episodios" / "abcdefghijk"
    if not pasta.exists():
        pasta = _episodio(tmp)
        shutil.copytree(REPO / "biblioteca" / "sfx", tmp / "biblioteca" / "sfx")
        (tmp / "u2net.onnx").write_bytes(b"m")
    f = Falso()
    montar_projeto(pasta, c, tmp, replace(f.dep(), chamar_llm=llm, modelo_recorte=tmp / "u2net.onnx"))
    return pasta, (pasta / "cortes" / "0" / "projeto" / "index.html").read_text(encoding="utf-8"), f


def _json_de(html: str, funcao: str) -> list[list[float]]:
    m = re.search(rf'posicionar\("{funcao}", (\[\[.*?\]\])\);', html)
    assert m is not None
    trilha: list[list[float]] = json.loads(m.group(1))
    return trilha


def test_f10_monta_o_bolo_de_camadas(tmp_path: Path) -> None:
    pasta, html, f = _montar(tmp_path, LLM())
    assert "{{" not in html and 'class="clip faixa solo"' in html   # o primeiro painel vai sozinho
    assert '[[0.0, "gancho"], [2.0, "claro"]' in html and '"escuro"' in html
    assert 'src="assets/recorte.webm"' in html and "--brand: #7b5cff" in html
    assert 'src="assets/sfx-whoosh.wav"' in html and 'src="assets/sfx-pop.wav"' in html
    assert '<i data-t="' in html                                   # legenda palavra a palavra
    card, cabeca = _json_de(html, "#q-card"), _json_de(html, "#q-cabeca")
    assert [y + 200 for _, _, y, _ in card] == [y for _, _, y, _ in cabeca]
    assets = pasta / "cortes" / "0" / "projeto" / "assets"
    assert (assets / "recorte.webm").exists() and (assets / "sfx-pop.wav").exists()
    assert f.chamadas.count("py-visao") == 2                     # rosto e recorte


def test_f10_e_f3_dividem_as_cenas_e_o_recorte_tem_cache(tmp_path: Path) -> None:
    llm = LLM()
    _montar(tmp_path, llm)
    _, _, f = _montar(tmp_path, llm)
    assert len(llm.prompts) == 1 and f.chamadas.count("py-visao") == 0
    _, html, _ = _montar(tmp_path, llm, replace(C10, formato="f3"))
    assert len(llm.prompts) == 1 and 'class="clip faixa"' in html   # mesmas cenas, layout do f3


def test_f10_ignora_o_tema_do_editor(tmp_path: Path) -> None:
    _, html, _ = _montar(tmp_path, LLM(), replace(C10, edicoes=Edicoes(trilha="A", tema="noite")))
    assert "--brand: #7b5cff" in html and "#d9b46a" not in html
