"""API dos Shorts de um episódio (plano B; spec produção §5): Renderizar, Cancelar, o MP4 do corte e o
resumo do render para a barra de etapas. `pasta_de` vem de rotas.py (valida o id do episódio)."""
import shutil
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
from cortes.producao.previas import Previas
from cortes.render.corte import (
    ARQUIVO,
    Corte,
    cancelar,
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


def pedir_render(pasta: Path, indice: int, formato: str | None, preparando: bool) -> None:
    if preparando:
        raise ErroProducao("a prévia deste corte está sendo preparada; espere terminar para renderizar")
    e = ler(pasta)
    if e.etapas["momentos"].situacao != "ok":
        raise ErroProducao(f"episódio {e.id} ainda não tem os momentos; espere a etapa terminar")
    if e.etapas["render"].situacao == "erro":
        raise ErroProducao("a etapa render deste episódio está com erro; use 'tentar de novo' no episódio")
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


def cancelar_render(pasta: Path, indice: int) -> None:
    """Corrida conhecida: a fila pode pegar o corte entre a leitura daqui e a gravação (ela não usa a
    trava `escrita`). Nesse caso o render segue e a gravação dela, no fim, vence: o Short renderiza."""
    d = pasta_corte(pasta, indice)
    if not (d / ARQUIVO).exists():
        raise ErroProducao(f"corte {indice} não existe")
    c = cancelar(ler_corte(d))
    if c is None:
        shutil.rmtree(d)   # nunca renderizou nem foi editado: o candidato volta a ter "Renderizar"
    else:
        gravar_corte(d, c)


def montar(app: FastAPI, pasta_de: Callable[[str], Path], fila: Fila, escrita: threading.Lock,
          previas: Previas) -> None:
    @app.post("/api/episodios/{id}/cortes/{indice}/renderizar", status_code=202)
    def api_renderizar(id: str, indice: int, pedido: PedidoRender) -> dict[str, bool]:
        pasta = pasta_de(id)
        with escrita:
            pedir_render(pasta, indice, pedido.formato, previas.preparando(id, indice))
        fila.enfileirar(id)
        return {"enfileirado": True}

    @app.post("/api/episodios/{id}/cortes/{indice}/cancelar")
    def api_cancelar(id: str, indice: int) -> dict[str, bool]:
        pasta = pasta_de(id)
        with escrita:
            cancelar_render(pasta, indice)
        return {"cancelado": True}

    @app.get("/api/episodios/{id}/cortes/{indice}/video")
    def api_video_corte(
        id: str, indice: int, baixar: bool = False, versao: int | None = None,
    ) -> FileResponse:
        pasta = pasta_de(id)
        d = pasta_corte(pasta, indice)
        if not (d / ARQUIVO).exists():
            raise ErroProducao(f"corte {indice} não existe")
        c = ler_corte(d)
        arq: Path
        if versao is not None:
            arq = d / f"short-v{versao}.mp4"
            if not arq.exists():
                raise ErroProducao(f"versão {versao} do corte {indice} não existe")
        else:
            achado = video(pasta, c)
            if achado is None or not achado.exists():
                raise ErroProducao(f"corte {indice} ainda sem vídeo")
            arq, versao = achado, c.versao
        nome = f"{id}-{indice}-v{versao}.mp4" if baixar else None
        return FileResponse(arq, media_type="video/mp4", filename=nome)
