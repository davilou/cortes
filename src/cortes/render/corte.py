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
PLANEJADO = "planejado.json"   # marcador: os N melhores já foram postos na fila (uma vez por episódio)


@dataclass(frozen=True)
class Edicoes:
    """Edições do editor (plano C). Chaves de legenda/mascaradas são índices em palavras.json — não
    mudam quando início/fim mudam. Rostos: plano de câmera → pessoa (zera com novo início/fim)."""
    legenda: dict[int, str] = field(default_factory=dict)   # "" tira a palavra da legenda
    mascaradas: tuple[int, ...] = ()
    rostos: dict[int, int] = field(default_factory=dict)


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


def pasta_corte(pasta_ep: Path, indice: int) -> Path:
    return pasta_ep / "cortes" / str(indice)


def video(pasta_ep: Path, c: Corte) -> Path | None:
    return pasta_corte(pasta_ep, c.indice) / f"short-v{c.versao}.mp4" if c.versao else None


def novo_corte(indice: int, cand: dict[str, Any], formato: str) -> Corte:
    return Corte(indice, float(cand["inicio"]), float(cand["fim"]), formato, str(cand["titulo"]), "na_fila")


def melhores(cands: list[dict[str, Any]], n: int) -> list[int]:
    return sorted(range(len(cands)), key=lambda i: (-float(cands[i]["nota_final"]), i))[:n]


def iniciar(c: Corte) -> Corte:
    return replace(c, status="renderizando", erro=None)


def concluir(c: Corte) -> Corte:
    return replace(c, status="pronto", versao=c.versao + 1, erro=None, alterado=False)


def falhar(c: Corte, msg: str) -> Corte:
    """A versão anterior (se houver) continua valendo: o MP4 dela não foi tocado (spec §8)."""
    return replace(c, status="erro", erro=msg)


def reenfileirar(c: Corte, formato: str) -> Corte:
    if c.status in ("na_fila", "renderizando"):
        raise ErroProducao(f"corte {c.indice} já está na fila do render")
    return replace(c, status="na_fila", formato=formato, erro=None)


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
    if isinstance(v, bool):
        raise ValueError(f"{onde}: {v!r} não é inteiro")
    try:
        return int(v)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{onde}: {v!r} não é inteiro") from ex


def _edicoes(x: Any) -> Edicoes:
    """Corte do plano B não tem 'edicoes': nasce sem edição (migração explícita de campo novo)."""
    if x is None:
        return Edicoes()
    if not isinstance(x, dict):
        raise ValueError("edicoes deveria ser um objeto")
    legenda = {_int(k, "edicoes.legenda"): v for k, v in x["legenda"].items()}
    if not all(isinstance(v, str) for v in legenda.values()):
        raise ValueError("edicoes.legenda: textos deveriam ser texto")
    mascaradas = tuple(sorted(_int(i, "edicoes.mascaradas") for i in x["mascaradas"]))
    rostos = {_int(k, "edicoes.rostos"): _int(v, "edicoes.rostos") for k, v in x["rostos"].items()}
    return Edicoes(legenda, mascaradas, rostos)


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
        return replace(c, edicoes=edicoes, alterado=alterado)
    except (OSError, KeyError, TypeError, ValueError) as ex:
        raise ErroProducao(f"{arq}: corte inválido ({ex})") from ex


def _indice_da_pasta(arq: Path) -> int:
    try:
        return int(arq.parent.name)
    except ValueError as ex:
        raise ErroProducao(f"{arq.parent}: nome de pasta não é um índice numérico ({ex})") from ex


def cortes_do_episodio(pasta_ep: Path) -> list[Corte]:
    arqs = sorted((pasta_ep / "cortes").glob(f"*/{ARQUIVO}"), key=_indice_da_pasta)
    return [ler_corte(a.parent) for a in arqs]


def planejar(pasta_ep: Path, formato: str, n: int, cands: list[dict[str, Any]]) -> None:
    """Põe os N melhores na fila do render, uma vez por episódio. Um corte que já existe (Renderizar
    manual antes do automático) fica como está."""
    (pasta_ep / "cortes").mkdir(parents=True, exist_ok=True)
    for i in melhores(cands, n):
        d = pasta_corte(pasta_ep, i)
        if not (d / ARQUIVO).exists():
            gravar_corte(d, novo_corte(i, cands[i], formato))
    salvar_json(pasta_ep / "cortes" / PLANEJADO, {"n": n, "formato": formato})
