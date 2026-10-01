import json
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cortes.painel.coleta import ErroColeta
from cortes.painel.dados import ErroPainel
from cortes.painel.retratos import Retrato, VideoRetrato, salvar_retrato
from cortes.painel.servidor import Config, criar_app

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
    c = Config(raiz=tmp_path, skill_dir=skill, estatico=estatico)
    videos = tuple(
        VideoRetrato(f"vid{i}xxxxxxx", f"O comediante {i}", date(2026, 10, 1), 30.0, 100 * i, 80.0, 24.0, 1)
        for i in range(1, 4))
    salvar_retrato(c.retratos, Retrato("grana", datetime(2026, 10, 20, 9), videos))
    return c


def falhar(args: list[str], cwd: Path) -> str:
    raise ErroColeta("login expirado")


def cliente(cfg: Config) -> TestClient:
    return TestClient(criar_app(cfg, executar=falhar, abrir=lambda args, cwd: None))


LIGACAO = {"link": "https://youtube.com/shorts/vid1xxxxxxx", "conta": "grana",
           "corte": "testes/f7-conversa-comediante", "formato": "f7", "temas": ["humor"],
           "podcast": "PrimoCast"}


def test_estado(cfg: Config) -> None:
    e = cliente(cfg).get("/api/estado").json()
    assert e["contas"][0]["id"] == "grana" and e["contas"][0]["ultimo_retrato"] is not None
    assert e["formatos"]["f7"]["nome"] == "Conversa" and e["temas"] == ["humor"]
    assert e["nichos"] == ["financas"] and e["rodando"] is False


def test_ligar_e_comparar(cfg: Config) -> None:
    c = cliente(cfg)
    assert c.post("/api/ligar", json=LIGACAO).status_code == 200
    linhas = {linha["video_id"]: linha for linha in c.get("/api/shorts").json()}
    assert linhas["vid1xxxxxxx"]["etiquetas"]["formato"] == "f7"
    assert linhas["vid2xxxxxxx"]["etiquetas"] is None
    comp = c.get("/api/comparar", params={"dim": "formato"}).json()
    assert comp["grupos"][0]["chave"] == "f7" and comp["medidos"] == 1


def test_ligar_video_fora_do_retrato(cfg: Config) -> None:
    r = cliente(cfg).post("/api/ligar", json={**LIGACAO, "link": "https://youtu.be/naoexiste00"})
    assert r.status_code == 422 and "último retrato" in r.json()["detail"]


def test_ligar_formato_invalido(cfg: Config) -> None:
    r = cliente(cfg).post("/api/ligar", json={**LIGACAO, "formato": "f9"})
    assert r.status_code == 422 and "formato 'f9'" in r.json()["detail"]


def test_sugestoes(cfg: Config) -> None:
    sug = cliente(cfg).get("/api/sugestoes/vid1xxxxxxx").json()
    assert sug[0]["caminho"] == "testes/f7-conversa-comediante" and sug[0]["formato"] == "f7"


def test_atualizar_registra_falha(cfg: Config) -> None:
    app = criar_app(cfg, executar=falhar, abrir=lambda args, cwd: None)
    c = TestClient(app)
    assert c.post("/api/atualizar", json={}).status_code == 202
    app.state.coleta.fio.join(timeout=5)
    conta = c.get("/api/estado").json()["contas"][0]
    assert conta["coleta"] == {"conta": "grana", "ok": False, "mensagem": "conta 'grana': login expirado"}


def test_nova_conta_com_nicho_inexistente_nao_grava(cfg: Config) -> None:
    antes = (cfg.raiz / "contas" / "contas.yaml").read_text(encoding="utf-8")
    r = cliente(cfg).post("/api/contas", json={"id": "riso", "nome": "Riso", "handle": "@riso",
                                               "nicho": "humor", "perfil_studio": "riso"})
    assert r.status_code == 422 and "nicho 'humor'" in r.json()["detail"]
    assert (cfg.raiz / "contas" / "contas.yaml").read_text(encoding="utf-8") == antes


def test_nova_conta_valida(cfg: Config) -> None:
    r = cliente(cfg).post("/api/contas", json={"id": "bolso", "nome": "Bolso", "handle": "@bolso",
                                               "nicho": "financas", "perfil_studio": "bolso"})
    assert r.status_code == 201
    assert [c["id"] for c in cliente(cfg).get("/api/estado").json()["contas"]] == ["grana", "bolso"]


def test_dimensao_invalida(cfg: Config) -> None:
    assert cliente(cfg).get("/api/comparar", params={"dim": "cor"}).status_code == 422


def test_nao_sobe_sem_a_skill(cfg: Config) -> None:
    with pytest.raises(ErroPainel, match="cli.mjs"):
        criar_app(Config(cfg.raiz, cfg.raiz / "nada", cfg.estatico))


def test_publicados_gravado_em_disco(cfg: Config) -> None:
    cliente(cfg).post("/api/ligar", json=LIGACAO)
    linha = json.loads(cfg.publicados.read_text(encoding="utf-8").splitlines()[0])
    assert linha["publicado_em"] == "2026-10-01" and linha["etiquetas"]["podcast"] == "PrimoCast"
