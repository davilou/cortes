import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from cortes.render.corte import Edicoes, concluir, novo_corte
from cortes.render.pipeline import DepRender, janela, montar_projeto, renderizar_corte
from cortes.render.processo import ErroRender
from cortes.render.seo import SCHEMA as SCHEMA_SEO
from cortes.render.trilha import Medida
from cortes.render.trilha_mood import SCHEMA as SCHEMA_TRILHA
from tests.test_render_trilha_biblioteca import biblioteca

REPO = Path(__file__).resolve().parents[1]
ROSTO = {"formato": 2, "largura": 1920, "altura": 1080, "cortes": [],
        "amostras": [{"t": 0.0, "rostos": [{"x": 960, "y": 540, "r": 80, "conf": 0.9}]}]}
SEO = {"titulo": "Eu ganhei", "descricao": "Ele conta como ganhou.", "hashtags": ["#dinheiro"],
       "tags": ["ganhar dinheiro"]}


def responde_seo(prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
    if schema is SCHEMA_TRILHA:
        return {"mood": "neutro", "motivo": "conversa"}
    assert schema is SCHEMA_SEO, "o pipeline só chama o LLM para o SEO e a trilha fora do f3/f4"
    return SEO


class Falso:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def rodar(self, args: list[str], cwd: Path | None) -> tuple[int, str]:
        self.chamadas.append(args[0])
        if args[0] == "ffmpeg" or args[0] == "npx":
            Path(args[-1]).write_bytes(b"mp4")
        elif args[0] == "py-visao":
            Path(args[4]).write_text(json.dumps(ROSTO), encoding="utf-8")
        return 0, "ok"

    def dep(self) -> DepRender:
        def tom(audio: Path, ini: float, dur: float) -> np.ndarray:
            t = np.arange(int(dur * 16000)) / 16000
            return (0.5 * np.sin(2 * np.pi * 50 * t)).astype(np.float32)

        return DepRender(Path("py-visao"), Path("m.onnx"), "npx", self.rodar, tom, responde_seo,
                         medir_lufs=lambda a: Medida(-16.0, 90.0))


def episodio(tmp: Path) -> Path:
    shutil.copytree(REPO / "render", tmp / "render")
    biblioteca(tmp / "biblioteca" / "trilhas")
    pasta = tmp / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    palavras = [{"texto": "Eu", "inicio": 10.1, "fim": 10.5},
                {"texto": "ganhei.", "inicio": 10.5, "fim": 11.0}]
    (pasta / "palavras.json").write_text(json.dumps(palavras), encoding="utf-8")
    meta = {"titulo": "Episódio", "canal": "Podcast"}
    (pasta / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return pasta


# Trilha escolhida à mão: os LLMs falsos do f3/f4 (que derivam de C) não precisam responder o mood;
# o caminho automático tem teste próprio (test_trilha_automatica_pergunta_o_mood).
C = replace(novo_corte(0, {"inicio": 10.3, "fim": 14.0, "titulo": "T"}, "f7"), edicoes=Edicoes(trilha="A"))


def test_janela_da_folga_no_inicio() -> None:
    assert janela(C) == (10.0, 14.0)
    assert janela(replace(C, inicio=0.1)) == (0.0, 14.0)


def test_renderiza_o_corte_ponta_a_ponta(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, C, tmp_path, f.dep())
    d = pasta / "cortes" / "0"
    assert (d / "short-v1.mp4").exists() and f.chamadas == ["ffmpeg", "py-visao", "npx"]
    html = (d / "projeto" / "index.html").read_text(encoding="utf-8")
    assert "{{" not in html and "<span>Eu ganhei.</span>" in html and 'data-duration="4.0"' in html


def test_segunda_versao_reaproveita_trecho_e_rosto(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, C, tmp_path, f.dep())
    renderizar_corte(pasta, concluir(C), tmp_path, f.dep())
    assert f.chamadas == ["ffmpeg", "py-visao", "npx", "npx"]
    assert (pasta / "cortes" / "0" / "short-v2.mp4").exists()


def test_novo_inicio_refaz_trecho_e_rosto(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, C, tmp_path, f.dep())
    renderizar_corte(pasta, replace(concluir(C), inicio=11.0), tmp_path, f.dep())
    assert f.chamadas == ["ffmpeg", "py-visao", "npx", "ffmpeg", "py-visao", "npx"]


def test_rosto_json_apagado_refaz_trecho_mesmo_com_marcador(tmp_path: Path) -> None:
    """O marcador `recorte.json` não basta: se `rosto.json` (ou `trecho.mp4`) não existir mais,
    o cache não pode ser reaproveitado — senão o render seguinte usaria um rosto.json ausente."""
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, C, tmp_path, f.dep())
    (pasta / "cortes" / "0" / "rosto.json").unlink()
    renderizar_corte(pasta, concluir(C), tmp_path, f.dep())
    assert f.chamadas == ["ffmpeg", "py-visao", "npx", "ffmpeg", "py-visao", "npx"]


def test_rosto_json_formato_velho_refaz_trecho_mesmo_com_marcador(tmp_path: Path) -> None:
    """Um `rosto.json` do plano B (formato 1) não serve mais: o editor (plano C) precisa das
    pessoas por plano, que só existem no formato atual — por isso o cache é invalidado."""
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, C, tmp_path, f.dep())
    (pasta / "cortes" / "0" / "rosto.json").write_text(
        json.dumps({"largura": 1920, "altura": 1080, "cortes": [],
                    "pontos": [{"t": 0.0, "x": 960, "y": 540, "corte": False}]}), encoding="utf-8")
    renderizar_corte(pasta, concluir(C), tmp_path, f.dep())
    assert f.chamadas == ["ffmpeg", "py-visao", "npx", "ffmpeg", "py-visao", "npx"]


def test_projeto_aplica_legenda_e_mascara(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    c = replace(C, edicoes=Edicoes({0: "Eu,"}, (1,), {}))
    montar_projeto(pasta, c, tmp_path, f.dep())
    html = (pasta / "cortes" / "0" / "projeto" / "index.html").read_text(encoding="utf-8")
    assert "<span>Eu, g*nhei.</span>" in html and f.chamadas == ["ffmpeg", "py-visao"]


def test_novo_trecho_apaga_miniaturas_velhas(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    montar_projeto(pasta, C, tmp_path, f.dep())
    mini = pasta / "cortes" / "0" / "miniaturas"
    mini.mkdir()
    (mini / "p0-0.jpg").write_bytes(b"x")
    montar_projeto(pasta, replace(C, inicio=11.0), tmp_path, f.dep())
    assert not mini.exists()


def test_f8_gera_o_fundo_uma_vez_e_reaproveita(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    c = replace(C, formato="f8")
    renderizar_corte(pasta, c, tmp_path, f.dep())
    renderizar_corte(pasta, concluir(c), tmp_path, f.dep())
    assert f.chamadas == ["ffmpeg", "py-visao", "ffmpeg", "npx", "npx"]
    assets = pasta / "cortes" / "0" / "projeto" / "assets"
    assert (assets / "fundo.mp4").exists()
    html = (pasta / "cortes" / "0" / "projeto" / "index.html").read_text(encoding="utf-8")
    assert '<div id="titulo">T</div>' in html


def test_f5_gera_o_gameplay_uma_vez_e_refaz_com_trecho_novo(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    (tmp_path / "biblioteca" / "gameplay").mkdir(parents=True)
    (tmp_path / "biblioteca" / "gameplay" / "orbital.mp4").write_bytes(b"x")
    c = replace(C, formato="f5")
    renderizar_corte(pasta, c, tmp_path, f.dep())
    renderizar_corte(pasta, concluir(c), tmp_path, f.dep())
    assert f.chamadas == ["ffmpeg", "py-visao", "ffmpeg", "npx", "npx"]
    renderizar_corte(pasta, replace(concluir(c), inicio=11.0), tmp_path, f.dep())
    assert f.chamadas[5:] == ["ffmpeg", "py-visao", "ffmpeg", "npx"]


def test_f5_sem_gameplay_na_biblioteca_e_erro(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    with pytest.raises(ErroRender, match="sem gameplay"):
        renderizar_corte(pasta, replace(C, formato="f5"), tmp_path, f.dep())
    assert "npx" not in f.chamadas


class FalsoSemRosto(Falso):
    """`py-visao` sempre falha: simula detecção de rosto indisponível."""

    def rodar(self, args: list[str], cwd: Path | None) -> tuple[int, str]:
        if args[0] == "py-visao":
            return 1, "modelo não carregou"
        return super().rodar(args, cwd)


def test_f8_renderiza_mesmo_com_falha_na_deteccao_de_rosto(tmp_path: Path) -> None:
    """f8 (desfoque) não usa câmera nem metade: falha ao medir rosto não deve derrubar o render
    (revisão formatos novos, item 1). Sem `rosto.json`, o cache fica inválido — o próximo render
    tenta medir de novo."""
    pasta, f = episodio(tmp_path), FalsoSemRosto()
    c = replace(C, formato="f8")
    renderizar_corte(pasta, c, tmp_path, f.dep())
    d = pasta / "cortes" / "0"
    assert (d / "short-v1.mp4").exists() and not (d / "rosto.json").exists()


def test_falante_falha_na_deteccao_de_rosto_e_erro(tmp_path: Path) -> None:
    """f1 usa câmera (QW/TRILHA_CHEIO): a mesma falha de detecção, nesse formato, continua
    derrubando o render com uma causa clara."""
    pasta, f = episodio(tmp_path), FalsoSemRosto()
    with pytest.raises(ErroRender, match="detecção de rosto"):
        renderizar_corte(pasta, replace(C, formato="f1"), tmp_path, f.dep())


def test_render_grava_a_trilha_da_versao(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, C, tmp_path, f.dep())
    d = pasta / "cortes" / "0"
    assert json.loads((d / "short-v1.trilha.json").read_text(encoding="utf-8"))["cama"] == "A"
    html = (d / "projeto" / "index.html").read_text(encoding="utf-8")
    assert 'id="trilha-0"' in html and (d / "projeto" / "assets" / "trilha.m4a").exists()


def test_trilha_automatica_pergunta_o_mood(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, replace(C, edicoes=Edicoes()), tmp_path, f.dep())
    usada = json.loads((pasta / "cortes" / "0" / "short-v1.trilha.json").read_text(encoding="utf-8"))
    assert (usada["cama"], usada["origem"], usada["motivo"]) == ("A", "auto", "conversa")


def test_sem_trilha_nao_poe_audio(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, replace(C, edicoes=Edicoes(trilha="nenhuma")), tmp_path, f.dep())
    html = (pasta / "cortes" / "0" / "projeto" / "index.html").read_text(encoding="utf-8")
    assert "trilha-0" not in html and "{{" not in html
