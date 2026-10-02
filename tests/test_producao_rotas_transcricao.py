"""API da produção com a transcrição colada do YouTube (spec produção §4.2)."""
import json
from pathlib import Path

import pytest

from cortes.painel.servidor import Config
from cortes.producao.estado import ler
from cortes.producao.rotas import TRANSCRICAO_MAX_BYTES
from tests.test_producao_rotas import NOVO, montar, preparar_concluido
from tests.test_producao_transcricao_colada import AMOSTRA


def test_transcricao_colada_e_gravada_com_o_episodio(cfg: Config) -> None:
    c, fila = montar(cfg)
    r = c.post("/api/episodios", json={**NOVO, "transcricao": AMOSTRA})
    assert r.status_code == 201
    pasta = cfg.raiz / "episodios" / "abcdefghijk"
    assert (pasta / "transcricao.txt").read_text(encoding="utf-8") == AMOSTRA
    assert ler(pasta).nicho == "financas" and fila.situacao()["na_fila"] == ["abcdefghijk"]
    ep = c.get("/api/producao").json()["episodios"][0]
    assert ep["fonte_legenda"] == "colada"


def test_sem_transcricao_nao_grava_arquivo(cfg: Config) -> None:
    c, _ = montar(cfg)
    assert c.post("/api/episodios", json=NOVO).status_code == 201
    assert not (cfg.raiz / "episodios" / "abcdefghijk" / "transcricao.txt").exists()
    assert c.get("/api/producao").json()["episodios"][0]["fonte_legenda"] is None


@pytest.mark.parametrize("texto, erro", [
    ("Transcrição\n" + AMOSTRA, "linha 1: texto antes do primeiro tempo"),
    (AMOSTRA.replace("0:18", "0:75", 1), "linha 3: tempo inválido '0:75'"),
    ("0:01\nsó isso\n", "transcrição curta demais: 2 palavras"),
    ("   ", "sem palavras"),
])
def test_transcricao_ruim_e_422_e_nada_e_criado(cfg: Config, texto: str, erro: str) -> None:
    c, fila = montar(cfg)
    r = c.post("/api/episodios", json={**NOVO, "transcricao": texto})
    assert r.status_code == 422 and erro in r.json()["detail"]
    assert r.json()["detail"].startswith("transcrição colada: ")
    assert not (cfg.raiz / "episodios").exists() and fila.situacao()["na_fila"] == []


def test_transcricao_grande_demais_e_422(cfg: Config) -> None:
    c, _ = montar(cfg)
    r = c.post("/api/episodios", json={**NOVO, "transcricao": AMOSTRA + "x" * TRANSCRICAO_MAX_BYTES})
    assert r.status_code == 422 and "grande demais" in r.json()["detail"]
    assert not (cfg.raiz / "episodios").exists()


def test_fonte_legenda_youtube_quando_ha_palavras_sem_transcricao(cfg: Config) -> None:
    pasta: Path = preparar_concluido(cfg)
    (pasta / "palavras.json").write_text(json.dumps([]), encoding="utf-8")
    c, _ = montar(cfg)
    assert c.get("/api/producao").json()["episodios"][0]["fonte_legenda"] == "youtube"
