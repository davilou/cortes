"""Aprovar ou rejeitar um candidato vira exemplo para o detector (spec produção §4.5).

O exemplo vai para nichos/<nicho>/exemplos/{bons,ruins}.jsonl — o mesmo arquivo que o perfil
lê e o prompt do detector injeta. A decisão fica também em episodios/<id>/curadoria.json para
a tela mostrar. Decisão é definitiva: desfazer exigiria apagar linha do jsonl.

O texto do exemplo vem de frases.json (join de frase_inicio..frase_fim) — o texto que o LLM
viu de verdade — e não de uma janela de tempo sobre palavras.json: um plano B que acolchoa o
corte (padding) não mudaria as frases incluídas, mas mudaria a janela de tempo.

Ordem de gravação (pensando em queda no meio): o exemplo é acrescentado ao jsonl ANTES de
curadoria.json ser gravado. Se cair entre os dois passos, a decisão não existe ainda e uma
repetição do pedido tenta de novo; o append é idempotente porque checa, pelo trio
episódio+início+fim, se a linha já está lá antes de escrever. A ordem inversa (curadoria.json
primeiro) deixaria uma decisão registrada sem o exemplo correspondente — e não há como
detectar isso depois para completar. Pelo mesmo trio, também se confere o arquivo OPOSTO: um
trecho não pode virar exemplo bom e ruim ao mesmo tempo.

`decidir` não trava nada sozinho — quem chama (o servidor do painel) precisa serializar as
chamadas (um lock de escrita), senão duas decisões para o mesmo índice podem entrelaçar leitura
e gravação.
"""
import json
from pathlib import Path
from typing import Any, Literal

from cortes.episodio import ler_json, salvar_json
from cortes.producao.estado import ErroProducao
from cortes.tipos import Frase

Decisao = Literal["aprovado", "rejeitado"]
MOTIVOS = ("começa no meio", "sem gancho", "não fecha", "fora do tema", "pouco espanto", "outro")

_CANDIDATOS = "candidatos.json"
_FRASES = "frases.json"
_CURADORIA = "curadoria.json"


def texto_do_trecho(frases: list[Frase], frase_inicio: int, frase_fim: int) -> str:
    """Junta o texto das frases frase_inicio..frase_fim (inclusive) — o que o LLM viu."""
    por_indice = {f.indice: f.texto for f in frases}
    if frase_inicio > frase_fim or frase_inicio not in por_indice or frase_fim not in por_indice:
        raise ErroProducao(
            f"{_FRASES}: frase_inicio/frase_fim ({frase_inicio}-{frase_fim}) fora do intervalo"
        )
    return " ".join(por_indice[i] for i in range(frase_inicio, frase_fim + 1))


def ler_arquivo(arquivo: Path) -> Any:
    """Lê um JSON de etapa do episódio. Ausente, ilegível ou truncado vira ErroProducao com o
    caminho — a API responde 422 com a causa, não 500. Quem trata "ainda não gerado" como
    vazio confere `exists()` antes; aqui ausente é erro."""
    if not arquivo.exists():
        raise ErroProducao(f"{arquivo}: não existe (a etapa ainda não gerou este arquivo)")
    try:
        return ler_json(arquivo)
    except (OSError, ValueError) as ex:   # ValueError cobre JSONDecodeError e UnicodeDecodeError
        raise ErroProducao(f"{arquivo}: ilegível ({type(ex).__name__}: {ex})") from ex


def candidatos(pasta: Path) -> list[dict[str, Any]]:
    arquivo = pasta / _CANDIDATOS
    if not arquivo.exists():
        raise ErroProducao(f"episódio {pasta.name} ainda não tem candidatos ({arquivo} não existe)")
    lista = ler_arquivo(arquivo)
    if not isinstance(lista, list) or not all(isinstance(c, dict) for c in lista):
        raise ErroProducao(f"{arquivo}: deveria ser uma lista de candidatos (objetos)")
    return lista


def decisoes(pasta: Path) -> dict[int, dict[str, Any]]:
    arquivo = pasta / _CURADORIA
    if not arquivo.exists():
        return {}
    d = ler_arquivo(arquivo)
    if not isinstance(d, dict) or not all(isinstance(v, dict) for v in d.values()):
        raise ErroProducao(f"{arquivo}: deveria ser um objeto {{índice: decisão}}")
    try:
        return {int(k): v for k, v in d.items()}
    except ValueError as ex:
        raise ErroProducao(f"{arquivo}: chave que não é índice ({ex})") from ex


def _frases(pasta: Path) -> list[Frase]:
    arquivo = pasta / _FRASES
    lista = ler_arquivo(arquivo)
    try:
        return [Frase(**f) for f in lista]
    except TypeError as ex:
        raise ErroProducao(f"{arquivo}: frase inválida ({ex})") from ex


def _numero(c: dict[str, Any], campo: str, arquivo: Path) -> float:
    v = c.get(campo)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ErroProducao(f"{arquivo}: campo '{campo}' deveria ser número, veio {v!r}")
    return float(v)


def _inteiro(c: dict[str, Any], campo: str, arquivo: Path) -> int:
    v = c.get(campo)
    if isinstance(v, bool) or not isinstance(v, int):
        raise ErroProducao(f"{arquivo}: campo '{campo}' deveria ser inteiro, veio {v!r}")
    return v


def _texto_campo(c: dict[str, Any], campo: str, arquivo: Path) -> str:
    v = c.get(campo)
    if not isinstance(v, str):
        raise ErroProducao(f"{arquivo}: campo '{campo}' deveria ser texto, veio {v!r}")
    return v


def _candidato(pasta: Path, indice: int) -> dict[str, Any]:
    arquivo = pasta / _CANDIDATOS
    todos = candidatos(pasta)
    if not 0 <= indice < len(todos):
        raise ErroProducao(f"candidato {indice} não existe ({len(todos)} candidatos) em {arquivo}")
    c = todos[indice]
    return {
        "inicio": _numero(c, "inicio", arquivo), "fim": _numero(c, "fim", arquivo),
        "titulo": _texto_campo(c, "titulo", arquivo),
        "frase_inicio": _inteiro(c, "frase_inicio", arquivo), "frase_fim": _inteiro(c, "frase_fim", arquivo),
    }


def _validar_motivo(decisao: Decisao, motivo: str | None) -> str | None:
    if decisao == "rejeitado":
        if not motivo or not motivo.strip():
            raise ErroProducao("rejeitar exige motivo")
        return motivo.strip()
    if motivo is not None:
        raise ErroProducao("aprovar não leva motivo")
    return None


def _validar_decisao_antiga(registrado: dict[str, Any], c: dict[str, Any], indice: int) -> None:
    """Sempre levanta: índice já decidido. candidatos.json regenerado (mesmo índice, outro
    trecho) ganha mensagem própria em vez de confundir com um clique duplicado na tela."""
    if registrado.get("inicio") != c["inicio"] or registrado.get("fim") != c["fim"]:
        raise ErroProducao(
            f"candidato {indice} mudou desde a decisão anterior (candidatos.json foi "
            f"regenerado); decisão antiga era '{registrado['decisao']}'"
        )
    raise ErroProducao(f"candidato {indice} já decidido: {registrado['decisao']}")


def _contem(arquivo: Path, episodio: str, inicio: float, fim: float) -> bool:
    for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
        if not linha.strip():
            continue
        try:
            d = json.loads(linha)
        except json.JSONDecodeError as ex:
            raise ErroProducao(f"{arquivo}: linha {n} inválida ({ex})") from ex
        if d.get("episodio") == episodio and d.get("inicio") == inicio and d.get("fim") == fim:
            return True
    return False


def _gravar_exemplo(raiz: Path, nicho: str, decisao: Decisao, exemplo: dict[str, Any]) -> None:
    pasta_exemplos = raiz / "nichos" / nicho / "exemplos"
    bons, ruins = pasta_exemplos / "bons.jsonl", pasta_exemplos / "ruins.jsonl"
    destino, oposto = (bons, ruins) if decisao == "aprovado" else (ruins, bons)
    if not destino.exists():
        raise ErroProducao(f"arquivo de exemplos não existe: {destino}")
    trio = (exemplo["episodio"], exemplo["inicio"], exemplo["fim"])
    if oposto.exists() and _contem(oposto, *trio):
        rotulo = "bom" if oposto == bons else "ruim"
        raise ErroProducao(f"trecho já registrado como {rotulo} em {oposto}; corrija à mão")
    if _contem(destino, *trio):
        return
    with destino.open("a", encoding="utf-8") as f:
        f.write(json.dumps(exemplo, ensure_ascii=False) + "\n")


def decidir(pasta: Path, raiz: Path, nicho: str, indice: int, decisao: Decisao, motivo: str | None) -> None:
    c = _candidato(pasta, indice)
    motivo_limpo = _validar_motivo(decisao, motivo)
    feitas = decisoes(pasta)
    if indice in feitas:
        _validar_decisao_antiga(feitas[indice], c, indice)
    frases = _frases(pasta)
    texto = texto_do_trecho(frases, c["frase_inicio"], c["frase_fim"])
    exemplo: dict[str, Any] = {"episodio": pasta.name, "inicio": c["inicio"], "fim": c["fim"],
                                "titulo": c["titulo"], "texto": texto}
    if motivo_limpo is not None:
        exemplo["motivo"] = motivo_limpo
    _gravar_exemplo(raiz, nicho, decisao, exemplo)
    registro = {"decisao": decisao, "motivo": motivo_limpo, "inicio": c["inicio"], "fim": c["fim"]}
    todas = {**feitas, indice: registro}
    salvar_json(pasta / _CURADORIA, {str(k): v for k, v in todas.items()})
