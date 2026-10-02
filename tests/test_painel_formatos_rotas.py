"""/api/formatos/{id}/demo: só serve caminhos configurados em contas/formatos.yaml, e só se o
arquivo existir — path traversal fica impossível porque dados.py já recusa, no carregamento,
qualquer 'demo' fora de 'testes/' (test_painel_dados.py cobre essas recusas em detalhe; aqui
cobrimos a rota em si)."""
import pytest

from cortes.painel.dados import ErroPainel
from cortes.painel.servidor import Config, criar_app
from tests.test_painel_servidor import cliente


def escrever_formatos(cfg: Config, texto: str) -> None:
    (cfg.raiz / "contas" / "formatos.yaml").write_text(texto, encoding="utf-8")


def test_demo_servida(cfg: Config) -> None:
    pasta = cfg.raiz / "testes" / "f7-conversa-comediante"
    (pasta / "v.mp4").write_bytes(b"fake-mp4-bytes")
    escrever_formatos(cfg, 'formatos:\n  f7: {nome: Conversa, demo: "testes/f7-conversa-comediante/v.mp4"}\n')
    r = cliente(cfg).get("/api/formatos/f7/demo")
    assert r.status_code == 200 and r.content == b"fake-mp4-bytes"
    assert r.headers["content-type"] == "video/mp4"


def test_demo_aceita_range(cfg: Config) -> None:
    """Starlette's FileResponse responde Range sozinho — o vídeo precisa disso pra dar seek."""
    pasta = cfg.raiz / "testes" / "f7-conversa-comediante"
    (pasta / "v.mp4").write_bytes(b"0123456789")
    escrever_formatos(cfg, 'formatos:\n  f7: {nome: Conversa, demo: "testes/f7-conversa-comediante/v.mp4"}\n')
    r = cliente(cfg).get("/api/formatos/f7/demo", headers={"Range": "bytes=2-4"})
    assert r.status_code == 206 and r.content == b"234"


def test_demo_sem_arquivo_no_disco(cfg: Config) -> None:
    escrever_formatos(cfg, 'formatos:\n  f7: {nome: Conversa, demo: "testes/f7-conversa-comediante/v.mp4"}\n')
    r = cliente(cfg).get("/api/formatos/f7/demo")
    assert r.status_code == 422 and "não encontrada" in r.json()["detail"]


def test_demo_nao_configurada(cfg: Config) -> None:
    r = cliente(cfg).get("/api/formatos/f7/demo")   # fixture não põe 'demo' em f7
    assert r.status_code == 422 and "não tem demonstração" in r.json()["detail"]


def test_demo_formato_inexistente(cfg: Config) -> None:
    r = cliente(cfg).get("/api/formatos/f-zzz/demo")
    assert r.status_code == 422 and "não existe" in r.json()["detail"]


def test_demo_fora_de_testes_e_recusada_na_subida(cfg: Config) -> None:
    """O YAML malicioso nunca chega a virar Formato: carregar_vocabulario (chamado por
    criar_app ao subir, e de novo a cada requisição) recusa antes de qualquer rota existir."""
    escrever_formatos(cfg, 'formatos:\n  f7: {nome: Conversa, demo: "../fora/segredo.mp4"}\n')
    with pytest.raises(ErroPainel, match="testes/"):
        criar_app(cfg, executar=lambda a, cwd: "", abrir=lambda a, cwd: None)
