"""API do editor (plano C; spec produção §5 "Editor"): estado do editor, edições, a prévia no
navegador (o projeto HyperFrames do corte com o runtime injetado), miniaturas dos rostos por plano,
o B-roll do f4 (leitura e "refazer") e as versões renderizadas. `pasta_de` vem de rotas.py (valida o
id do episódio)."""
import re
import shutil
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
from cortes.render.assets import FUNDO, GAMEPLAY, apagar_clipes
from cortes.render.corte import ARQUIVO, Corte, gravar_corte, ler_corte, pasta_corte
from cortes.render.edicao import Edicao, aplicar, indices_do_corte, mascarar
from cortes.render.ilustracao_cache import ARQUIVO as ARQUIVO_ILUSTRACAO
from cortes.render.ilustracao_cache import PASTA as PASTA_ILUSTRACAO
from cortes.render.ilustracao_cache import ler_ilustracoes, miniatura
from cortes.render.miniatura import gerar_miniatura
from cortes.render.montagem import FORMATOS
from cortes.render.previa import com_runtime
from cortes.render.processo import ErroRender, Rodar
from cortes.render.rosto import Plano, Rosto, ler_rosto, planos
from cortes.tipos import Palavra

JANELA_S = 30.0                 # transcrição mostrada em volta do corte, para mover início/fim
PALAVRAS_AVISO = 8              # quantas palavras do início a regra de início lê
SEM_CACHE = {"Cache-Control": "no-store"}
_VERSAO = re.compile(r"short-v(\d+)\.mp4$")
# clipes do f4 (render/ilustracao_cache.py, nome_asset): o tipo vem da extensão, em lista fechada
_BROLL_PREVIA = re.compile(r"assets/broll-\d+\.(mp4|jpg)")
_TIPO_BROLL = {"mp4": "video/mp4", "jpg": "image/jpeg"}
# lista fechada: trecho de todos, fundo desfocado do f8 e gameplay do f5 (render/assets.py)
_VIDEOS_PREVIA = frozenset(f"assets/{v}" for v in ("trecho.mp4", FUNDO, GAMEPLAY))


def _url(id: str, n: int) -> str:
    return f"/api/episodios/{id}/cortes/{n}"


def corte_de(pasta: Path, n: int) -> Corte:
    d = pasta_corte(pasta, n)
    if not (d / ARQUIVO).exists():
        raise ErroProducao(f"corte {n} não existe; renderize o candidato antes de editar")
    return ler_corte(d)


def palavras_do_episodio(pasta: Path) -> list[Palavra]:
    arq = pasta / "palavras.json"
    if not arq.exists():
        raise ErroProducao(f"{arq}: não existe (a transcrição deste episódio ainda não rodou)")
    return [Palavra(**p) for p in ler_json(arq)]


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


def _plano_json(id: str, c: Corte, v: int, p: Plano) -> dict[str, Any]:
    escolhida = c.edicoes.rostos.get(p.k)
    invalida = escolhida is not None and not 0 <= escolhida < len(p.pessoas)
    escolha = p.padrao if escolhida is None or invalida else escolhida
    return {"k": p.k, "ini": p.ini, "fim": p.fim, "padrao": p.padrao, "escolha": escolha,
            "escolha_invalida": invalida,
            "pessoas": [{"j": j, "x": s.x, "y": s.y, "n": s.n,
                         "miniatura": f"{_url(id, c.indice)}/planos/{p.k}/pessoas/{j}?v={v}"}
                        for j, s in enumerate(p.pessoas)]}


def _planos_json(id: str, d: Path, c: Corte) -> tuple[list[dict[str, Any]], str | None]:
    """ErroRender (ex.: rosto.json de formato velho, plano B) não pode derrubar o editor — fica
    visível em `rosto_erro`; a prévia refaz a medição e resolve."""
    try:
        rp = rosto_do_corte(d)
    except ErroRender as ex:
        return [], str(ex)
    if rp is None:
        return [], None
    marca = d / "recorte.json"
    v = int(marca.stat().st_mtime) if marca.exists() else 0
    return [_plano_json(id, c, v, p) for p in rp[1]], None


def _broll_json(id: str, d: Path, c: Corte) -> tuple[list[dict[str, Any]], str | None]:
    """Só o f4. Cache do B-roll ilegível não derruba o editor: fica em `broll_erro`."""
    if c.formato != "f4":
        return [], None
    try:
        lido = ler_ilustracoes(d)
    except ErroRender as ex:
        return [], str(ex)
    if lido is None:
        return [], None
    v = int((d / PASTA_ILUSTRACAO / ARQUIVO_ILUSTRACAO).stat().st_mtime)
    return [{"k": i.k, "inicio": i.deixa.inicio, "fim": i.deixa.fim, "coisa": i.deixa.coisa,
             "busca": i.deixa.busca, "tipo": i.deixa.tipo, "midia": i.midia,
             "fonte_url": i.fonte.url if i.fonte else None, "canal": i.fonte.canal if i.fonte else None,
             "motivo": i.motivo,
             "miniatura": f"{_url(id, c.indice)}/broll/{i.k}?v={v}" if i.arquivo else None}
            for i in lido.ilustracoes], None


def situacao_previa(previas: Previas, d: Path, id: str, c: Corte) -> dict[str, Any]:
    """Memória da thread primeiro; sem ela (painel reiniciado), o disco. Sem edição salva desde o
    último render (`alterado is False`) a prévia está sempre pronta — o render grava o index.html e
    só DEPOIS o corte.json (`concluir`), então o mtime do index.html fica mais velho mesmo sem nada
    desatualizado; comparar os dois só faz sentido quando existe edição pendente (`alterado`)."""
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
    desatualizada = c.alterado and idx.stat().st_mtime < (d / ARQUIVO).stat().st_mtime
    return {"situacao": "desatualizada" if desatualizada else "pronta", "erro": None, "url": url}


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
    planos_json, rosto_erro = _planos_json(id, d, c)
    broll, broll_erro = _broll_json(id, d, c)
    return {"corte": asdict(c), "episodio": {"id": id, "titulo": meta.get("titulo")},
            "palavras": _palavras_json(todas, c), "inicio_palavra": i0, "fim_palavra": i1,
            "aviso_inicio": comeca_no_meio(abertura), "planos": planos_json, "rosto_erro": rosto_erro,
            "broll": broll, "broll_erro": broll_erro,
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
    pessoas_por_plano: list[int] = []
    if pedido.rosto is not None:   # só lê o rosto.json quando a edição precisa dele (item 1)
        rp = rosto_do_corte(pasta_corte(pasta, n))
        pessoas_por_plano = [len(p.pessoas) for p in rp[1]] if rp else []
    novo = aplicar(c, pedido.edicao(), palavras_do_episodio(pasta), pessoas_por_plano)
    if novo != c:
        gravar_corte(pasta_corte(pasta, n), novo)
        previas.pedir(pasta.name, n)


def refazer_broll(pasta: Path, n: int, previas: Previas) -> None:
    """Apaga o cache do f4 (`ilustracao/`, deixas incluídas) e os clipes, e pede a prévia: o LLM,
    as buscas e a conferência rodam de novo. Recusado enquanto a prévia ou o render usam a pasta."""
    c = corte_de(pasta, n)
    if c.formato != "f4":
        raise ErroProducao(f"corte {n} não é B-roll (f4): não há B-roll para refazer")
    _exigir_editavel(previas, pasta.name, c)
    d = pasta_corte(pasta, n)
    if (d / PASTA_ILUSTRACAO).exists():
        shutil.rmtree(d / PASTA_ILUSTRACAO)
    if (d / "projeto" / "assets").exists():
        apagar_clipes(d / "projeto" / "assets")
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
        if arquivo in _VIDEOS_PREVIA and (proj / arquivo).exists():
            return FileResponse(proj / arquivo, media_type="video/mp4", headers=SEM_CACHE)
        if (m := _BROLL_PREVIA.fullmatch(arquivo)) and (proj / arquivo).exists():
            return FileResponse(proj / arquivo, media_type=_TIPO_BROLL[m.group(1)], headers=SEM_CACHE)
        raise ErroProducao(f"arquivo da prévia indisponível: {arquivo!r}")

    @app.get("/api/episodios/{id}/cortes/{n}/planos/{k}/pessoas/{j}")
    def api_miniatura(id: str, n: int, k: int, j: int) -> FileResponse:
        pasta = pasta_de(id)
        c = corte_de(pasta, n)
        if not editavel(previas, id, c):   # o rosto pode estar sendo medido de novo (item 2)
            raise ErroProducao(f"corte {n} está sendo preparado; espere terminar para ver as miniaturas")
        d = pasta_corte(pasta, n)
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

    @app.get("/api/episodios/{id}/cortes/{n}/broll/{k}")
    def api_broll(id: str, n: int, k: int) -> FileResponse:
        return FileResponse(miniatura_broll(pasta_de(id), n, k, previas), media_type="image/jpeg")


def miniatura_broll(pasta: Path, n: int, k: int, previas: Previas) -> Path:
    """A miniatura do clipe da deixa k do f4: um quadro do vídeo ou a foto. Recusada enquanto a
    prévia ou o render podem estar refazendo a pasta `ilustracao/` (como a miniatura de rosto)."""
    c = corte_de(pasta, n)
    if not editavel(previas, pasta.name, c):
        raise ErroProducao(f"corte {n} está sendo preparado; espere terminar para ver o B-roll")
    lido = ler_ilustracoes(pasta_corte(pasta, n))
    mini = next((miniatura(i) for i in lido.ilustracoes if i.k == k), None) if lido else None
    if mini is None or not mini.exists():
        raise ErroProducao(f"B-roll {k} do corte {n} não existe ou ficou sem visual")
    return mini


def _rotas_edicao(app: FastAPI, pasta_de: Callable[[str], Path], previas: Previas,
                  escrita: threading.Lock) -> None:
    @app.post("/api/episodios/{id}/cortes/{n}/editar")
    def api_editar(id: str, n: int, pedido: PedidoEdicao) -> Any:
        pasta = pasta_de(id)
        with escrita:
            editar(pasta, n, pedido, previas)
        return estado_editor(pasta, n, previas)

    @app.post("/api/episodios/{id}/cortes/{n}/broll/refazer")
    def api_refazer_broll(id: str, n: int) -> Any:
        pasta = pasta_de(id)
        with escrita:
            refazer_broll(pasta, n, previas)
        return estado_editor(pasta, n, previas)

    @app.post("/api/episodios/{id}/cortes/{n}/previa")
    def api_pedir_previa(id: str, n: int) -> Any:
        pasta = pasta_de(id)
        with escrita:
            c = corte_de(pasta, n)
            _exigir_editavel(previas, id, c)
            previas.pedir(id, n)
        return estado_editor(pasta, n, previas)
