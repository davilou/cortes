"""API dos Shorts de um episódio (plano B; spec produção §5): Renderizar, Cancelar, o MP4 do corte, o
SEO (render/seo.py), abrir a pasta do MP4 no Explorer e o resumo do render para a barra de etapas.
`pasta_de` vem de rotas.py (valida o id do episódio)."""
import shutil
import subprocess
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
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
from cortes.render.montagem import validar_formato
from cortes.render.seo import ARQUIVO as ARQUIVO_SEO
from cortes.render.seo import Seo, ler_seo

GerarSeo = Callable[[Path, Corte], Seo]   # (pasta do episódio, corte) → SEO gravado
AbrirPasta = Callable[[Path], None]       # arquivo a mostrar selecionado no Explorer


def abrir_pasta_real(arq: Path) -> None:
    """O Explorer devolve código 1 mesmo quando abre: não há o que conferir no retorno."""
    subprocess.Popen(["explorer", f"/select,{arq.resolve()}"])


@dataclass(frozen=True)
class AcoesCorte:
    gerar_seo: GerarSeo
    abrir_pasta: AbrirPasta = abrir_pasta_real


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

    def _seo(c: Corte) -> dict[str, Any] | None:
        s = ler_seo(pasta_corte(pasta, c.indice))
        return asdict(s) if s else None

    return [{**asdict(c), "video": _video(c), "seo": _seo(c)} for c in cortes_do_episodio(pasta)]


def corte_pronto(pasta: Path, indice: int) -> tuple[Corte, Path]:
    """O corte e o MP4 da versão atual; recusa corte sem vídeo."""
    d = pasta_corte(pasta, indice)
    if not (d / ARQUIVO).exists():
        raise ErroProducao(f"corte {indice} não existe")
    c = ler_corte(d)
    arq = video(pasta, c)
    if arq is None or not arq.exists():
        raise ErroProducao(f"corte {indice} ainda sem vídeo")
    return c, arq


def refazer_seo(pasta: Path, indice: int, gerar: GerarSeo) -> Seo:
    """Para Short renderizado antes do SEO existir, ou quando o SEO não agradou: apaga o cache e gera
    de novo. Recusado com o corte na fila ou renderizando — o render grava o mesmo seo.json."""
    c, _ = corte_pronto(pasta, indice)
    if c.status in ("na_fila", "renderizando"):
        raise ErroProducao(f"corte {indice} está na fila do render; o SEO sai junto com ele")
    (pasta_corte(pasta, indice) / ARQUIVO_SEO).unlink(missing_ok=True)
    return gerar(pasta, c)


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
    if formato is not None:
        validar_formato(formato)
    d = pasta_corte(pasta, indice)
    if (d / ARQUIVO).exists():
        atual = ler_corte(d)
        gravar_corte(d, reenfileirar(atual, formato or atual.formato))
    else:
        gravar_corte(d, novo_corte(indice, cands[indice], formato or e.formato))


def cancelar_render(pasta: Path, indice: int) -> None:
    """Chamar sob a trava `escrita`: a fila pega o próximo corte sob a mesma trava, então daqui ou
    se vê o corte na fila (e ela não o pega mais) ou já `renderizando` (e o cancelar é recusado)."""
    d = pasta_corte(pasta, indice)
    if not (d / ARQUIVO).exists():
        raise ErroProducao(f"corte {indice} não existe")
    c = cancelar(ler_corte(d))
    if c is None:
        _apagar_corte(d)
    else:
        gravar_corte(d, c)


def _apagar_corte(d: Path) -> None:
    """Nunca renderizou nem foi editado: o candidato volta a ter "Renderizar". O corte.json sai
    primeiro — se o resto da pasta não sair (arquivo em uso), não sobra um corte "na fila" fantasma."""
    try:
        (d / ARQUIVO).unlink()
        shutil.rmtree(d)
    except OSError as ex:
        raise ErroProducao(f"não deu para apagar {d}: {ex}") from ex


def montar(app: FastAPI, pasta_de: Callable[[str], Path], fila: Fila, escrita: threading.Lock,
          previas: Previas, acoes: AcoesCorte) -> None:
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

    @app.post("/api/episodios/{id}/cortes/{indice}/seo")
    def api_seo(id: str, indice: int) -> dict[str, Any]:
        return asdict(refazer_seo(pasta_de(id), indice, acoes.gerar_seo))

    @app.post("/api/episodios/{id}/cortes/{indice}/abrir-pasta")
    def api_abrir_pasta(id: str, indice: int) -> dict[str, bool]:
        _, arq = corte_pronto(pasta_de(id), indice)
        acoes.abrir_pasta(arq)
        return {"aberto": True}

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
