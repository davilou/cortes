"""API do editor (plano C; spec produção §5 "Editor"): estado do editor, edições, a prévia no
navegador (o projeto HyperFrames do corte com o runtime injetado), miniaturas dos rostos por plano
e as versões renderizadas. `pasta_de` vem de rotas.py (valida o id do episódio)."""
import re
import threading
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from cortes.episodio import ler_json
from cortes.producao.estado import ErroProducao
from cortes.producao.previas import Previas
from cortes.regra_inicio import comeca_no_meio
from cortes.render.corte import ARQUIVO, Corte, gravar_corte, ler_corte, pasta_corte
from cortes.render.edicao import Edicao, aplicar, indices_do_corte, mascarar
from cortes.render.miniatura import gerar_miniatura
from cortes.render.montagem import FORMATOS
from cortes.render.previa import com_runtime
from cortes.render.processo import Rodar
from cortes.render.rosto import Plano, Rosto, ler_rosto, planos
from cortes.tipos import Palavra

JANELA_S = 30.0                 # transcrição mostrada em volta do corte, para mover início/fim
PALAVRAS_AVISO = 8              # quantas palavras do início a regra de início lê
SEM_CACHE = {"Cache-Control": "no-store"}
_VERSAO = re.compile(r"short-v(\d+)\.mp4$")


def _url(id: str, n: int) -> str:
    return f"/api/episodios/{id}/cortes/{n}"


def corte_de(pasta: Path, n: int) -> Corte:
    d = pasta_corte(pasta, n)
    if not (d / ARQUIVO).exists():
        raise ErroProducao(f"corte {n} não existe; renderize o candidato antes de editar")
    return ler_corte(d)


def palavras_do_episodio(pasta: Path) -> list[Palavra]:
    return [Palavra(**p) for p in ler_json(pasta / "palavras.json")]


def _palavras_json(todas: list[Palavra], c: Corte) -> list[dict[str, Any]]:
    res = []
    for i, p in enumerate(todas):
        if not c.inicio - JANELA_S <= p.inicio <= c.fim + JANELA_S:
            continue
        texto = c.edicoes.legenda.get(i, p.texto)
        masc = i in c.edicoes.mascaradas
        res.append({"i": i, "texto": mascarar(texto) if masc else texto, "original": p.texto,
                    "inicio": p.inicio, "fim": p.fim, "dentro": c.inicio - 0.01 <= p.inicio <= c.fim + 0.01,
                    "mascarada": masc, "editada": i in c.edicoes.legenda})
    return res


def rosto_do_corte(d: Path) -> tuple[Rosto, list[Plano]] | None:
    if not (d / "rosto.json").exists():
        return None
    r = ler_rosto(d / "rosto.json")
    return r, planos(r)


def _planos_json(id: str, d: Path, c: Corte) -> list[dict[str, Any]]:
    rp = rosto_do_corte(d)
    if rp is None:
        return []
    marca = d / "recorte.json"
    v = int(marca.stat().st_mtime) if marca.exists() else 0
    return [{"k": p.k, "ini": p.ini, "fim": p.fim, "padrao": p.padrao,
             "escolha": c.edicoes.rostos.get(p.k, p.padrao),
             "pessoas": [{"j": j, "x": s.x, "y": s.y, "n": s.n,
                          "miniatura": f"{_url(id, c.indice)}/planos/{p.k}/pessoas/{j}?v={v}"}
                         for j, s in enumerate(p.pessoas)]} for p in rp[1]]


def situacao_previa(previas: Previas, d: Path, id: str, c: Corte) -> dict[str, Any]:
    """Memória da thread primeiro; sem ela (painel reiniciado), o disco: index.html mais novo que o
    corte.json = pronta, mais velho = desatualizada, ausente = ausente."""
    idx = d / "projeto" / "index.html"
    mem = previas.situacao(id, c.indice)
    url = (f"{_url(id, c.indice)}/previa/index.html?v={int(idx.stat().st_mtime * 1000)}"
          if idx.exists() else None)
    if mem is not None and mem.situacao != "pronta":
        return {"situacao": mem.situacao, "erro": mem.erro, "url": None}
    if mem is not None and url is not None:   # a thread acabou de montar: vale mais que o mtime
        return {"situacao": "pronta", "erro": None, "url": url}
    if url is None:
        return {"situacao": "ausente", "erro": None, "url": None}
    novo = idx.stat().st_mtime >= (d / ARQUIVO).stat().st_mtime
    return {"situacao": "pronta" if novo else "desatualizada", "erro": None, "url": url}


def _versoes(id: str, d: Path, n: int) -> list[dict[str, Any]]:
    vs = sorted(int(m.group(1)) for a in d.glob("short-v*.mp4") if (m := _VERSAO.search(a.name)))
    return [{"versao": v, "url": f"{_url(id, n)}/video?versao={v}"} for v in vs]


def editavel(previas: Previas, id: str, c: Corte) -> bool:
    return c.status not in ("na_fila", "renderizando") and not previas.preparando(id, c.indice)


def estado_editor(pasta: Path, n: int, previas: Previas) -> dict[str, Any]:
    id, c = pasta.name, corte_de(pasta, n)
    d = pasta_corte(pasta, n)
    todas = palavras_do_episodio(pasta)
    i0, i1 = indices_do_corte(todas, c.inicio, c.fim)
    meta = ler_json(pasta / "meta.json") if (pasta / "meta.json").exists() else {}
    abertura = " ".join(p.texto for p in todas[i0:i0 + PALAVRAS_AVISO])
    return {"corte": asdict(c), "episodio": {"id": id, "titulo": meta.get("titulo")},
            "palavras": _palavras_json(todas, c), "inicio_palavra": i0, "fim_palavra": i1,
            "aviso_inicio": comeca_no_meio(abertura), "planos": _planos_json(id, d, c),
            "previa": situacao_previa(previas, d, id, c), "versoes": _versoes(id, d, n),
            "formatos": list(FORMATOS), "editavel": editavel(previas, id, c)}


class PedidoEdicao(BaseModel):
    inicio_palavra: int | None = None
    fim_palavra: int | None = None
    titulo: str | None = None
    formato: str | None = None
    legenda: dict[int, str | None] = {}
    mascarar: dict[int, bool] = {}
    mascarar_palavroes: bool = False
    rosto: tuple[int, int] | None = None

    def edicao(self) -> Edicao:
        return Edicao(self.inicio_palavra, self.fim_palavra, self.titulo, self.formato, dict(self.legenda),
                      dict(self.mascarar), self.mascarar_palavroes, self.rosto)


def _exigir_editavel(previas: Previas, id: str, c: Corte) -> None:
    if c.status in ("na_fila", "renderizando"):
        raise ErroProducao(f"corte {c.indice} está na fila do render; espere terminar para editar")
    if previas.preparando(id, c.indice):
        raise ErroProducao(f"a prévia do corte {c.indice} está sendo preparada; espere terminar")


def editar(pasta: Path, n: int, pedido: PedidoEdicao, previas: Previas) -> None:
    c = corte_de(pasta, n)
    _exigir_editavel(previas, pasta.name, c)
    rp = rosto_do_corte(pasta_corte(pasta, n))
    pessoas_por_plano = [len(p.pessoas) for p in rp[1]] if rp else []
    novo = aplicar(c, pedido.edicao(), palavras_do_episodio(pasta), pessoas_por_plano)
    if novo != c:
        gravar_corte(pasta_corte(pasta, n), novo)
        previas.pedir(pasta.name, n)


def montar(app: FastAPI, pasta_de: Callable[[str], Path], previas: Previas, rodar: Rodar,
          escrita: threading.Lock) -> None:
    _rotas_leitura(app, pasta_de, previas, rodar)
    _rotas_edicao(app, pasta_de, previas, escrita)


def _rotas_leitura(app: FastAPI, pasta_de: Callable[[str], Path], previas: Previas, rodar: Rodar) -> None:
    @app.get("/api/episodios/{id}/cortes/{n}/editor")
    def api_editor(id: str, n: int) -> Any:
        return estado_editor(pasta_de(id), n, previas)

    @app.get("/api/episodios/{id}/cortes/{n}/previa/{arquivo:path}")
    def api_previa(id: str, n: int, arquivo: str) -> Response:
        proj = pasta_corte(pasta_de(id), n) / "projeto"
        if arquivo == "index.html" and (proj / "index.html").exists():
            html = com_runtime((proj / "index.html").read_text(encoding="utf-8"))
            return HTMLResponse(html, headers=SEM_CACHE)
        if arquivo == "assets/trecho.mp4" and (proj / arquivo).exists():
            return FileResponse(proj / arquivo, media_type="video/mp4", headers=SEM_CACHE)
        raise ErroProducao(f"arquivo da prévia indisponível: {arquivo!r}")

    @app.get("/api/episodios/{id}/cortes/{n}/planos/{k}/pessoas/{j}")
    def api_miniatura(id: str, n: int, k: int, j: int) -> FileResponse:
        d = pasta_corte(pasta_de(id), n)
        rp = rosto_do_corte(d)
        if rp is None:
            raise ErroProducao(f"corte {n} ainda sem rosto medido")
        r, pls = rp
        if not 0 <= k < len(pls) or not 0 <= j < len(pls[k].pessoas):
            raise ErroProducao(f"plano {k} / pessoa {j} não existe")
        arq = d / "miniaturas" / f"p{k}-{j}.jpg"
        if not arq.exists():
            trecho = d / "projeto" / "assets" / "trecho.mp4"
            gerar_miniatura(trecho, arq, pls[k], j, r.largura, r.altura, rodar)
        return FileResponse(arq, media_type="image/jpeg")


def _rotas_edicao(app: FastAPI, pasta_de: Callable[[str], Path], previas: Previas,
                  escrita: threading.Lock) -> None:
    @app.post("/api/episodios/{id}/cortes/{n}/editar")
    def api_editar(id: str, n: int, pedido: PedidoEdicao) -> Any:
        pasta = pasta_de(id)
        with escrita:
            editar(pasta, n, pedido, previas)
        return estado_editor(pasta, n, previas)

    @app.post("/api/episodios/{id}/cortes/{n}/previa")
    def api_pedir_previa(id: str, n: int) -> Any:
        pasta = pasta_de(id)
        with escrita:
            c = corte_de(pasta, n)
            _exigir_editavel(previas, id, c)
            previas.pedir(id, n)
        return estado_editor(pasta, n, previas)
