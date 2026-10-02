"""Rota da aba Formatos: serve o vídeo de demonstração de um formato (spec painel §Formatos).

Só os caminhos configurados em contas/formatos.yaml são servidos — `dados._demo` já recusa,
no carregamento, qualquer 'demo' que não seja relativo e dentro de 'testes/'; aqui confere de
novo (defesa em profundidade) e que o arquivo exista de verdade no disco."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from cortes.painel.dados import ErroPainel, carregar_vocabulario


def montar(app: FastAPI, raiz: Path) -> None:
    @app.get("/api/formatos/{id}/demo")
    def api_formato_demo(id: str) -> FileResponse:
        return FileResponse(_caminho_demo(raiz, id), media_type="video/mp4")


def _caminho_demo(raiz: Path, id: str) -> Path:
    voc = carregar_vocabulario(raiz)
    formato = voc.formatos.get(id)
    if formato is None:
        raise ErroPainel(f"formato '{id}' não existe")
    if not formato.demo:
        raise ErroPainel(f"formato '{id}' não tem demonstração configurada")
    raiz_testes = (raiz / "testes").resolve()
    caminho = (raiz / formato.demo).resolve()
    if raiz_testes != caminho and raiz_testes not in caminho.parents:
        raise ErroPainel(f"formato '{id}': demo '{formato.demo}' fica fora de {raiz_testes}")
    if not caminho.is_file():
        raise ErroPainel(f"formato '{id}': demo '{formato.demo}' não encontrada em disco")
    return caminho
