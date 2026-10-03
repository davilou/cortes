from dataclasses import replace
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from cortes.painel.servidor import Config, criar_app
from cortes.producao.estado import EstadoEpisodio, gravar, ler, marcar
from cortes.producao.fila import Fila
from cortes.producao.render import reabrir_render
from cortes.render.corte import (
    Edicoes,
    concluir,
    cortes_do_episodio,
    gravar_corte,
    iniciar,
    ler_corte,
    novo_corte,
    pasta_corte,
    reenfileirar,
)
from tests.test_producao_rotas import CAND, preparar_concluido

AGORA = datetime(2026, 10, 2, 9)
EP = "/api/episodios/abcdefghijk"


def montar(cfg: Config, rodadas: list[str] | None = None) -> tuple[TestClient, Fila]:
    def rodar(nome: str, pasta: Path, e: EstadoEpisodio) -> None:
        if rodadas is not None:
            rodadas.append(nome)

    fila = Fila(cfg.raiz, rodar, lambda: AGORA, antes=lambda p: reabrir_render(p, AGORA))
    app = criar_app(cfg, executar=lambda a, c: "", abrir=lambda a, c: None, fila=fila)
    return TestClient(app, base_url="http://127.0.0.1"), fila


def test_renderizar_em_f1_num_episodio_f7_cria_o_corte_em_f1_e_reabre_a_etapa(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    rodadas: list[str] = []
    c, fila = montar(cfg, rodadas)
    r = c.post(f"{EP}/cortes/0/renderizar", json={"formato": "f1"})
    assert r.status_code == 202 and fila.situacao()["na_fila"] == ["abcdefghijk"]
    assert ler_corte(pasta_corte(pasta, 0)).formato == "f1"
    fila.processar("abcdefghijk")
    assert rodadas == ["render"]   # o gancho reabriu só a etapa render


def test_renderizar_recusa(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    c, _ = montar(cfg)
    assert "não existe" in c.post(f"{EP}/cortes/7/renderizar", json={}).json()["detail"]
    assert "formato 'f4'" in c.post(f"{EP}/cortes/0/renderizar", json={"formato": "f4"}).json()["detail"]
    c.post(f"{EP}/cortes/0/renderizar", json={})
    assert "já está na fila" in c.post(f"{EP}/cortes/0/renderizar", json={}).json()["detail"]
    gravar(pasta, marcar(ler(pasta), "momentos", "pendente", AGORA))
    assert "momentos" in c.post(f"{EP}/cortes/0/renderizar", json={}).json()["detail"]


def test_renderizar_recusa_com_etapa_render_em_erro(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    gravar(pasta, marcar(ler(pasta), "render", "erro", AGORA, "falhou"))
    c, _ = montar(cfg)
    r = c.post(f"{EP}/cortes/0/renderizar", json={})
    assert r.status_code == 422
    assert "tentar de novo" in r.json()["detail"]
    assert not (pasta / "cortes" / "0" / "corte.json").exists()


def test_detalhe_traz_cortes_e_resumo(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    gravar_corte(pasta_corte(pasta, 0), concluir(novo_corte(0, CAND, "f7")))
    c, _ = montar(cfg)
    d = c.get(EP).json()
    assert d["cortes"][0]["video"] == f"{EP}/cortes/0/video" and d["candidatos"][0]["corte"] == "pronto"
    assert d["render"] == {"prontos": 1, "total": 1, "rodando": None, "erros": 0}
    assert c.get("/api/producao").json()["episodios"][0]["render"]["prontos"] == 1


def test_video_do_corte_e_download(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    corte = concluir(novo_corte(0, CAND, "f7"))
    gravar_corte(pasta_corte(pasta, 0), corte)
    (pasta_corte(pasta, 0) / "short-v1.mp4").write_bytes(b"mp4")
    c, _ = montar(cfg)
    assert c.get(f"{EP}/cortes/0/video").content == b"mp4"
    r = c.get(f"{EP}/cortes/0/video", params={"baixar": "true"})
    assert 'attachment; filename="abcdefghijk-0-v1.mp4"' in r.headers["content-disposition"]
    assert c.get(f"{EP}/cortes/3/video").status_code == 422
    assert cortes_do_episodio(pasta) == [corte]


def test_cancelar_com_versao_volta_a_pronto(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    gravar_corte(pasta_corte(pasta, 0), reenfileirar(concluir(novo_corte(0, CAND, "f7")), "f1"))
    c, _ = montar(cfg)
    assert c.post(f"{EP}/cortes/0/cancelar").status_code == 200
    corte = ler_corte(pasta_corte(pasta, 0))
    assert corte.status == "pronto" and corte.versao == 1


def test_cancelar_sem_versao_apaga_o_corte(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    c, _ = montar(cfg)
    c.post(f"{EP}/cortes/0/renderizar", json={"formato": "f1"})
    assert c.post(f"{EP}/cortes/0/cancelar").status_code == 200
    assert not pasta_corte(pasta, 0).exists() and cortes_do_episodio(pasta) == []
    assert c.get(EP).json()["candidatos"][0]["corte"] is None


def test_cancelar_sem_versao_com_edicao_fica_em_erro(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    gravar_corte(pasta_corte(pasta, 0), replace(novo_corte(0, CAND, "f7"), edicoes=Edicoes({1: "x"})))
    c, _ = montar(cfg)
    assert c.post(f"{EP}/cortes/0/cancelar").status_code == 200
    corte = ler_corte(pasta_corte(pasta, 0))
    assert corte.status == "erro" and corte.erro == "render cancelado" and corte.edicoes.legenda == {1: "x"}


def test_cancelar_recusa_corte_renderizando_ou_inexistente(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    gravar_corte(pasta_corte(pasta, 0), iniciar(novo_corte(0, CAND, "f7")))
    c, _ = montar(cfg)
    r = c.post(f"{EP}/cortes/0/cancelar")
    assert r.status_code == 422 and "já começou" in r.json()["detail"]
    assert ler_corte(pasta_corte(pasta, 0)).status == "renderizando"
    r = c.post(f"{EP}/cortes/3/cancelar")
    assert r.status_code == 422 and "não existe" in r.json()["detail"]


def test_cancelar_renderizar_de_novo_restaura_o_formato_da_versao_pronta(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    gravar_corte(pasta_corte(pasta, 0), concluir(novo_corte(0, CAND, "f7")))
    c, _ = montar(cfg)
    assert c.post(f"{EP}/cortes/0/renderizar", json={"formato": "f1"}).status_code == 202
    assert c.post(f"{EP}/cortes/0/cancelar").status_code == 200
    corte = ler_corte(pasta_corte(pasta, 0))
    assert corte.status == "pronto" and corte.formato == "f7"
