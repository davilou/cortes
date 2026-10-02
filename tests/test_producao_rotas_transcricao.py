"""API da produção com a transcrição colada do YouTube (spec produção §4.2)."""
import json
from pathlib import Path

import pytest

from cortes.painel.servidor import Config
from cortes.producao.estado import gravar, ler, marcar, novo
from cortes.producao.rotas import TRANSCRICAO_MAX_BYTES
from tests.test_producao_rotas import AGORA, NOVO, montar, preparar_concluido
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
], ids=["antes-do-tempo", "tempo-invalido", "curta", "vazia"])
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


def episodio_com_legenda_em_erro(cfg: Config) -> Path:
    pasta = cfg.raiz / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    e = novo("abcdefghijk", "https://youtu.be/abcdefghijk", "financas", 5, "f7", AGORA)
    e = marcar(marcar(e, "video", "ok", AGORA), "legenda", "erro", AGORA,
               "YouTube limitou as requisições; tente em alguns minutos")
    gravar(pasta, e)
    return pasta


def test_colar_em_episodio_com_legenda_em_erro_reabre_e_enfileira(cfg: Config) -> None:
    pasta = episodio_com_legenda_em_erro(cfg)
    c, fila = montar(cfg)
    r = c.post("/api/episodios/abcdefghijk/transcricao", json={"transcricao": AMOSTRA})
    assert r.status_code == 202 and r.json() == {"enfileirado": True}
    assert (pasta / "transcricao.txt").read_text(encoding="utf-8") == AMOSTRA
    assert ler(pasta).etapas["legenda"].situacao == "pendente"
    assert ler(pasta).etapas["video"].situacao == "ok"
    assert fila.situacao()["na_fila"] == ["abcdefghijk"]
    assert c.get("/api/producao").json()["episodios"][0]["fonte_legenda"] == "colada"


def test_colar_sem_etapa_em_erro_so_grava(cfg: Config) -> None:
    pasta = cfg.raiz / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    gravar(pasta, novo("abcdefghijk", "u", "financas", 5, "f7", AGORA))
    c, fila = montar(cfg)
    r = c.post("/api/episodios/abcdefghijk/transcricao", json={"transcricao": AMOSTRA})
    assert r.status_code == 202 and r.json() == {"enfileirado": False}
    assert (pasta / "transcricao.txt").exists() and fila.situacao()["na_fila"] == []


def test_colar_com_legenda_pronta_e_422(cfg: Config) -> None:
    pasta = episodio_com_legenda_em_erro(cfg)
    (pasta / "palavras.json").write_text("[]", encoding="utf-8")
    c, fila = montar(cfg)
    r = c.post("/api/episodios/abcdefghijk/transcricao", json={"transcricao": AMOSTRA})
    assert r.status_code == 422 and r.json()["detail"] == "a legenda deste episódio já está pronta"
    assert not (pasta / "transcricao.txt").exists() and fila.situacao()["na_fila"] == []
    assert ler(pasta).etapas["legenda"].situacao == "erro"


@pytest.mark.parametrize("texto, erro", [
    ("Transcrição\n" + AMOSTRA, "transcrição colada: linha 1: texto antes do primeiro tempo"),
    ("0:01\nsó isso\n", "transcrição colada: transcrição curta demais"),
    (AMOSTRA + "x" * TRANSCRICAO_MAX_BYTES, "transcrição colada grande demais"),
], ids=["antes-do-tempo", "curta", "grande"])
def test_colar_texto_ruim_e_422_e_nada_e_gravado(cfg: Config, texto: str, erro: str) -> None:
    pasta = episodio_com_legenda_em_erro(cfg)
    c, fila = montar(cfg)
    r = c.post("/api/episodios/abcdefghijk/transcricao", json={"transcricao": texto})
    assert r.status_code == 422 and r.json()["detail"].startswith(erro)
    assert not (pasta / "transcricao.txt").exists() and fila.situacao()["na_fila"] == []
    assert ler(pasta).etapas["legenda"].situacao == "erro"


@pytest.mark.parametrize("id, erro", [("zzzzzzzzzzz", "não está na produção"),
                                      ("curto", "id de episódio inválido")])
def test_colar_em_id_desconhecido_e_422(cfg: Config, id: str, erro: str) -> None:
    c, _ = montar(cfg)
    r = c.post(f"/api/episodios/{id}/transcricao", json={"transcricao": AMOSTRA})
    assert r.status_code == 422 and erro in r.json()["detail"]
    assert not (cfg.raiz / "episodios").exists()
