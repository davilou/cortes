"""API da produção com a transcrição colada do YouTube (spec produção §4.2)."""
import json
from pathlib import Path

import pytest

from cortes.painel.servidor import Config
from cortes.producao.estado import gravar, ler, marcar, novo
from cortes.producao.etapas import ARQUIVO_FONTE
from cortes.producao.rotas import TRANSCRICAO_MAX_BYTES
from tests.amostras import AMOSTRA
from tests.test_producao_rotas import AGORA, NOVO, montar, preparar_concluido


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
    (AMOSTRA.replace("0:18", "0:05", 1), "linha 3: tempo 0:05 não é maior que o anterior"),
    (AMOSTRA.replace("0:18", "0:75", 1), "linha 3: tempo inválido '0:75'"),
    ("0:01\nsó isso\n", "transcrição curta demais: 2 palavras"),
    ("   ", "sem palavras"),
], ids=["tempo-nao-cresce", "tempo-invalido", "curta", "vazia"])
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
    (AMOSTRA.replace("0:18", "0:75", 1), "transcrição colada: linha 3: tempo inválido"),
    ("0:01\nsó isso\n", "transcrição colada: transcrição curta demais"),
    (AMOSTRA + "x" * TRANSCRICAO_MAX_BYTES, "transcrição colada grande demais"),
], ids=["tempo-invalido", "curta", "grande"])
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


def test_colar_com_a_fila_processando_o_episodio_e_422(cfg: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    pasta = episodio_com_legenda_em_erro(cfg)
    c, fila = montar(cfg)
    situacao = fila.situacao()
    monkeypatch.setattr(fila, "situacao", lambda: {**situacao, "atual": {"episodio": "abcdefghijk",
                                                                          "etapa": "legenda"}})
    r = c.post("/api/episodios/abcdefghijk/transcricao", json={"transcricao": AMOSTRA})
    assert r.status_code == 422 and "sendo processado agora" in r.json()["detail"]
    assert not (pasta / "transcricao.txt").exists()


def test_colar_com_legenda_ok_ou_rodando_e_422(cfg: Config) -> None:
    pasta = episodio_com_legenda_em_erro(cfg)
    c, _ = montar(cfg)
    for situacao in ("ok", "rodando"):
        gravar(pasta, marcar(ler(pasta), "legenda", situacao, AGORA))
        r = c.post("/api/episodios/abcdefghijk/transcricao", json={"transcricao": AMOSTRA})
        assert r.status_code == 422 and f"está '{situacao}'" in r.json()["detail"]
        assert not (pasta / "transcricao.txt").exists()


@pytest.mark.parametrize("marcador, esperado",
                         [("youtube", "youtube"), ("colada", "colada"), (None, "colada")])
def test_fonte_legenda_segue_o_marcador_de_quem_gerou_palavras(cfg: Config, marcador: str | None,
                                                               esperado: str) -> None:
    pasta = episodio_com_legenda_em_erro(cfg)
    for nome in ("legenda.pt.json3", "transcricao.txt", "palavras.json"):
        (pasta / nome).write_text("[]", encoding="utf-8")
    if marcador is not None:
        (pasta / ARQUIVO_FONTE).write_text(marcador, encoding="utf-8")
    c, _ = montar(cfg)
    assert c.get("/api/producao").json()["episodios"][0]["fonte_legenda"] == esperado
