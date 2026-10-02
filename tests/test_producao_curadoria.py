import json
from pathlib import Path

import pytest

from cortes.producao.curadoria import MOTIVOS, decidir, decisoes, texto_do_trecho
from cortes.producao.estado import ErroProducao
from cortes.tipos import Palavra

CAND = {"frase_inicio": 0, "frase_fim": 1, "inicio": 10.0, "fim": 12.0, "notas": {}, "bonus": ["humor"],
        "penalidades": [], "justificativa": "j", "titulo": "Ganhei dez mil", "nota_final": 80.0}


def montar(tmp: Path) -> tuple[Path, Path]:
    raiz = tmp
    ex = raiz / "nichos" / "financas" / "exemplos"
    ex.mkdir(parents=True)
    for a in ("bons.jsonl", "ruins.jsonl"):
        (ex / a).write_text("", encoding="utf-8")
    pasta = raiz / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    (pasta / "candidatos.json").write_text(json.dumps([CAND]), encoding="utf-8")
    dados = [("antes", 9.0), ("Eu", 10.0), ("ganhei", 10.5), ("dez", 11.0), ("mil.", 11.5), ("depois", 12.5)]
    palavras = [{"texto": t, "inicio": i, "fim": i + 0.5} for t, i in dados]
    (pasta / "palavras.json").write_text(json.dumps(palavras), encoding="utf-8")
    return raiz, pasta


def test_texto_do_trecho() -> None:
    ps = [Palavra("a", 0, 1), Palavra("b", 1, 2), Palavra("c", 2, 3)]
    assert texto_do_trecho(ps, 1.0, 2.0) == "b"


def test_aprovar_grava_exemplo_bom(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    decidir(pasta, raiz, "financas", 0, "aprovado", None)
    bons = (raiz / "nichos/financas/exemplos/bons.jsonl").read_text(encoding="utf-8").splitlines()
    ex = json.loads(bons[0])
    assert ex["texto"] == "Eu ganhei dez mil."
    assert ex["titulo"] == "Ganhei dez mil" and ex["episodio"] == "abcdefghijk"
    assert decisoes(pasta) == {0: {"decisao": "aprovado", "motivo": None}}


def test_rejeitar_exige_motivo_e_grava_exemplo_ruim(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    with pytest.raises(ErroProducao, match="motivo"):
        decidir(pasta, raiz, "financas", 0, "rejeitado", " ")
    decidir(pasta, raiz, "financas", 0, "rejeitado", f"{MOTIVOS[0]}: começa no 'e aí'")
    ruins = (raiz / "nichos/financas/exemplos/ruins.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(ruins[0])["motivo"].startswith(MOTIVOS[0])


def test_decisao_e_definitiva(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    decidir(pasta, raiz, "financas", 0, "aprovado", None)
    with pytest.raises(ErroProducao, match="já decidido"):
        decidir(pasta, raiz, "financas", 0, "rejeitado", "outro")


def test_indice_invalido(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    with pytest.raises(ErroProducao, match="candidato 5"):
        decidir(pasta, raiz, "financas", 5, "aprovado", None)
