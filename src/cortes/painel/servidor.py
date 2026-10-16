"""Servidor local do painel: rotas JSON finas sobre as funções puras + a página estática."""
import shutil
import threading
import traceback
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cortes.detector import ChamarLLM, chamar_llm_real
from cortes.episodio import id_do_video
from cortes.painel import coleta, formatos_rotas
from cortes.painel.comparacao import comparaveis, confusoes, dimensao, grupos, matriz
from cortes.painel.dados import ErroPainel, carregar_contas, carregar_vocabulario, ler_yaml
from cortes.painel.ligacao import listar_cortes, sugerir
from cortes.painel.metodo import Linha, bases, montar_linhas
from cortes.painel.publicados import Etiquetas, Publicado, gravar_publicados, ler_publicados, ligar
from cortes.painel.retratos import ler_retratos
from cortes.producao import rotas as rotas_producao
from cortes.producao.estado import ErroProducao
from cortes.producao.etapas import Dependencias, rodar_etapa
from cortes.producao.fila import Fila
from cortes.producao.previas import Previas
from cortes.producao.render import reabrir_render
from cortes.producao.rotas_cortes import AbrirPasta, AcoesCorte, abrir_pasta_real
from cortes.render.corte import Corte
from cortes.render.montagem import FORMATOS, caminho_template
from cortes.render.pipeline import SCRIPT_ROSTO, DepRender, gerar_seo, montar_projeto
from cortes.render.processo import ErroRender, Rodar, rodar_processo
from cortes.render.trilha_biblioteca import BIBLIOTECA, ler_plano

HOSTS_LOCAIS = ("127.0.0.1", "localhost")


@dataclass(frozen=True)
class Config:
    raiz: Path          # onde ficam contas/, nichos/, testes/, episodios/
    skill_dir: Path     # scripts/ da skill youtube-analytics
    estatico: Path      # web/static
    py_visao: Path      # Python com onnxruntime e cv2 (venv do ComfyUI) para o detector de rosto
    modelo_rosto: Path  # mnv3_detection_opt.onnx do OpenSeeFace

    @property
    def contas_yaml(self) -> Path:
        return self.raiz / "contas" / "contas.yaml"

    @property
    def publicados(self) -> Path:
        return self.raiz / "contas" / "publicados.jsonl"

    @property
    def retratos(self) -> Path:
        return self.raiz / "contas" / "retratos"


@dataclass
class EstadoColeta:
    trava: threading.Lock = field(default_factory=threading.Lock)
    rodando: bool = False
    resultados: dict[str, coleta.Resultado] = field(default_factory=dict)
    erro: str | None = None   # exceção inesperada (fora de ErroColeta/ErroPainel/OSError)
    fio: threading.Thread | None = None


class NovaConta(BaseModel):
    id: str
    nome: str
    handle: str
    nicho: str
    perfil_studio: str


class Ligacao(BaseModel):
    link: str
    conta: str
    corte: str
    formato: str
    temas: list[str]
    podcast: str


class PedidoAtualizar(BaseModel):
    conta: str | None = None   # None = todas as contas


def criar_app(cfg: Config, executar: coleta.Executor = coleta._executar,
              abrir: coleta.Abridor = coleta._abrir,
              agora: Callable[[], datetime] = datetime.now, fila: Fila | None = None,
              previas: Previas | None = None, rodar: Rodar = rodar_processo,
              chamar_llm: ChamarLLM = chamar_llm_real, abrir_pasta: AbrirPasta = abrir_pasta_real) -> FastAPI:
    carregar_vocabulario(cfg.raiz)       # configuração inválida: não sobe
    coleta.verificar_skill(cfg.skill_dir)
    npx = verificar_render(cfg)
    dep = DepRender(cfg.py_visao, cfg.modelo_rosto, npx, rodar=rodar, chamar_llm=chamar_llm)
    # ler-validar-gravar de contas.yaml, publicados.jsonl, curadoria e corte.json; a fila do render
    # também a usa para pegar o próximo corte (producao/render.py)
    escrita = threading.Lock()
    fila = fila if fila is not None else _fila_real(cfg, agora, dep, escrita)

    def _previa(pasta: Path, c: Corte) -> None:
        montar_projeto(pasta, c, cfg.raiz, dep)

    previas = previas if previas is not None else Previas(cfg.raiz, _previa)

    @asynccontextmanager
    async def ciclo(_: FastAPI) -> AsyncIterator[None]:
        fila.iniciar()   # só sob uvicorn (ou `with TestClient`): retoma o que ficou rodando
        previas.iniciar()
        yield
        # Sem fase de desligamento, de propósito: a thread da fila é daemon e morre com o
        # processo; o que estava "rodando" é reaberto por `recuperar` na próxima subida.

    app = FastAPI(title="Painel de contas", lifespan=ciclo)
    # Só 127.0.0.1/localhost: uma página de fora não alcança a API por DNS rebinding.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(HOSTS_LOCAIS))
    estado = EstadoColeta()
    app.state.coleta = estado
    app.state.fila = fila

    _handlers(app)
    _rotas_leitura(app, cfg, estado)
    _rotas_acao(app, cfg, estado, escrita, executar, abrir, agora)
    acoes = AcoesCorte(lambda pasta, c: gerar_seo(pasta, c, dep), abrir_pasta)
    rotas_producao.montar(app, cfg.raiz, fila, escrita, agora, previas, acoes, rodar)
    formatos_rotas.montar(app, cfg.raiz)
    app.mount("/", StaticFiles(directory=cfg.estatico, html=True), name="web")
    return app


def _handlers(app: FastAPI) -> None:
    """Exception handlers das rotas: cada erro de domínio vira JSON com a causa (sem default
    silencioso); extraído de `criar_app` para caber no teto de 50 linhas por função."""
    @app.exception_handler(ErroPainel)
    async def _erro(_: Request, e: ErroPainel) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(e)})

    @app.exception_handler(OSError)
    async def _erro_disco(_: Request, e: OSError) -> JSONResponse:
        # ex.: PermissionError após as retentativas do salvar_json (antivírus/indexador
        # segurando o arquivo). Alto no terminal, causa na resposta; tentar de novo costuma bastar.
        traceback.print_exception(e)
        return JSONResponse(status_code=503, content={"detail": f"falha de disco: {type(e).__name__}: {e}"})

    @app.exception_handler(ErroProducao)
    async def _erro_producao(_: Request, e: ErroProducao) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(e)})

    @app.exception_handler(ErroRender)
    async def _erro_render(_: Request, e: ErroRender) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(e)})


def verificar_render(cfg: Config) -> str:
    """Configuração do render ausente (inclusive a biblioteca de trilhas) → o servidor não sobe e
    diz o que falta (spec produção §8).
    Devolve o caminho do npx (no Windows, npx.cmd)."""
    faltas = [f"{nome} não está no PATH" for nome in ("ffmpeg", "npx") if shutil.which(nome) is None]
    arquivos = [("Python da visão (--py-visao)", cfg.py_visao),
                ("modelo do rosto (--modelo-rosto)", cfg.modelo_rosto),
                ("detector de rosto", cfg.raiz / SCRIPT_ROSTO)]
    arquivos += [("template", caminho_template(cfg.raiz, f)) for f in FORMATOS]
    faltas += [f"{rotulo} não existe: {p}" for rotulo, p in arquivos if not p.exists()]
    try:
        ler_plano(cfg.raiz / BIBLIOTECA)
    except ErroRender as e:
        faltas.append(str(e))
    npx = shutil.which("npx")
    if faltas or npx is None:
        raise ErroPainel("render sem configuração: " + "; ".join(faltas))
    return npx


def _fila_real(cfg: Config, agora: Callable[[], datetime], dep_render: DepRender,
               escrita: threading.Lock) -> Fila:
    dep = Dependencias(render=dep_render, escrita=escrita)
    return Fila(cfg.raiz, lambda nome, pasta, e: rodar_etapa(nome, pasta, e, cfg.raiz, dep), agora,
               antes=lambda pasta: reabrir_render(pasta, agora()))


def _rotas_leitura(app: FastAPI, cfg: Config, estado: EstadoColeta) -> None:
    def linhas() -> list[Linha]:
        voc = carregar_vocabulario(cfg.raiz)
        return montar_linhas(ler_retratos(cfg.retratos), ler_publicados(cfg.publicados, voc))

    @app.get("/api/estado")
    def api_estado() -> Any:
        voc = carregar_vocabulario(cfg.raiz)
        retratos = ler_retratos(cfg.retratos)
        pubs = ler_publicados(cfg.publicados, voc)
        base = bases(montar_linhas(retratos, pubs), voc.contas)
        contas = [{**asdict(c), "ultimo_retrato": rs[-1].coletado_em if (rs := retratos.get(c.id)) else None,
                   "coleta": estado.resultados.get(c.id), **asdict(base[c.id]),
                   "ligados": sum(1 for p in pubs if p.conta == c.id)} for c in voc.contas.values()]
        nichos = sorted(p.parent.name for p in (cfg.raiz / "nichos").glob("*/perfil.yaml"))
        formatos = {fid: {**asdict(f), "tem_demo": (cfg.raiz / f.demo).is_file() if f.demo else False}
                    for fid, f in voc.formatos.items()}
        return jsonable_encoder({"contas": contas, "rodando": estado.rodando, "formatos": formatos,
                                 "temas": sorted(voc.temas), "nichos": nichos, "erro_coleta": estado.erro,
                                 "podcasts": sorted({p.etiquetas.podcast for p in pubs})})

    @app.get("/api/shorts")
    def api_shorts() -> Any:
        return jsonable_encoder(linhas())

    @app.get("/api/cortes")
    def api_cortes() -> Any:
        return jsonable_encoder(listar_cortes(cfg.raiz, carregar_vocabulario(cfg.raiz).formatos))

    @app.get("/api/sugestoes/{video_id}")
    def api_sugestoes(video_id: str) -> Any:
        linha = next((x for x in linhas() if x.video_id == video_id), None)
        if linha is None:
            raise ErroPainel(f"vídeo '{video_id}' não está em nenhum retrato")
        cortes = listar_cortes(cfg.raiz, carregar_vocabulario(cfg.raiz).formatos)
        return jsonable_encoder(sugerir(linha.titulo, cortes))

    @app.get("/api/comparar")
    def api_comparar(dim: str = "formato") -> Any:
        d, ls = dimensao(dim), linhas()
        return jsonable_encoder({"grupos": grupos(ls, d), "matriz": matriz(ls), "confusoes": confusoes(ls),
                                 "medidos": comparaveis(ls),
                                 "maturando": sum(1 for x in ls if x.medida.estado == "maturando")})


def _rotas_acao(app: FastAPI, cfg: Config, estado: EstadoColeta, escrita: threading.Lock,
                executar: coleta.Executor, abrir: coleta.Abridor, agora: Callable[[], datetime]) -> None:
    @app.post("/api/atualizar", status_code=202)
    def api_atualizar(pedido: PedidoAtualizar) -> dict[str, bool]:
        voc = carregar_vocabulario(cfg.raiz)
        if pedido.conta is not None and pedido.conta not in voc.contas:
            raise ErroPainel(f"conta '{pedido.conta}' não existe")
        alvo = [voc.contas[pedido.conta]] if pedido.conta else list(voc.contas.values())
        with estado.trava:
            if estado.rodando:
                raise HTTPException(409, "já existe uma atualização rodando")
            estado.rodando = True
            estado.erro = None
            for conta in alvo:   # só as contas desta rodada: a falha das outras continua visível
                estado.resultados.pop(conta.id, None)

        def rodar() -> None:
            try:
                coleta.coletar_todas(alvo, cfg.skill_dir, cfg.retratos, agora, executar,
                                     lambda r: estado.resultados.__setitem__(r.conta, r))
            except Exception as e:
                estado.erro = f"coleta interrompida: {type(e).__name__}: {e}"
                traceback.print_exc()
            finally:
                estado.rodando = False

        estado.fio = threading.Thread(target=rodar, daemon=True)
        estado.fio.start()
        return {"iniciado": True}

    @app.post("/api/login/{conta_id}", status_code=202)
    def api_login(conta_id: str) -> dict[str, bool]:
        voc = carregar_vocabulario(cfg.raiz)
        if conta_id not in voc.contas:
            raise ErroPainel(f"conta '{conta_id}' não existe")
        coleta.abrir_login(voc.contas[conta_id], cfg.skill_dir, abrir)
        return {"aberto": True}

    @app.post("/api/contas", status_code=201)
    def api_nova_conta(nova: NovaConta) -> dict[str, str]:
        with escrita:
            _acrescentar_conta(cfg, nova)
        return {"id": nova.id}

    @app.post("/api/ligar")
    def api_ligar(lig: Ligacao) -> Any:
        with escrita:
            return jsonable_encoder(_ligar(cfg, lig))


def _cabecalho(texto: str) -> str:
    """O bloco de comentários `#` do topo do arquivo original: o dump do YAML não os preserva,
    então quem edita o arquivo por fora (anotação, aviso de "gerado") perderia na próxima gravação."""
    linhas = texto.splitlines(keepends=True)
    fim = next((i for i, linha in enumerate(linhas) if not linha.startswith("#")), len(linhas))
    return "".join(linhas[:fim])


def _acrescentar_conta(cfg: Config, nova: NovaConta) -> None:
    """Grava num .tmp, valida o arquivo inteiro e só então substitui: conta inválida não entra."""
    texto = cfg.contas_yaml.read_text(encoding="utf-8")
    contas_atuais = ler_yaml(cfg.contas_yaml, "contas")  # ErroPainel claro se vazio/inválido
    if not isinstance(contas_atuais, list):
        raise ErroPainel(f"{cfg.contas_yaml}: 'contas' deve ser uma lista")
    bruto = {"contas": [*contas_atuais, nova.model_dump()]}
    tmp = cfg.contas_yaml.with_suffix(".yaml.tmp")
    tmp.write_text(_cabecalho(texto) + yaml.safe_dump(bruto, allow_unicode=True, sort_keys=False),
                   encoding="utf-8")
    try:
        carregar_contas(tmp, cfg.raiz / "nichos")
        tmp.replace(cfg.contas_yaml)
    finally:
        tmp.unlink(missing_ok=True)


def _ligar(cfg: Config, lig: Ligacao) -> Publicado:
    voc = carregar_vocabulario(cfg.raiz)
    if lig.conta not in voc.contas:
        raise ErroPainel(f"conta '{lig.conta}' não existe")
    try:
        vid = id_do_video(lig.link)
    except ValueError as e:
        raise ErroPainel(str(e)) from e
    cortes_conhecidos = {c.caminho for c in listar_cortes(cfg.raiz, voc.formatos)}
    if lig.corte not in cortes_conhecidos:
        raise ErroPainel(f"corte '{lig.corte}' não existe")
    rs = ler_retratos(cfg.retratos).get(lig.conta)
    video = next((v for v in rs[-1].videos if v.video_id == vid), None) if rs else None
    if video is None:
        raise ErroPainel(f"o vídeo {vid} não está no último retrato de '{lig.conta}': "
                         "atualize a conta e tente de novo")
    novo = Publicado(vid, lig.conta, video.publicado_em, lig.corte,
                     Etiquetas(lig.formato, tuple(lig.temas), lig.podcast.strip()))
    gravar_publicados(cfg.publicados, ligar(ler_publicados(cfg.publicados, voc), novo, voc))
    return novo
