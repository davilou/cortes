"""API dos Shorts de um episódio (plano B; spec produção §5): Renderizar, o MP4 do corte e o
resumo do render para a barra de etapas. `pasta_de` vem de rotas.py (valida o id do episódio)."""
import threading
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from cortes.producao import curadoria
from cortes.producao.estado import ErroProducao, ler
from cortes.producao.fila import Fila
from cortes.render.corte import (
    ARQUIVO,
    Corte,
    cortes_do_episodio,
    gravar_corte,
    ler_corte,
    novo_corte,
    pasta_corte,
    reenfileirar,
    video,
)
from cortes.render.montagem import FORMATOS


class PedidoRender(BaseModel):
    formato: str | None = None   # None: o formato do corte, ou o do episódio se o corte é novo


def resumo_render(pasta: Path) -> dict[str, Any]:
    cs = cortes_do_episodio(pasta)
    rodando = next((c.indice for c in cs if c.status == "renderizando"), None)
    return {"prontos": sum(c.status == "pronto" for c in cs), "total": len(cs), "rodando": rodando,
            "erros": sum(c.status == "erro" for c in cs)}


def cortes_json(pasta: Path) -> list[dict[str, Any]]:
    def _video(c: Corte) -> str | None:
        return f"/api/episodios/{pasta.name}/cortes/{c.indice}/video" if c.versao else None

    return [{**asdict(c), "video": _video(c)} for c in cortes_do_episodio(pasta)]


def pedir_render(pasta: Path, indice: int, formato: str | None) -> None:
    e = ler(pasta)
    if e.etapas["momentos"].situacao != "ok":
        raise ErroProducao(f"episódio {e.id} ainda não tem os momentos; espere a etapa terminar")
    cands = curadoria.candidatos(pasta)
    if not 0 <= indice < len(cands):
        raise ErroProducao(f"candidato {indice} não existe (o episódio tem {len(cands)})")
    if formato is not None and formato not in FORMATOS:
        raise ErroProducao(f"formato '{formato}' ainda não renderiza; use um de {FORMATOS}")
    d = pasta_corte(pasta, indice)
    if (d / ARQUIVO).exists():
        atual = ler_corte(d)
        gravar_corte(d, reenfileirar(atual, formato or atual.formato))
    else:
        gravar_corte(d, novo_corte(indice, cands[indice], formato or e.formato))


def montar(app: FastAPI, pasta_de: Callable[[str], Path], fila: Fila, escrita: threading.Lock) -> None:
    @app.post("/api/episodios/{id}/cortes/{indice}/renderizar", status_code=202)
    def api_renderizar(id: str, indice: int, pedido: PedidoRender) -> dict[str, bool]:
        pasta = pasta_de(id)
        with escrita:
            pedir_render(pasta, indice, pedido.formato)
        fila.enfileirar(id)
        return {"enfileirado": True}

    @app.get("/api/episodios/{id}/cortes/{indice}/video")
    def api_video_corte(id: str, indice: int, baixar: bool = False) -> FileResponse:
        pasta = pasta_de(id)
        d = pasta_corte(pasta, indice)
        if not (d / ARQUIVO).exists():
            raise ErroProducao(f"corte {indice} não existe")
        c = ler_corte(d)
        arq = video(pasta, c)
        if arq is None or not arq.exists():
            raise ErroProducao(f"corte {indice} ainda sem vídeo")
        nome = f"{id}-{indice}-v{c.versao}.mp4" if baixar else None
        return FileResponse(arq, media_type="video/mp4", filename=nome)
