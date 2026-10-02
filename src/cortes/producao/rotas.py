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

from cortes.episodio import id_do_video, salvar_texto
from cortes.painel.dados import VIDEO_ID
from cortes.perfil import CRITERIOS
from cortes.producao import curadoria, legenda_yt, transcricao_colada
from cortes.producao.estado import ErroProducao, EstadoEpisodio, etapa_com_erro, gravar, ler, novo, reabrir
from cortes.producao.etapas import ARQUIVO_FONTE
from cortes.producao.fila import Fila

FORMATOS_RENDER = ("f7", "f1")   # planos D e E acrescentam f4 e f3
N_SHORTS_MAX = 10
TRANSCRICAO_MAX_BYTES = 5 * 1024 * 1024


class NovoEpisodio(BaseModel):
    link: str
    nicho: str
    n_shorts: int
    formato: str
    transcricao: str | None = None   # colada de "Mostrar transcrição" do YouTube (spec §4.2)


class PedidoTranscricao(BaseModel):
    transcricao: str


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


def _meta(pasta: Path) -> dict[str, Any]:
    """meta.json ainda não gerado é estado normal (vídeo baixando); existente e ruim é erro."""
    arquivo = pasta / "meta.json"
    if not arquivo.exists():
        return {}
    meta = curadoria.ler_arquivo(arquivo)
    if not isinstance(meta, dict):
        raise ErroProducao(f"{arquivo}: deveria ser um objeto")
    return meta


def _candidatos(pasta: Path) -> list[dict[str, Any]]:
    """Antes da etapa momentos não há candidatos: lista vazia. Arquivo ruim é erro."""
    return curadoria.candidatos(pasta) if (pasta / "candidatos.json").exists() else []


def _resumo(pasta: Path) -> dict[str, Any]:
    meta = _meta(pasta)
    return {**asdict(ler(pasta)), "titulo": meta.get("titulo"), "canal": meta.get("canal"),
            "duracao_s": meta.get("duracao_s"), "n_candidatos": len(_candidatos(pasta)),
            "fonte_legenda": _fonte_legenda(pasta)}


def _fonte_legenda(pasta: Path) -> Literal["colada", "youtube"] | None:
    """Com `palavras.json`, vale o marcador de quem o gerou (etapas.ARQUIVO_FONTE): um
    `legenda.pt.json3` pode sobrar de um parse que falhou antes da transcrição colada.
    Sem marcador (episódio de antes dele), a transcrição colada, se existir, foi a fonte."""
    marcador = pasta / ARQUIVO_FONTE
    if (pasta / "palavras.json").exists() and marcador.exists():
        fonte = marcador.read_text(encoding="utf-8").strip()
        if fonte not in ("colada", "youtube"):
            raise ErroProducao(f"{marcador}: fonte de legenda desconhecida {fonte!r}")
        return "colada" if fonte == "colada" else "youtube"
    if (pasta / transcricao_colada.ARQUIVO).exists():
        return "colada"
    if (pasta / legenda_yt.ARQUIVO).exists() or (pasta / "palavras.json").exists():
        return "youtube"
    return None


def _episodios(raiz: Path) -> list[dict[str, Any]]:
    """Um episódio com arquivo ruim não some com a lista: vira `{"id", "erro"}`. Os quebrados
    vêm primeiro (por id), depois os bons do mais novo para o mais antigo."""
    bons: list[dict[str, Any]] = []
    quebrados: list[dict[str, Any]] = []
    for pasta in sorted(a.parent for a in raiz.glob("episodios/*/estado.json")):
        try:
            bons.append(_resumo(pasta))
        except ErroProducao as ex:
            quebrados.append({"id": pasta.name, "erro": str(ex)})
    return quebrados + sorted(bons, key=lambda r: r["criado_em"], reverse=True)


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
    if pedido.transcricao is not None:
        _validar_transcricao(pedido.transcricao)
    return id


def _validar_transcricao(texto: str) -> None:
    """Parse completo antes de criar o episódio: transcrição ruim não vira episódio quebrado."""
    tamanho = len(texto.encode("utf-8"))
    if tamanho > TRANSCRICAO_MAX_BYTES:
        raise ErroProducao(f"transcrição colada grande demais: {tamanho / 1024 / 1024:.1f} MB "
                           f"(máximo {TRANSCRICAO_MAX_BYTES // 1024 // 1024} MB)")
    try:
        transcricao_colada.palavras_da_transcricao(texto)
    except transcricao_colada.ErroTranscricao as ex:
        raise ErroProducao(f"transcrição colada: {ex}") from ex


def montar(app: FastAPI, raiz: Path, fila: Fila, escrita: threading.Lock,
           agora: Callable[[], datetime] = datetime.now) -> None:
    """`escrita` é a trava do servidor: serializa criar episódio e gravar curadoria (que
    escreve nos exemplos do nicho e não trava nada sozinha)."""
    _rotas_leitura(app, raiz, fila)
    _rotas_acao(app, raiz, fila, escrita, agora)
    _rota_transcricao(app, raiz, fila, escrita)


def _rotas_leitura(app: FastAPI, raiz: Path, fila: Fila) -> None:
    @app.get("/api/producao")
    def api_producao() -> Any:
        return jsonable_encoder({"fila": fila.situacao(), "episodios": _episodios(raiz),
                                 "formatos": FORMATOS_RENDER})

    @app.get("/api/episodios/{id}")
    def api_episodio(id: str) -> Any:
        pasta = _pasta(raiz, id)
        feitas = curadoria.decisoes(pasta)
        cands = [{**c, "indice": i, "decisao": feitas.get(i, {}).get("decisao")}
                 for i, c in enumerate(_candidatos(pasta))]
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
            if pedido.transcricao is not None:   # antes do estado.json: a fila nunca vê o episódio sem ela
                salvar_texto(pasta / transcricao_colada.ARQUIVO, pedido.transcricao)
            gravar(pasta, novo(id, f"https://www.youtube.com/watch?v={id}", pedido.nicho,
                               pedido.n_shorts, pedido.formato, agora()))
        fila.enfileirar(id)
        return {"id": id}

    @app.post("/api/episodios/{id}/tentar", status_code=202)
    def api_tentar(id: str) -> dict[str, bool]:
        pasta = _pasta(raiz, id)
        with escrita:   # clique duplo: o segundo já não vê erro e recebe 422
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


def _rota_transcricao(app: FastAPI, raiz: Path, fila: Fila, escrita: threading.Lock) -> None:
    @app.post("/api/episodios/{id}/transcricao", status_code=202)
    def api_transcricao(id: str, pedido: PedidoTranscricao) -> dict[str, bool]:
        """Saída para episódio já na produção com a legenda bloqueada (429): grava a transcrição
        colada e, se há etapa em erro, reabre e enfileira como o 'tentar de novo'."""
        pasta = _pasta(raiz, id)
        with escrita:
            e = ler(pasta)
            _conferir_pode_colar(pasta, e, fila)
            _validar_transcricao(pedido.transcricao)
            salvar_texto(pasta / transcricao_colada.ARQUIVO, pedido.transcricao)
            reabrir_agora = etapa_com_erro(e) is not None
            if reabrir_agora:
                gravar(pasta, reabrir(e))
                fila.enfileirar(id)
        return {"enfileirado": reabrir_agora}


def _conferir_pode_colar(pasta: Path, e: EstadoEpisodio, fila: Fila) -> None:
    """Tudo antes de gravar: um pedido recusado não deixa transcricao.txt para trás. A fila
    rodando o episódio poderia estar no meio da etapa legenda (download em curso)."""
    if (pasta / "palavras.json").exists():
        raise ErroProducao("a legenda deste episódio já está pronta")
    atual = fila.situacao()["atual"]
    if atual is not None and atual.get("episodio") == e.id:
        raise ErroProducao(f"episódio {e.id} está sendo processado agora; espere a etapa terminar")
    situacao = e.etapas["legenda"].situacao
    if situacao not in ("erro", "pendente"):
        raise ErroProducao(f"a etapa legenda está '{situacao}'; só dá para colar com ela em erro ou pendente")
