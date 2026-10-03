import json
import os
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cortes.painel.servidor import Config, criar_app
from cortes.producao.estado import EstadoEpisodio
from cortes.producao.fila import Fila
from cortes.producao.previas import Previas
from cortes.render.corte import Corte, Edicoes, concluir, gravar_corte, ler_corte, novo_corte, pasta_corte
from cortes.render.ilustracao import Deixa
from cortes.render.ilustracao_cache import Chave, Ilustracao, gravar_ilustracoes
from cortes.render.previa import RUNTIME
from tests.test_producao_rotas import preparar_concluido

AGORA = datetime(2026, 10, 2, 9)
EP = "/api/episodios/abcdefghijk"
PALAVRAS = [{"texto": t, "inicio": float(i), "fim": i + 0.8} for i, t in
            enumerate(["Antes.", "Mas", "eu", "ganhei", "porra,", "dez", "mil", "reais.", "Depois"])]
ROSTO = {"formato": 2, "largura": 1920, "altura": 1080, "cortes": [2.0],
         "amostras": [{"t": 0.0, "rostos": [{"x": 960, "y": 540, "r": 80, "conf": 0.9}]},
                      {"t": 2.5, "rostos": [{"x": 400, "y": 500, "r": 80, "conf": 0.9},
                                            {"x": 1500, "y": 500, "r": 80, "conf": 0.8}]},
                      {"t": 2.75, "rostos": [{"x": 410, "y": 500, "r": 80, "conf": 0.9},
                                             {"x": 1510, "y": 500, "r": 80, "conf": 0.8}]}]}


class Ambiente:
    def __init__(self, cfg: Config) -> None:
        self.pasta = preparar_concluido(cfg)
        (self.pasta / "palavras.json").write_text(json.dumps(PALAVRAS), encoding="utf-8")
        self.d = pasta_corte(self.pasta, 0)
        gravar_corte(self.d, concluir(novo_corte(0, {"inicio": 1.0, "fim": 7.8, "titulo": "Ganhei"}, "f7")))
        (self.d / "short-v1.mp4").write_bytes(b"v1")
        (self.d / "rosto.json").write_text(json.dumps(ROSTO), encoding="utf-8")
        proj = self.d / "projeto"
        (proj / "assets").mkdir(parents=True)
        (proj / "assets" / "trecho.mp4").write_bytes(b"trecho")
        time.sleep(0.01)
        (proj / "index.html").write_text("<html>\n  <head>\n</head></html>", encoding="utf-8")
        self.montados: list[Corte] = []
        self.rodados: list[list[str]] = []
        self.previas = Previas(cfg.raiz, lambda p, c: self.montados.append(c))
        fila = Fila(cfg.raiz, self._nada, lambda: AGORA)
        app = criar_app(cfg, executar=lambda a, c: "", abrir=lambda a, c: None, fila=fila,
                        previas=self.previas, rodar=self._rodar)
        self.c = TestClient(app, base_url="http://127.0.0.1")

    def _nada(self, nome: str, pasta: Path, e: EstadoEpisodio) -> None:
        return None

    def _rodar(self, args: list[str], cwd: Path | None) -> tuple[int, str]:
        self.rodados.append(args)
        Path(args[-1]).write_bytes(b"jpg")
        return 0, ""


def test_estado_do_editor(cfg: Config) -> None:
    a = Ambiente(cfg)
    d = a.c.get(f"{EP}/cortes/0/editor").json()
    assert (d["inicio_palavra"], d["fim_palavra"]) == (1, 7) and d["aviso_inicio"] is True
    assert [p["dentro"] for p in d["palavras"]] == [False] + [True] * 7 + [False]
    url_previa = d["previa"]["url"]
    assert d["previa"]["situacao"] == "pronta"
    assert url_previa.startswith(f"{EP}/cortes/0/previa/index.html?v=")
    assert [(p["k"], len(p["pessoas"]), p["escolha"]) for p in d["planos"]] == [(0, 1, 0), (1, 2, 0)]
    assert d["versoes"] == [{"versao": 1, "url": f"{EP}/cortes/0/video?versao=1"}]
    assert d["editavel"] is True and d["formatos"] == ["f7", "f1", "f6", "f5", "f8", "f9"]


def test_previa_pronta_quando_nao_alterado_mesmo_com_corte_json_mais_novo(cfg: Config) -> None:
    """O render grava o index.html e só DEPOIS o corte.json (`concluir`); sem edição pendente
    (`alterado is False`) o index.html mais velho não quer dizer desatualizado — item 3."""
    a = Ambiente(cfg)
    os.utime(a.d / "projeto" / "index.html", (1, 1))
    assert a.c.get(f"{EP}/cortes/0/editor").json()["previa"]["situacao"] == "pronta"


def test_previa_desatualizada_quando_alterado_e_index_mais_velho_que_o_corte(cfg: Config) -> None:
    a = Ambiente(cfg)
    gravar_corte(a.d, replace(ler_corte(a.d), alterado=True))
    os.utime(a.d / "projeto" / "index.html", (1, 1))
    assert a.c.get(f"{EP}/cortes/0/editor").json()["previa"]["situacao"] == "desatualizada"


def test_arquivos_da_previa(cfg: Config) -> None:
    a = Ambiente(cfg)
    html = a.c.get(f"{EP}/cortes/0/previa/index.html").text
    assert RUNTIME in html
    r = a.c.get(f"{EP}/cortes/0/previa/assets/trecho.mp4")
    assert r.content == b"trecho" and r.headers["cache-control"] == "no-store"
    assert a.c.get(f"{EP}/cortes/0/previa/../corte.json").status_code in (404, 422)
    assert a.c.get(f"{EP}/cortes/0/previa/hyperframes.json").status_code == 422


def test_miniatura_gerada_uma_vez(cfg: Config) -> None:
    a = Ambiente(cfg)
    assert a.c.get(f"{EP}/cortes/0/planos/1/pessoas/1").content == b"jpg"
    a.c.get(f"{EP}/cortes/0/planos/1/pessoas/1")
    assert len(a.rodados) == 1
    assert a.c.get(f"{EP}/cortes/0/planos/1/pessoas/5").status_code == 422


def test_video_por_versao(cfg: Config) -> None:
    a = Ambiente(cfg)
    assert a.c.get(f"{EP}/cortes/0/video", params={"versao": 1}).content == b"v1"
    assert a.c.get(f"{EP}/cortes/0/video", params={"versao": 2}).status_code == 422


def test_editar_inicio_pede_previa_e_marca_alterado(cfg: Config) -> None:
    a = Ambiente(cfg)
    d = a.c.post(f"{EP}/cortes/0/editar", json={"inicio_palavra": 2}).json()
    assert d["corte"]["inicio"] == 2.0 and d["corte"]["alterado"] is True
    assert d["previa"]["situacao"] == "preparando" and d["editavel"] is False
    assert "preparada" in a.c.post(f"{EP}/cortes/0/renderizar", json={}).json()["detail"]
    a.previas.processar("abcdefghijk", 0)
    assert a.montados[0].inicio == 2.0
    assert a.c.get(f"{EP}/cortes/0/editor").json()["previa"]["situacao"] == "pronta"


def test_editar_legenda_e_palavroes(cfg: Config) -> None:
    a = Ambiente(cfg)
    d = a.c.post(f"{EP}/cortes/0/editar", json={"legenda": {"5": "10"}, "mascarar_palavroes": True}).json()
    textos = {p["i"]: p["texto"] for p in d["palavras"]}
    assert textos[5] == "10" and textos[4] == "p*rra,"


def test_escolher_pessoa(cfg: Config) -> None:
    a = Ambiente(cfg)
    d = a.c.post(f"{EP}/cortes/0/editar", json={"rosto": [1, 1]}).json()
    assert d["planos"][1]["escolha"] == 1
    a.previas.processar("abcdefghijk", 0)   # a edição pediu prévia; sem isso a próxima é recusada
    assert "pessoa 3" in a.c.post(f"{EP}/cortes/0/editar", json={"rosto": [1, 3]}).json()["detail"]


def test_edicao_recusada_com_o_corte_na_fila(cfg: Config) -> None:
    a = Ambiente(cfg)
    a.c.post(f"{EP}/cortes/0/renderizar", json={})
    assert "fila" in a.c.post(f"{EP}/cortes/0/editar", json={"titulo": "Novo"}).json()["detail"]


def test_pedir_previa(cfg: Config) -> None:
    a = Ambiente(cfg)
    assert a.c.post(f"{EP}/cortes/0/previa").json()["previa"]["situacao"] == "preparando"


def test_rosto_formato_velho_abre_o_editor_com_planos_vazios_e_rosto_erro(cfg: Config) -> None:
    """rosto.json do plano B (formato 1) não pode derrubar o editor (GET/POST 422) — item 1."""
    a = Ambiente(cfg)
    (a.d / "rosto.json").write_text(json.dumps({"largura": 1920, "altura": 1080, "cortes": [],
        "pontos": [{"t": 0.0, "x": 960, "y": 540, "corte": False}]}), encoding="utf-8")
    d = a.c.get(f"{EP}/cortes/0/editor").json()
    assert d["planos"] == [] and "meça o rosto de novo" in d["rosto_erro"]


def test_editar_titulo_funciona_com_rosto_formato_velho(cfg: Config) -> None:
    a = Ambiente(cfg)
    (a.d / "rosto.json").write_text(json.dumps({"largura": 1920, "altura": 1080, "cortes": [],
        "pontos": [{"t": 0.0, "x": 960, "y": 540, "corte": False}]}), encoding="utf-8")
    d = a.c.post(f"{EP}/cortes/0/editar", json={"titulo": "Novo título"}).json()
    assert d["corte"]["titulo"] == "Novo título" and d["rosto_erro"] is not None


def test_escolha_antiga_fica_invalida_quando_a_pessoa_nao_existe_mais(cfg: Config) -> None:
    """edicoes.rostos pode sobreviver a uma nova medição do rosto e apontar pra pessoa que não
    existe mais no plano — a tela usa o padrão e avisa, em vez de quebrar — item 4."""
    a = Ambiente(cfg)
    c = ler_corte(a.d)
    gravar_corte(a.d, replace(c, edicoes=Edicoes(rostos={1: 5})))
    d = a.c.get(f"{EP}/cortes/0/editor").json()
    plano1 = next(p for p in d["planos"] if p["k"] == 1)
    assert plano1["escolha"] == plano1["padrao"] and plano1["escolha_invalida"] is True


def test_palavras_json_ausente_e_erro_claro(cfg: Config) -> None:
    a = Ambiente(cfg)
    (a.pasta / "palavras.json").unlink()
    d = a.c.get(f"{EP}/cortes/0/editor").json()
    assert "transcrição deste episódio ainda não rodou" in d["detail"]


def test_miniatura_recusada_com_o_corte_na_fila(cfg: Config) -> None:
    a = Ambiente(cfg)
    a.c.post(f"{EP}/cortes/0/renderizar", json={})
    r = a.c.get(f"{EP}/cortes/0/planos/1/pessoas/1")
    assert r.status_code == 422 and "preparado" in r.json()["detail"]


def test_miniatura_recusada_com_a_previa_preparando(cfg: Config) -> None:
    a = Ambiente(cfg)
    a.previas.pedir("abcdefghijk", 0)
    r = a.c.get(f"{EP}/cortes/0/planos/1/pessoas/1")
    assert r.status_code == 422 and "preparado" in r.json()["detail"]


def ambiente_f9(cfg: Config) -> Ambiente:
    a = Ambiente(cfg)
    gravar_corte(a.d, replace(ler_corte(a.d), formato="f9"))
    pasta = a.d / "ilustracao"
    pasta.mkdir()
    (pasta / "D1-c2.jpg").write_bytes(b"vans")
    ilus = [Ilustracao(1, Deixa(1.2, 2.6, "Vans", "b"), pasta / "D1-c2.jpg", "http://loja/vans", "é o tênis",
                       (), False),
            Ilustracao(2, Deixa(4.5, 5.7, "bota", "b"), None, None, "nenhuma é a bota", (), False)]
    gravar_ilustracoes(pasta, Chave(0.7, 7.8, "h"), ilus, None)
    (a.d / "projeto" / "assets" / "ilus-1.jpg").write_bytes(b"vans")
    return a


def test_editor_lista_as_ilustracoes_do_f9(cfg: Config) -> None:
    a = ambiente_f9(cfg)
    d = a.c.get(f"{EP}/cortes/0/editor").json()
    vans, bota = d["ilustracoes"]
    assert vans["coisa"] == "Vans" and vans["imagem"].startswith(f"{EP}/cortes/0/ilustracao/1?v=")
    assert vans["fonte_url"] == "http://loja/vans" and d["ilustracao_erro"] is None
    assert bota["imagem"] is None and bota["motivo"] == "nenhuma é a bota"
    assert a.c.get(vans["imagem"]).content == b"vans"
    r = a.c.get(f"{EP}/cortes/0/ilustracao/2")
    assert r.status_code == 422 and "sem imagem" in r.json()["detail"]


def test_imagem_da_ilustracao_caminho_feliz(cfg: Config) -> None:
    r = ambiente_f9(cfg).c.get(f"{EP}/cortes/0/ilustracao/1")
    assert r.status_code == 200 and r.content == b"vans" and r.headers["content-type"] == "image/jpeg"


def test_editor_sem_ilustracoes_fora_do_f9(cfg: Config) -> None:
    d = Ambiente(cfg).c.get(f"{EP}/cortes/0/editor").json()
    assert d["ilustracoes"] == [] and d["ilustracao_erro"] is None


def test_cache_da_ilustracao_invalido_nao_derruba_o_editor(cfg: Config) -> None:
    a = ambiente_f9(cfg)
    (a.d / "ilustracao" / "ilustracao.json").write_text('{"formato": 2}', encoding="utf-8")
    d = a.c.get(f"{EP}/cortes/0/editor").json()
    assert d["ilustracoes"] == [] and "cache da ilustração inválido" in d["ilustracao_erro"]


def test_imagem_da_ilustracao_recusada_com_a_previa_preparando(cfg: Config) -> None:
    a = ambiente_f9(cfg)
    a.previas.pedir("abcdefghijk", 0)
    r = a.c.get(f"{EP}/cortes/0/ilustracao/1")
    assert r.status_code == 422 and "preparado" in r.json()["detail"]


def test_previa_serve_o_cartao_do_f9(cfg: Config) -> None:
    a = ambiente_f9(cfg)
    assert a.c.get(f"{EP}/cortes/0/previa/assets/ilus-1.jpg").content == b"vans"
    assert a.c.get(f"{EP}/cortes/0/previa/assets/ilus-1.png").status_code == 422


@pytest.mark.parametrize("nome", ["fundo.mp4", "gameplay.mp4"])
def test_previa_serve_o_video_de_fundo_do_f8_e_do_f5(cfg: Config, nome: str) -> None:
    a = Ambiente(cfg)
    (a.d / "projeto" / "assets" / nome).write_bytes(b"fundo")
    r = a.c.get(f"{EP}/cortes/0/previa/assets/{nome}")
    assert r.content == b"fundo" and r.headers["content-type"] == "video/mp4"
    assert a.c.get(f"{EP}/cortes/0/previa/assets/outro.mp4").status_code == 422
    travessia = f"{EP}/cortes/0/previa/assets%2F..%2Fassets%2F{nome}"   # %2F: o cliente não normaliza
    assert a.c.get(travessia).status_code == 422


def test_refazer_ilustracao_apaga_o_cache_e_os_cartoes_e_pede_a_previa(cfg: Config) -> None:
    a = ambiente_f9(cfg)
    (a.d / "projeto" / "assets" / "ilus-9.jpg").write_bytes(b"velha")
    d = a.c.post(f"{EP}/cortes/0/ilustracao/refazer").json()
    assert d["previa"]["situacao"] == "preparando" and d["ilustracoes"] == []
    assets = a.d / "projeto" / "assets"
    assert not (a.d / "ilustracao").exists() and not list(assets.glob("ilus-*.jpg"))
    assert (assets / "trecho.mp4").exists()


def test_refazer_ilustracao_recusado_com_a_previa_preparando(cfg: Config) -> None:
    a = ambiente_f9(cfg)
    a.previas.pedir("abcdefghijk", 0)
    r = a.c.post(f"{EP}/cortes/0/ilustracao/refazer")
    assert r.status_code == 422 and "preparada" in r.json()["detail"]
    assert (a.d / "ilustracao" / "ilustracao.json").exists()


def test_refazer_ilustracao_recusado_com_o_corte_na_fila(cfg: Config) -> None:
    a = ambiente_f9(cfg)
    a.c.post(f"{EP}/cortes/0/renderizar", json={})
    r = a.c.post(f"{EP}/cortes/0/ilustracao/refazer")
    assert r.status_code == 422 and "fila" in r.json()["detail"]
    assert (a.d / "ilustracao" / "ilustracao.json").exists()


def test_refazer_ilustracao_recusado_fora_do_f9(cfg: Config) -> None:
    r = Ambiente(cfg).c.post(f"{EP}/cortes/0/ilustracao/refazer")
    assert r.status_code == 422 and "f9" in r.json()["detail"]
