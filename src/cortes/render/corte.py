"""Corte de um episódio: o candidato que vira Short, o formato e o status do render (spec §4.3).

episodios/<id>/cortes/<indice>/corte.json. O `indice` é o do candidato em candidatos.json, então a
curadoria do plano A (curadoria.json, por índice) vale para o Short. Aprovado e rejeitado ficam lá,
não aqui (uma decisão, um arquivo); o status deste arquivo é só o do render.
"""
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, cast

from cortes.episodio import ler_json, salvar_json
from cortes.producao.estado import ErroProducao

Status = Literal["na_fila", "renderizando", "pronto", "erro"]
STATUS = ("na_fila", "renderizando", "pronto", "erro")
ARQUIVO = "corte.json"


@dataclass(frozen=True)
class Edicoes:
    """Edições do editor (plano C). Chaves de legenda/mascaradas são índices em palavras.json — não
    mudam quando início/fim mudam. Rostos: plano de câmera → pessoa (zera com novo início/fim)."""
    legenda: dict[int, str] = field(default_factory=dict)   # "" tira a palavra da legenda
    mascaradas: tuple[int, ...] = ()
    rostos: dict[int, int] = field(default_factory=dict)
    trilha: str | None = None   # None = automática (LLM); "nenhuma" ou id da cama (editor)
    tema: str | None = None     # f3: None = o do LLM; nome de motion_tema.TEMAS (editor)


@dataclass(frozen=True)
class Corte:
    indice: int
    inicio: float
    fim: float
    formato: str
    titulo: str
    status: Status
    versao: int = 0            # última versão pronta (short-v<versao>.mp4); 0 = nenhuma
    erro: str | None = None
    edicoes: Edicoes = field(default_factory=Edicoes)
    alterado: bool = False     # edição salva e ainda não renderizada
    formato_pronto: str | None = None   # formato de short-v<versao>.mp4; None enquanto versao == 0


def pasta_corte(pasta_ep: Path, indice: int) -> Path:
    return pasta_ep / "cortes" / str(indice)


def video(pasta_ep: Path, c: Corte) -> Path | None:
    return pasta_corte(pasta_ep, c.indice) / f"short-v{c.versao}.mp4" if c.versao else None


def novo_corte(indice: int, cand: dict[str, Any], formato: str) -> Corte:
    return Corte(indice, float(cand["inicio"]), float(cand["fim"]), formato, str(cand["titulo"]), "na_fila")


def iniciar(c: Corte) -> Corte:
    return replace(c, status="renderizando", erro=None)


def concluir(c: Corte) -> Corte:
    return replace(c, status="pronto", versao=c.versao + 1, erro=None, alterado=False,
                   formato_pronto=c.formato)


def falhar(c: Corte, msg: str) -> Corte:
    """A versão anterior (se houver) continua valendo: o MP4 dela não foi tocado (spec §8)."""
    return replace(c, status="erro", erro=msg)


def reenfileirar(c: Corte, formato: str) -> Corte:
    if c.status in ("na_fila", "renderizando"):
        raise ErroProducao(f"corte {c.indice} já está na fila do render")
    return replace(c, status="na_fila", formato=formato, erro=None)


def cancelar(c: Corte) -> Corte | None:
    """Tira da fila um Short que ainda não começou. Com versão pronta, ela continua valendo (volta a
    'pronto' no formato dela, que "Renderizar de novo" pode ter trocado); sem versão e sem edição,
    devolve None e quem chama apaga a pasta do corte; sem versão mas com edição, fica em erro para as
    edições não se perderem."""
    if c.status == "renderizando":
        raise ErroProducao(f"o Short {c.indice} já começou a renderizar; não dá mais para cancelar")
    if c.status != "na_fila":
        raise ErroProducao("só dá para cancelar um Short que está na fila e ainda não começou")
    if c.versao > 0:
        if c.formato_pronto is None:
            raise ErroProducao(f"corte {c.indice} tem versão {c.versao} mas não sabe o formato dela")
        return replace(c, status="pronto", erro=None, formato=c.formato_pronto)
    if c.edicoes == Edicoes() and not c.alterado:
        return None
    return replace(c, status="erro", erro="render cancelado")


def proximo(cortes: list[Corte]) -> Corte | None:
    """Quem ficou 'renderizando' numa queda volta primeiro; depois a fila pela ordem do índice
    (candidatos.json vem da maior nota para a menor)."""
    pendentes = [c for c in cortes if c.status in ("renderizando", "na_fila")]
    return min(pendentes, key=lambda c: (c.status != "renderizando", c.indice), default=None)


def gravar_corte(d: Path, c: Corte) -> None:
    d.mkdir(parents=True, exist_ok=True)
    salvar_json(d / ARQUIVO, asdict(c))


def _campo(x: dict[str, Any], nome: str, tipo: type | tuple[type, ...]) -> Any:
    """Bool é recusado mesmo onde se espera número (em Python, True é um int)."""
    v = x[nome]
    if not isinstance(v, tipo) or isinstance(v, bool):
        raise ValueError(f"campo '{nome}' deveria ser {getattr(tipo, '__name__', tipo)}, veio {v!r}")
    return v


def _int(v: Any, onde: str) -> int:
    """Chave do JSON: o `json` grava toda chave de objeto como texto, então aceita texto numérico."""
    if isinstance(v, bool):
        raise ValueError(f"{onde}: {v!r} não é inteiro")
    try:
        return int(v)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{onde}: {v!r} não é inteiro") from ex


def _int_valor(v: Any, onde: str) -> int:
    """Valor (não chave): tem que já ser `int` de verdade — sem bool, texto nem fração."""
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"{onde}: {v!r} deveria ser inteiro")
    return v


def _edicoes(x: Any) -> Edicoes:
    """Corte do plano B não tem 'edicoes': nasce sem edição (migração explícita de campo novo)."""
    if x is None:
        return Edicoes()
    if not isinstance(x, dict):
        raise ValueError("edicoes deveria ser um objeto")
    if not isinstance(x["legenda"], dict):
        raise ValueError("edicoes.legenda deveria ser um objeto")
    legenda = {_int(k, "edicoes.legenda"): v for k, v in x["legenda"].items()}
    if not all(isinstance(v, str) for v in legenda.values()):
        raise ValueError("edicoes.legenda: textos deveriam ser texto")
    if not isinstance(x["mascaradas"], list):
        raise ValueError("edicoes.mascaradas deveria ser uma lista")
    mascaradas = tuple(sorted(_int_valor(i, "edicoes.mascaradas") for i in x["mascaradas"]))
    if not isinstance(x["rostos"], dict):
        raise ValueError("edicoes.rostos deveria ser um objeto")
    rostos = {_int(k, "edicoes.rostos"): _int_valor(v, "edicoes.rostos") for k, v in x["rostos"].items()}
    trilha = x.get("trilha")   # ausente: corte de antes da trilha (migração: automática)
    if trilha is not None and not isinstance(trilha, str):
        raise ValueError(f"edicoes.trilha deveria ser texto ou nulo, veio {trilha!r}")
    tema = x.get("tema")   # ausente: corte de antes do tema (migração: o do LLM)
    if tema is not None and not isinstance(tema, str):
        raise ValueError(f"edicoes.tema deveria ser texto ou nulo, veio {tema!r}")
    return Edicoes(legenda, mascaradas, rostos, trilha, tema)


def _basicos(x: dict[str, Any], d: Path) -> Corte:
    """Campos simples do corte (sem edicoes/alterado); extraído para `ler_corte` caber em 50 linhas."""
    if x["status"] not in STATUS:
        raise ValueError(f"status '{x['status']}' inválido; use um de {STATUS}")
    if x["erro"] is not None and not isinstance(x["erro"], str):
        raise ValueError("campo 'erro' deveria ser texto ou nulo")
    indice = _campo(x, "indice", int)
    if indice != int(d.name):
        raise ValueError(f"indice {indice} não bate com a pasta '{d.name}'")
    inicio, fim = float(_campo(x, "inicio", (int, float))), float(_campo(x, "fim", (int, float)))
    if inicio >= fim:
        raise ValueError(f"inicio {inicio} deveria ser menor que fim {fim}")
    versao = _campo(x, "versao", int)
    if versao < 0:
        raise ValueError(f"versao {versao} não pode ser negativa")
    status = cast(Status, x["status"])
    if status == "pronto" and versao < 1:
        raise ValueError("status 'pronto' exige versao >= 1")
    return Corte(indice, inicio, fim, _campo(x, "formato", str), _campo(x, "titulo", str),
                 status, versao, x["erro"])


def _formato_pronto(x: dict[str, Any], versao: int) -> str | None:
    """Ausente: corte.json de antes do campo (migração explícita) — com versão, o formato atual é o
    da versão pronta (vale enquanto ninguém o trocou depois do último render); sem versão, None."""
    if "formato_pronto" not in x:
        return _campo(x, "formato", str) if versao > 0 else None
    v = x["formato_pronto"]
    if v is not None and not isinstance(v, str):
        raise ValueError(f"campo 'formato_pronto' deveria ser texto ou nulo, veio {v!r}")
    if (v is None) != (versao == 0):
        raise ValueError(f"formato_pronto {v!r} não combina com versao {versao}")
    return v


def ler_corte(d: Path) -> Corte:
    """`indice` tem que bater com o nome da pasta (uma fonte da verdade só); `versao` não pode ser
    negativa; `status == "pronto"` exige `versao >= 1` (pronto sem MP4 nenhum não existe); `inicio`
    tem que ser menor que `fim`."""
    arq = d / ARQUIVO
    try:
        x = ler_json(arq)
        c = _basicos(x, d)
        edicoes = _edicoes(x.get("edicoes"))
        alterado = x.get("alterado", False)   # ausente: corte do plano B (migração)
        if not isinstance(alterado, bool):
            raise ValueError("campo 'alterado' deveria ser booleano")
        return replace(c, edicoes=edicoes, alterado=alterado, formato_pronto=_formato_pronto(x, c.versao))
    except (OSError, KeyError, TypeError, ValueError) as ex:
        raise ErroProducao(f"{arq}: corte inválido ({ex})") from ex


def _indice_da_pasta(arq: Path) -> int:
    try:
        return int(arq.parent.name)
    except ValueError as ex:
        raise ErroProducao(f"{arq.parent}: nome de pasta não é um índice numérico ({ex})") from ex


def _ler_se_existe(d: Path) -> Corte | None:
    """corte.json apagado entre o glob e a leitura (um Cancelar) é corte que não existe mais, não
    corte inválido; qualquer outro problema de leitura continua sendo erro."""
    try:
        return ler_corte(d)
    except ErroProducao as ex:
        if isinstance(ex.__cause__, FileNotFoundError):
            return None
        raise


def cortes_do_episodio(pasta_ep: Path) -> list[Corte]:
    arqs = sorted((pasta_ep / "cortes").glob(f"*/{ARQUIVO}"), key=_indice_da_pasta)
    return [c for a in arqs if (c := _ler_se_existe(a.parent)) is not None]

