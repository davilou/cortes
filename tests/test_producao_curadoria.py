import json
from pathlib import Path

import pytest

from cortes.producao.curadoria import MOTIVOS, decidir, decisoes, texto_do_trecho
from cortes.producao.estado import ErroProducao
from cortes.tipos import Frase

CAND = {"frase_inicio": 0, "frase_fim": 1, "inicio": 10.0, "fim": 12.0, "notas": {}, "bonus": ["humor"],
        "penalidades": [], "justificativa": "j", "titulo": "Ganhei dez mil", "nota_final": 80.0}
TEXTO_ESPERADO = "Eu ganhei dez mil."


def montar(tmp: Path) -> tuple[Path, Path]:
    raiz = tmp
    ex = raiz / "nichos" / "financas" / "exemplos"
    ex.mkdir(parents=True)
    for a in ("bons.jsonl", "ruins.jsonl"):
        (ex / a).write_text("", encoding="utf-8")
    pasta = raiz / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    (pasta / "candidatos.json").write_text(json.dumps([CAND]), encoding="utf-8")
    frases = [{"indice": 0, "texto": "Eu ganhei", "inicio": 10.0, "fim": 11.0},
              {"indice": 1, "texto": "dez mil.", "inicio": 11.0, "fim": 12.0}]
    (pasta / "frases.json").write_text(json.dumps(frases), encoding="utf-8")
    return raiz, pasta


def linha_exemplo(texto: str = TEXTO_ESPERADO) -> dict[str, object]:
    return {"episodio": "abcdefghijk", "inicio": 10.0, "fim": 12.0,
            "titulo": "Ganhei dez mil", "texto": texto}


def test_texto_do_trecho() -> None:
    fs = [Frase(0, "a", 0, 1), Frase(1, "b", 1, 2), Frase(2, "c", 2, 3)]
    assert texto_do_trecho(fs, 0, 1) == "a b"


def test_texto_do_trecho_fora_do_intervalo_falha() -> None:
    fs = [Frase(0, "a", 0, 1)]
    with pytest.raises(ErroProducao, match="frases.json"):
        texto_do_trecho(fs, 0, 5)


def test_aprovar_grava_exemplo_bom(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    decidir(pasta, raiz, "financas", 0, "aprovado", None)
    bons = (raiz / "nichos/financas/exemplos/bons.jsonl").read_text(encoding="utf-8").splitlines()
    ex = json.loads(bons[0])
    assert ex["texto"] == TEXTO_ESPERADO
    assert ex["titulo"] == "Ganhei dez mil" and ex["episodio"] == "abcdefghijk"
    assert decisoes(pasta) == {0: {"decisao": "aprovado", "motivo": None, "inicio": 10.0, "fim": 12.0}}


def test_rejeitar_exige_motivo_e_grava_exemplo_ruim(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    with pytest.raises(ErroProducao, match="motivo"):
        decidir(pasta, raiz, "financas", 0, "rejeitado", " ")
    decidir(pasta, raiz, "financas", 0, "rejeitado", f"{MOTIVOS[0]}: começa no 'e aí'")
    ruins = (raiz / "nichos/financas/exemplos/ruins.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(ruins[0])["motivo"].startswith(MOTIVOS[0])


def test_aprovar_nao_leva_motivo(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    with pytest.raises(ErroProducao, match="não leva motivo"):
        decidir(pasta, raiz, "financas", 0, "aprovado", "qualquer")


def test_decisao_e_definitiva(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    decidir(pasta, raiz, "financas", 0, "aprovado", None)
    with pytest.raises(ErroProducao, match="já decidido"):
        decidir(pasta, raiz, "financas", 0, "rejeitado", "outro")


def test_candidato_mudou_apos_decisao_falha(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    decidir(pasta, raiz, "financas", 0, "aprovado", None)
    outro = {**CAND, "inicio": 20.0, "fim": 22.0}
    (pasta / "candidatos.json").write_text(json.dumps([outro]), encoding="utf-8")
    with pytest.raises(ErroProducao, match="mudou"):
        decidir(pasta, raiz, "financas", 0, "rejeitado", "outro")


def test_indice_invalido(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    with pytest.raises(ErroProducao, match="candidato 5"):
        decidir(pasta, raiz, "financas", 5, "aprovado", None)


def test_candidato_com_campo_invalido(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    ruim = {**CAND, "inicio": "dez"}
    (pasta / "candidatos.json").write_text(json.dumps([ruim]), encoding="utf-8")
    with pytest.raises(ErroProducao, match="inicio"):
        decidir(pasta, raiz, "financas", 0, "aprovado", None)


def test_arquivo_de_exemplos_ausente(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    (raiz / "nichos/financas/exemplos/bons.jsonl").unlink()
    with pytest.raises(ErroProducao, match="não existe"):
        decidir(pasta, raiz, "financas", 0, "aprovado", None)


def test_retentativa_depois_de_queda_nao_duplica_exemplo(tmp_path: Path) -> None:
    """Simula a queda depois do append e antes de curadoria.json: a linha já está no jsonl,
    mas a decisão ainda não foi gravada. A repetição do pedido não duplica a linha."""
    raiz, pasta = montar(tmp_path)
    bons = raiz / "nichos/financas/exemplos/bons.jsonl"
    bons.write_text(json.dumps(linha_exemplo(), ensure_ascii=False) + "\n", encoding="utf-8")
    decidir(pasta, raiz, "financas", 0, "aprovado", None)
    assert len(bons.read_text(encoding="utf-8").splitlines()) == 1
    assert decisoes(pasta) == {0: {"decisao": "aprovado", "motivo": None, "inicio": 10.0, "fim": 12.0}}


def test_trecho_ja_aprovado_nao_pode_ser_rejeitado(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    bons = raiz / "nichos/financas/exemplos/bons.jsonl"
    bons.write_text(json.dumps(linha_exemplo(), ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(ErroProducao, match="já registrado como bom"):
        decidir(pasta, raiz, "financas", 0, "rejeitado", f"{MOTIVOS[0]}: x")
    ruins = raiz / "nichos/financas/exemplos/ruins.jsonl"
    assert ruins.read_text(encoding="utf-8") == ""
    assert decisoes(pasta) == {}


def test_linha_invalida_no_jsonl_falha_com_arquivo_e_linha(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    bons = raiz / "nichos/financas/exemplos/bons.jsonl"
    bons.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(ErroProducao, match="linha 1"):
        decidir(pasta, raiz, "financas", 0, "aprovado", None)
