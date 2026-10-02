"""Aprovar ou rejeitar um candidato vira exemplo para o detector (spec produção §4.5).

O exemplo vai para nichos/<nicho>/exemplos/{bons,ruins}.jsonl — o mesmo arquivo que o perfil
lê e o prompt do detector injeta. A decisão fica também em episodios/<id>/curadoria.json para
a tela mostrar. Decisão é definitiva: desfazer exigiria apagar linha do jsonl.

Ordem de gravação (pensando em queda no meio): o exemplo é acrescentado ao jsonl ANTES de
curadoria.json ser gravado. Se cair entre os dois passos, a decisão não existe ainda e uma
repetição do pedido tenta de novo; o append é idempotente porque checa, pelo trio
episódio+início+fim, se a linha já está lá antes de escrever. A ordem inversa (curadoria.json
primeiro) deixaria uma decisão registrada sem o exemplo correspondente — e não há como
detectar isso depois para completar.
"""
import json
from pathlib import Path
from typing import Any, Literal

from cortes.episodio import ler_json, salvar_json
from cortes.producao.estado import ErroProducao
from cortes.tipos import Palavra

Decisao = Literal["aprovado", "rejeitado"]
MOTIVOS = ("começa no meio", "sem gancho", "não fecha", "fora do tema", "pouco espanto", "outro")

_CANDIDATOS = "candidatos.json"
_PALAVRAS = "palavras.json"
_CURADORIA = "curadoria.json"


def texto_do_trecho(palavras: list[Palavra], inicio: float, fim: float) -> str:
    return " ".join(p.texto for p in palavras if inicio <= p.inicio < fim)


def decisoes(pasta: Path) -> dict[int, dict[str, Any]]:
    arquivo = pasta / _CURADORIA
    if not arquivo.exists():
        return {}
    return {int(k): v for k, v in ler_json(arquivo).items()}


def _numero(c: dict[str, Any], campo: str, arquivo: Path) -> float:
    v = c.get(campo)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ErroProducao(f"{arquivo}: campo '{campo}' deveria ser número, veio {v!r}")
    return float(v)


def _texto(c: dict[str, Any], campo: str, arquivo: Path) -> str:
    v = c.get(campo)
    if not isinstance(v, str):
        raise ErroProducao(f"{arquivo}: campo '{campo}' deveria ser texto, veio {v!r}")
    return v


def _candidato(pasta: Path, indice: int) -> dict[str, Any]:
    arquivo = pasta / _CANDIDATOS
    candidatos = ler_json(arquivo)
    if not 0 <= indice < len(candidatos):
        raise ErroProducao(f"candidato {indice} não existe ({len(candidatos)} candidatos) em {arquivo}")
    c = candidatos[indice]
    return {"inicio": _numero(c, "inicio", arquivo), "fim": _numero(c, "fim", arquivo),
            "titulo": _texto(c, "titulo", arquivo)}


def _validar_motivo(decisao: Decisao, motivo: str | None) -> str | None:
    if decisao == "rejeitado":
        if not motivo or not motivo.strip():
            raise ErroProducao("rejeitar exige motivo")
        return motivo.strip()
    if motivo is not None:
        raise ErroProducao("aprovar não leva motivo")
    return None


def _ja_existe(destino: Path, episodio: str, inicio: float, fim: float) -> bool:
    for linha in destino.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        d = json.loads(linha)
        if d.get("episodio") == episodio and d.get("inicio") == inicio and d.get("fim") == fim:
            return True
    return False


def _gravar_exemplo(raiz: Path, nicho: str, decisao: Decisao, exemplo: dict[str, Any]) -> None:
    arquivo = "bons.jsonl" if decisao == "aprovado" else "ruins.jsonl"
    destino = raiz / "nichos" / nicho / "exemplos" / arquivo
    if not destino.exists():
        raise ErroProducao(f"arquivo de exemplos não existe: {destino}")
    if _ja_existe(destino, exemplo["episodio"], exemplo["inicio"], exemplo["fim"]):
        return
    with destino.open("a", encoding="utf-8") as f:
        f.write(json.dumps(exemplo, ensure_ascii=False) + "\n")


def decidir(pasta: Path, raiz: Path, nicho: str, indice: int, decisao: Decisao, motivo: str | None) -> None:
    c = _candidato(pasta, indice)
    motivo_limpo = _validar_motivo(decisao, motivo)
    feitas = decisoes(pasta)
    if indice in feitas:
        raise ErroProducao(f"candidato {indice} já decidido: {feitas[indice]['decisao']}")
    palavras = [Palavra(**p) for p in ler_json(pasta / _PALAVRAS)]
    exemplo: dict[str, Any] = {
        "episodio": pasta.name, "inicio": c["inicio"], "fim": c["fim"], "titulo": c["titulo"],
        "texto": texto_do_trecho(palavras, c["inicio"], c["fim"]),
    }
    if motivo_limpo is not None:
        exemplo["motivo"] = motivo_limpo
    _gravar_exemplo(raiz, nicho, decisao, exemplo)
    todas = {**feitas, indice: {"decisao": decisao, "motivo": motivo_limpo}}
    salvar_json(pasta / _CURADORIA, {str(k): v for k, v in todas.items()})
