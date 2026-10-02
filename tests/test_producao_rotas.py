import json
import time
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cortes.llm import ErroLLM
from cortes.painel.servidor import Config, criar_app
from cortes.producao.estado import EstadoEpisodio, concluido, gravar, ler, marcar, novo
from cortes.producao.fila import Fila, RodarEtapa

AGORA = datetime(2026, 10, 2, 9)
CAND = {"frase_inicio": 0, "frase_fim": 1, "inicio": 10.0, "fim": 40.0,
        "notas": {"gancho_3s": 5, "autocontido": 4, "espanto": 4, "historia_ou_virada": 3, "fechamento": 4},
        "bonus": ["humor"], "penalidades": [], "justificativa": "abre com número", "titulo": "Ganhei dez mil",
        "nota_final": 87.5}
FRASES = [{"indice": 0, "texto": "Eu ganhei dez mil.", "inicio": 10.0, "fim": 20.0},
          {"indice": 1, "texto": "E perdi tudo.", "inicio": 20.0, "fim": 40.0}]
NOVO = {"link": "https://youtu.be/abcdefghijk", "nicho": "financas", "n_shorts": 5, "formato": "f7"}


def nada(nome: str, pasta: Path, e: EstadoEpisodio) -> None:
    return None


def montar(cfg: Config, rodar: RodarEtapa = nada) -> tuple[TestClient, Fila]:
    fila = Fila(cfg.raiz, rodar, lambda: AGORA)
    app = criar_app(cfg, executar=lambda a, c: "", abrir=lambda a, c: None, fila=fila)
    return TestClient(app, base_url="http://127.0.0.1"), fila


def test_novo_episodio_entra_na_fila(cfg: Config) -> None:
    c, fila = montar(cfg)
    r = c.post("/api/episodios", json={**NOVO, "link": "https://www.youtube.com/watch?v=abcdefghijk"})
    assert r.status_code == 201 and r.json() == {"id": "abcdefghijk"}
    assert fila.situacao()["na_fila"] == ["abcdefghijk"]
    e = ler(cfg.raiz / "episodios" / "abcdefghijk")
    assert e.nicho == "financas" and e.url == "https://www.youtube.com/watch?v=abcdefghijk"


@pytest.mark.parametrize("corpo, erro", [
    ({**NOVO, "link": "https://www.youtube.com/@canal"}, "sem id"),
    ({**NOVO, "nicho": "humor"}, "nicho 'humor'"),
    ({**NOVO, "nicho": "../contas"}, "nicho '../contas'"),
    ({**NOVO, "formato": "f4"}, "formato 'f4'"),
    ({**NOVO, "n_shorts": 0}, "n_shorts"),
])
def test_novo_episodio_recusado(cfg: Config, corpo: dict[str, object], erro: str) -> None:
    c, fila = montar(cfg)
    r = c.post("/api/episodios", json=corpo)
    assert r.status_code == 422 and erro in json.dumps(r.json(), ensure_ascii=False)
    assert fila.situacao()["na_fila"] == []
    assert not (cfg.raiz / "episodios").exists()


def test_episodio_repetido_recusado(cfg: Config) -> None:
    c, _ = montar(cfg)
    c.post("/api/episodios", json=NOVO)
    r = c.post("/api/episodios", json=NOVO)
    assert r.status_code == 422 and "já está na produção" in r.json()["detail"]


def preparar_concluido(cfg: Config) -> Path:
    pasta = cfg.raiz / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    e = novo("abcdefghijk", "https://youtu.be/abcdefghijk", "financas", 5, "f7", AGORA)
    for n in e.etapas:
        e = marcar(e, n, "ok", AGORA)
    gravar(pasta, e)
    (pasta / "meta.json").write_text(json.dumps({"titulo": "Ep", "canal": "PrimoCast", "duracao_s": 600,
                                                  "data": "20260929", "id": "abcdefghijk"}), encoding="utf-8")
    (pasta / "candidatos.json").write_text(json.dumps([CAND]), encoding="utf-8")
    (pasta / "frases.json").write_text(json.dumps(FRASES), encoding="utf-8")
    (pasta / "video.mp4").write_bytes(b"0123456789" * 100)
    return pasta


def test_lista_e_detalhe(cfg: Config) -> None:
    preparar_concluido(cfg)
    c, _ = montar(cfg)
    p = c.get("/api/producao").json()
    assert p["episodios"][0]["id"] == "abcdefghijk" and p["episodios"][0]["titulo"] == "Ep"
    assert p["episodios"][0]["n_candidatos"] == 1 and p["fila"]["pausada"] is None
    assert p["episodios"][0]["etapas"]["momentos"]["situacao"] == "ok"
    d = c.get("/api/episodios/abcdefghijk").json()
    assert d["candidatos"][0]["titulo"] == "Ganhei dez mil" and d["candidatos"][0]["decisao"] is None
    assert d["candidatos"][0]["indice"] == 0
    assert d["rubrica"] == ["gancho_3s", "autocontido", "espanto", "historia_ou_virada", "fechamento"]


def test_video_atende_range(cfg: Config) -> None:
    preparar_concluido(cfg)
    c, _ = montar(cfg)
    r = c.get("/api/episodios/abcdefghijk/video", headers={"Range": "bytes=0-9"})
    assert r.status_code == 206 and r.content == b"0123456789"


def test_id_invalido_nao_vira_caminho(cfg: Config) -> None:
    c, _ = montar(cfg)
    assert c.get("/api/episodios/..%2F..%2Fcontas").status_code in (404, 422)
    r = c.get("/api/episodios/abc.defghij")
    assert r.status_code == 422 and "inválido" in r.json()["detail"]
    r = c.get("/api/episodios/naoexiste00")
    assert r.status_code == 422 and "não está na produção" in r.json()["detail"]


def test_decisao(cfg: Config) -> None:
    preparar_concluido(cfg)
    c, _ = montar(cfg)
    r = c.post("/api/episodios/abcdefghijk/candidatos/0/decisao",
               json={"decisao": "rejeitado", "motivo": "sem gancho"})
    assert r.status_code == 200
    assert c.get("/api/episodios/abcdefghijk").json()["candidatos"][0]["decisao"] == "rejeitado"
    ruins = cfg.raiz / "nichos" / "financas" / "exemplos" / "ruins.jsonl"
    ruim = json.loads(ruins.read_text(encoding="utf-8"))
    assert ruim["texto"] == "Eu ganhei dez mil. E perdi tudo." and ruim["motivo"] == "sem gancho"


def test_decisao_recusada(cfg: Config) -> None:
    preparar_concluido(cfg)
    c, _ = montar(cfg)
    url = "/api/episodios/abcdefghijk/candidatos/{}/decisao"
    assert c.post(url.format(0), json={"decisao": "rejeitado"}).status_code == 422
    r = c.post(url.format(5), json={"decisao": "aprovado"})
    assert r.status_code == 422 and "não existe" in r.json()["detail"]
    assert c.post(url.format(0), json={"decisao": "talvez"}).status_code == 422


def test_tentar_de_novo_so_com_erro(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    c, fila = montar(cfg)
    assert c.post("/api/episodios/abcdefghijk/tentar").status_code == 422
    gravar(pasta, marcar(ler(pasta), "momentos", "erro", AGORA, "falhou"))
    assert c.post("/api/episodios/abcdefghijk/tentar").status_code == 202
    assert fila.situacao()["na_fila"] == ["abcdefghijk"]
    assert ler(pasta).etapas["momentos"].situacao == "pendente"


def test_retomar_fila(cfg: Config) -> None:
    c, fila = montar(cfg)
    assert c.post("/api/fila/retomar").status_code == 202
    assert fila.situacao()["pausada"] is None


def limite(nome: str, pasta: Path, e: EstadoEpisodio) -> None:
    raise ErroLLM("limite de uso")


def test_retomar_que_nao_reabre_mostra_o_erro_e_segue_pausada(cfg: Config) -> None:
    c, fila = montar(cfg, limite)
    c.post("/api/episodios", json=NOVO)
    fila.processar("abcdefghijk")   # síncrono: a etapa levanta ErroLLM e a fila pausa
    assert fila.situacao()["pausada"] is not None
    (cfg.raiz / "episodios" / "abcdefghijk" / "estado.json").write_text("{", encoding="utf-8")
    r = c.post("/api/fila/retomar")
    assert r.status_code == 422 and "estado inválido" in r.json()["detail"]
    assert fila.situacao()["pausada"] is not None


def test_fila_sobe_com_o_servidor(cfg: Config) -> None:
    pasta = cfg.raiz / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    e = novo("abcdefghijk", "https://youtu.be/abcdefghijk", "financas", 5, "f7", AGORA)
    gravar(pasta, marcar(e, "video", "rodando", AGORA))   # o processo caiu no meio do download
    rodadas: list[str] = []
    c, fila = montar(cfg, lambda nome, p, e: rodadas.append(nome))
    with c:   # o lifespan chama fila.iniciar(): recupera o que ficou rodando e processa
        prazo = time.monotonic() + 5
        while (len(rodadas) < 4 or fila.situacao()["atual"] is not None) and time.monotonic() < prazo:
            time.sleep(0.02)
    assert rodadas == ["video", "legenda", "sinais", "momentos"]
    assert concluido(ler(pasta))
