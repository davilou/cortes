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
from cortes.render.ilustracao_cache import FORMATO, Chave, Fonte, Ilustracao, gravar_ilustracoes
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
    assert d["editavel"] is True and d["formatos"] == ["f7", "f1", "f6", "f5", "f8", "f4", "f3"]


def test_janela_da_transcricao_padrao_cobre_o_episodio_curto(cfg: Config) -> None:
    d = Ambiente(cfg).c.get(f"{EP}/cortes/0/editor").json()
    assert [p["i"] for p in d["palavras"]] == list(range(9))
    assert (d["tem_antes"], d["tem_depois"]) == (False, False)


def test_janela_da_transcricao_e_escolhida_por_lado(cfg: Config) -> None:
    """Corte 1.0–7.8: 0.5 s antes deixa a palavra 0 (em 0.0) de fora; 0.5 s depois pega a 8 (8.0)."""
    a = Ambiente(cfg)
    d = a.c.get(f"{EP}/cortes/0/editor?antes=0.5&depois=0.5").json()
    assert [p["i"] for p in d["palavras"]] == list(range(1, 9))
    assert (d["tem_antes"], d["tem_depois"]) == (True, False)
    d = a.c.get(f"{EP}/cortes/0/editor?antes=1&depois=0").json()
    assert [p["i"] for p in d["palavras"]] == list(range(8))
    assert (d["tem_antes"], d["tem_depois"]) == (False, True)


def test_janela_negativa_e_recusada(cfg: Config) -> None:
    assert Ambiente(cfg).c.get(f"{EP}/cortes/0/editor?antes=-1").status_code == 422


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


def ambiente_f4(cfg: Config) -> Ambiente:
    a = Ambiente(cfg)
    gravar_corte(a.d, replace(ler_corte(a.d), formato="f4"))
    pasta = a.d / "ilustracao"
    pasta.mkdir()
    (pasta / "D1-v2.mp4").write_bytes(b"trecho")
    (pasta / "D1-v2-q2.jpg").write_bytes(b"quadro")
    (pasta / "D2-c1-cheia.jpg").write_bytes(b"camisa")
    vans, camisa = Deixa(1.2, 2.6, "Vans", "b", "literal"), Deixa(3.0, 4.0, "camisa", "c", "literal")
    pandemia = Deixa(4.5, 5.7, "pandemia", "empty street", "acontecimento")
    ilus = [Ilustracao(1, vans, "video", pasta / "D1-v2.mp4", Fonte("https://yt/v", "Canal", "T"),
                       "é o tênis", (), False),
            Ilustracao(2, camisa, "foto", pasta / "D2-c1-cheia.jpg", Fonte("http://loja"), "só a foto",
                       (), False),
            Ilustracao(3, pandemia, None, None, None, "sem visual: nenhum vídeo", (), False),
            Ilustracao(4, camisa, "foto", pasta / "D2-c1-cheia.jpg", Fonte("javascript:alert(1)"), "ok", (),
                       False)]
    gravar_ilustracoes(pasta, Chave(0.7, 7.8, "h"), ilus, None)
    (a.d / "projeto" / "assets" / "broll-1.mp4").write_bytes(b"trecho")
    (a.d / "projeto" / "assets" / "broll-2.jpg").write_bytes(b"camisa")
    return a


def test_editor_lista_o_broll_do_f4_com_tipo_e_miniatura(cfg: Config) -> None:
    a = ambiente_f4(cfg)
    d = a.c.get(f"{EP}/cortes/0/editor").json()
    vans, camisa, pandemia, perigosa = d["broll"]
    assert (vans["midia"], camisa["midia"], pandemia["midia"]) == ("video", "foto", None)
    assert vans["miniatura"].startswith(f"{EP}/cortes/0/broll/1?v=") and d["broll_erro"] is None
    assert vans["fonte_url"] == "https://yt/v" and vans["canal"] == "Canal" and vans["tipo"] == "literal"
    assert pandemia["miniatura"] is None and pandemia["tipo"] == "acontecimento"
    assert camisa["fonte_url"] == "http://loja" and perigosa["fonte_url"] is None   # só http/https
    assert a.c.get(vans["miniatura"]).content == b"quadro"      # um quadro do vídeo
    assert a.c.get(camisa["miniatura"]).content == b"camisa"    # a própria foto
    r = a.c.get(f"{EP}/cortes/0/broll/3")
    assert r.status_code == 422 and "sem visual" in r.json()["detail"]


def test_miniatura_do_broll_e_jpeg(cfg: Config) -> None:
    r = ambiente_f4(cfg).c.get(f"{EP}/cortes/0/broll/1")
    assert r.status_code == 200 and r.content == b"quadro" and r.headers["content-type"] == "image/jpeg"


def test_editor_sem_broll_fora_do_f4(cfg: Config) -> None:
    d = Ambiente(cfg).c.get(f"{EP}/cortes/0/editor").json()
    assert d["broll"] == [] and d["broll_erro"] is None


def test_cache_do_broll_invalido_nao_derruba_o_editor(cfg: Config) -> None:
    a = ambiente_f4(cfg)
    (a.d / "ilustracao" / "ilustracao.json").write_text(f'{{"formato": {FORMATO}}}', encoding="utf-8")
    d = a.c.get(f"{EP}/cortes/0/editor").json()
    assert d["broll"] == [] and "cache da ilustração inválido" in d["broll_erro"]


def test_miniatura_do_broll_recusada_com_a_previa_preparando(cfg: Config) -> None:
    a = ambiente_f4(cfg)
    a.previas.pedir("abcdefghijk", 0)
    r = a.c.get(f"{EP}/cortes/0/broll/1")
    assert r.status_code == 422 and "preparado" in r.json()["detail"]


def test_previa_serve_os_clipes_do_f4_por_lista_fechada(cfg: Config) -> None:
    a = ambiente_f4(cfg)
    r = a.c.get(f"{EP}/cortes/0/previa/assets/broll-1.mp4")
    assert r.content == b"trecho" and r.headers["content-type"] == "video/mp4"
    r = a.c.get(f"{EP}/cortes/0/previa/assets/broll-2.jpg")
    assert r.content == b"camisa" and r.headers["content-type"] == "image/jpeg"
    for nome in ("broll-1.png", "broll-x.mp4", "broll-1.mp4.jpg", "ilus-1.jpg", "broll-9.mp4"):
        assert a.c.get(f"{EP}/cortes/0/previa/assets/{nome}").status_code == 422


@pytest.mark.parametrize("nome", ["fundo.mp4", "gameplay.mp4"])
def test_previa_serve_o_video_de_fundo_do_f8_e_do_f5(cfg: Config, nome: str) -> None:
    a = Ambiente(cfg)
    (a.d / "projeto" / "assets" / nome).write_bytes(b"fundo")
    r = a.c.get(f"{EP}/cortes/0/previa/assets/{nome}")
    assert r.content == b"fundo" and r.headers["content-type"] == "video/mp4"
    assert a.c.get(f"{EP}/cortes/0/previa/assets/outro.mp4").status_code == 422
    travessia = f"{EP}/cortes/0/previa/assets%2F..%2Fassets%2F{nome}"   # %2F: o cliente não normaliza
    assert a.c.get(travessia).status_code == 422


def test_refazer_broll_apaga_o_cache_e_os_clipes_e_pede_a_previa(cfg: Config) -> None:
    a = ambiente_f4(cfg)
    assets = a.d / "projeto" / "assets"
    (assets / "ilus-9.jpg").write_bytes(b"cartao do f9")
    d = a.c.post(f"{EP}/cortes/0/broll/refazer").json()
    assert d["previa"]["situacao"] == "preparando" and d["broll"] == []
    assert not (a.d / "ilustracao").exists()
    assert not [*assets.glob("broll-*"), *assets.glob("ilus-*")] and (assets / "trecho.mp4").exists()


def test_refazer_broll_recusado_com_a_previa_preparando(cfg: Config) -> None:
    a = ambiente_f4(cfg)
    a.previas.pedir("abcdefghijk", 0)
    r = a.c.post(f"{EP}/cortes/0/broll/refazer")
    assert r.status_code == 422 and "preparada" in r.json()["detail"]
    assert (a.d / "ilustracao" / "ilustracao.json").exists()


def test_refazer_broll_recusado_com_o_corte_na_fila(cfg: Config) -> None:
    a = ambiente_f4(cfg)
    a.c.post(f"{EP}/cortes/0/renderizar", json={})
    r = a.c.post(f"{EP}/cortes/0/broll/refazer")
    assert r.status_code == 422 and "fila" in r.json()["detail"]
    assert (a.d / "ilustracao" / "ilustracao.json").exists()


def test_refazer_broll_recusado_fora_do_f4(cfg: Config) -> None:
    r = Ambiente(cfg).c.post(f"{EP}/cortes/0/broll/refazer")
    assert r.status_code == 422 and "f4" in r.json()["detail"]


def test_editor_mostra_a_trilha(cfg: Config) -> None:
    a = Ambiente(cfg)
    t = a.c.get(f"{EP}/cortes/0/editor").json()["trilha"]
    assert t["escolha"] == "auto" and t["automatica"] is None
    assert [c["id"] for c in t["camas"]] == ["A", "B", "C"]
    mood = {"mood": "tensao", "motivo": "perda", "chave": {"texto": "outro trecho"}}
    (a.d / "trilha.json").write_text(json.dumps(mood), encoding="utf-8")
    t = a.c.get(f"{EP}/cortes/0/editor").json()["trilha"]
    assert t["automatica"] is None, "mood de outro texto não vale para o trecho atual"
    mood["chave"] = {"texto": "Mas eu ganhei porra, dez mil reais."}
    (a.d / "trilha.json").write_text(json.dumps(mood), encoding="utf-8")
    t = a.c.get(f"{EP}/cortes/0/editor").json()["trilha"]
    assert (t["automatica"], t["motivo"]) == ("B", "perda")


def test_editar_trilha(cfg: Config) -> None:
    a = Ambiente(cfg)
    d = a.c.post(f"{EP}/cortes/0/editar", json={"trilha": "C"}).json()
    assert d["trilha"]["escolha"] == "C" and ler_corte(a.d).edicoes.trilha == "C"
    a.previas.processar("abcdefghijk", 0)   # editar pede a prévia; enquanto ela prepara, edição é recusada
    r = a.c.post(f"{EP}/cortes/0/editar", json={"trilha": "Z"})
    assert r.status_code == 422 and "trilha 'Z'" in r.json()["detail"]
    d = a.c.post(f"{EP}/cortes/0/editar", json={"trilha": "auto"}).json()
    assert d["trilha"]["escolha"] == "auto" and ler_corte(a.d).edicoes.trilha is None


def test_previa_serve_a_trilha(cfg: Config) -> None:
    a = Ambiente(cfg)
    (a.d / "projeto" / "assets" / "trilha.m4a").write_bytes(b"m4a")
    r = a.c.get(f"{EP}/cortes/0/previa/assets/trilha.m4a")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mp4"
