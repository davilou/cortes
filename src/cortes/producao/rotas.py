"""API da Produção (spec produção §5). Montada pelo servidor do painel: rotas finas sobre
estado, fila e curadoria. Todo `{id}` passa por `_pasta` (VIDEO_ID) antes de virar caminho."""
import threading
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from pydantic import BaseModel

from cortes.episodio import id_do_video, ler_json
from cortes.painel.dados import VIDEO_ID
from cortes.perfil import CRITERIOS
from cortes.producao import curadoria
from cortes.producao.estado import ErroProducao, etapa_com_erro, gravar, ler, novo, reabrir
from cortes.producao.fila import Fila

FORMATOS_RENDER = ("f7", "f1")   # planos D e E acrescentam f4 e f3
N_SHORTS_MAX = 10


class NovoEpisodio(BaseModel):
    link: str
    nicho: str
    n_shorts: int
    formato: str


class PedidoDecisao(BaseModel):
    decisao: Literal["aprovado", "rejeitado"]
    motivo: str | None = None   # obrigatório ao rejeitar (validado em curadoria.decidir)


def _pasta(raiz: Path, id: str) -> Path:
    if not VIDEO_ID.fullmatch(id):
        raise ErroProducao(f"id de episódio inválido: {id!r}")
    pasta = raiz / "episodios" / id
    if not (pasta / "estado.json").exists():
        raise ErroProducao(f"episódio {id} não está na produção")
    return pasta


def _json_ou(arquivo: Path, vazio: Any) -> Any:
    """Arquivo de etapa ainda não gerado é estado normal (episódio em andamento), não erro."""
    return ler_json(arquivo) if arquivo.exists() else vazio


def _resumo(pasta: Path) -> dict[str, Any]:
    meta = _json_ou(pasta / "meta.json", {})
    return {**asdict(ler(pasta)), "titulo": meta.get("titulo"), "canal": meta.get("canal"),
            "duracao_s": meta.get("duracao_s"), "n_candidatos": len(_json_ou(pasta / "candidatos.json", []))}


def _nichos(raiz: Path) -> list[str]:
    return sorted(p.parent.name for p in (raiz / "nichos").glob("*/perfil.yaml"))


def _validar(raiz: Path, pedido: NovoEpisodio) -> str:
    try:
        id = id_do_video(pedido.link)
    except ValueError as ex:
        raise ErroProducao(str(ex)) from ex
    if pedido.nicho not in _nichos(raiz):
        raise ErroProducao(f"nicho '{pedido.nicho}' não existe em {raiz / 'nichos'}")
    if pedido.formato not in FORMATOS_RENDER:
        raise ErroProducao(f"formato '{pedido.formato}' ainda não renderiza; use um de {FORMATOS_RENDER}")
    if not 1 <= pedido.n_shorts <= N_SHORTS_MAX:
        raise ErroProducao(f"n_shorts deve ficar entre 1 e {N_SHORTS_MAX}")
    if (raiz / "episodios" / id / "estado.json").exists():
        raise ErroProducao(f"episódio {id} já está na produção")
    return id


def montar(app: FastAPI, raiz: Path, fila: Fila, escrita: threading.Lock,
           agora: Callable[[], datetime] = datetime.now) -> None:
    """`escrita` é a trava do servidor: serializa criar episódio e gravar curadoria (que
    escreve nos exemplos do nicho e não trava nada sozinha)."""
    _rotas_leitura(app, raiz, fila)
    _rotas_acao(app, raiz, fila, escrita, agora)


def _rotas_leitura(app: FastAPI, raiz: Path, fila: Fila) -> None:
    @app.get("/api/producao")
    def api_producao() -> Any:
        pastas = [a.parent for a in raiz.glob("episodios/*/estado.json")]
        eps = sorted((_resumo(p) for p in pastas), key=lambda r: r["criado_em"], reverse=True)
        return jsonable_encoder({"fila": fila.situacao(), "episodios": eps, "formatos": FORMATOS_RENDER})

    @app.get("/api/episodios/{id}")
    def api_episodio(id: str) -> Any:
        pasta = _pasta(raiz, id)
        feitas = curadoria.decisoes(pasta)
        cands = [{**c, "indice": i, "decisao": feitas.get(i, {}).get("decisao")}
                 for i, c in enumerate(_json_ou(pasta / "candidatos.json", []))]
        return jsonable_encoder({**_resumo(pasta), "rubrica": list(CRITERIOS), "motivos": curadoria.MOTIVOS,
                                 "candidatos": cands})

    @app.get("/api/episodios/{id}/video")
    def api_video(id: str) -> FileResponse:
        video = _pasta(raiz, id) / "video.mp4"
        if not video.exists():
            raise ErroProducao(f"episódio {id} ainda sem vídeo")
        return FileResponse(video, media_type="video/mp4")


def _rotas_acao(app: FastAPI, raiz: Path, fila: Fila, escrita: threading.Lock,
                agora: Callable[[], datetime]) -> None:
    @app.post("/api/episodios", status_code=201)
    def api_novo(pedido: NovoEpisodio) -> dict[str, str]:
        with escrita:   # dois pedidos do mesmo link não passam juntos pela checagem de repetido
            id = _validar(raiz, pedido)
            pasta = raiz / "episodios" / id
            pasta.mkdir(parents=True, exist_ok=True)
            gravar(pasta, novo(id, f"https://www.youtube.com/watch?v={id}", pedido.nicho,
                               pedido.n_shorts, pedido.formato, agora()))
        fila.enfileirar(id)
        return {"id": id}

    @app.post("/api/episodios/{id}/tentar", status_code=202)
    def api_tentar(id: str) -> dict[str, bool]:
        pasta = _pasta(raiz, id)
        e = ler(pasta)
        if etapa_com_erro(e) is None:
            raise ErroProducao(f"episódio {id} não tem etapa com erro")
        gravar(pasta, reabrir(e))
        fila.enfileirar(id)
        return {"enfileirado": True}

    @app.post("/api/episodios/{id}/candidatos/{indice}/decisao")
    def api_decisao(id: str, indice: int, pedido: PedidoDecisao) -> dict[str, bool]:
        pasta = _pasta(raiz, id)
        with escrita:
            curadoria.decidir(pasta, raiz, ler(pasta).nicho, indice, pedido.decisao, pedido.motivo)
        return {"ok": True}

    @app.post("/api/fila/retomar", status_code=202)
    def api_retomar() -> dict[str, bool]:
        fila.retomar()   # ErroProducao (episódio pausado ilegível) → 422; a fila segue pausada
        return {"retomada": True}
