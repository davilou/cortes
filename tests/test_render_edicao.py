from dataclasses import replace

import pytest

from cortes.producao.estado import ErroProducao
from cortes.render.corte import Edicoes, novo_corte
from cortes.render.edicao import (
    AUTOMATICO,
    Edicao,
    aplicar,
    eh_palavrao,
    indices_do_corte,
    mascarar,
    palavras_editadas,
)
from cortes.tipos import Palavra

TODAS = [Palavra(t, float(i), i + 0.8) for i, t in
         enumerate(["Antes.", "Mas", "eu", "perdi", "porra,", "tudo", "no", "chat", "GPT.", "Depois"])]
C = novo_corte(0, {"inicio": 1.0, "fim": 8.8, "titulo": "T"}, "f7")


@pytest.mark.parametrize("antes, depois", [
    ("porra,", "p*rra,"), ("Merda.", "M*rda."), ("cu", "c*"), ("123", "123")])
def test_mascarar(antes: str, depois: str) -> None:
    assert mascarar(antes) == depois


def test_eh_palavrao_ignora_caixa_acento_e_pontuacao() -> None:
    assert eh_palavrao("Porra,") and eh_palavrao("DESGRAÇA!") and not eh_palavrao("porta")


def test_indices_do_corte() -> None:
    assert indices_do_corte(TODAS, 1.0, 8.8) == (1, 8)
    with pytest.raises(ErroProducao, match="nenhuma palavra"):
        indices_do_corte(TODAS, 20.0, 30.0)


def test_palavras_editadas_troca_apaga_e_mascara() -> None:
    ws = palavras_editadas(TODAS, Edicoes({7: "ChatGPT.", 8: ""}, (4,), {}))
    assert [w.texto for w in ws][3:8] == ["perdi", "p*rra,", "tudo", "no", "ChatGPT."]
    assert len(ws) == 9


def test_mover_inicio_e_fim_por_palavra_zera_rostos() -> None:
    c = replace(C, edicoes=Edicoes(rostos={0: 1}))
    novo = aplicar(c, Edicao(inicio_palavra=2, fim_palavra=6), TODAS, [2])
    assert (novo.inicio, novo.fim, novo.edicoes.rostos, novo.alterado) == (2.0, 6.8, {}, True)


@pytest.mark.parametrize("ed, erro", [
    (Edicao(inicio_palavra=6, fim_palavra=2), "antes do fim"),
    (Edicao(inicio_palavra=99), "palavra 99"),
    (Edicao(inicio_palavra=3, fim_palavra=3), "duração"),
    (Edicao(titulo="  "), "título"),
    (Edicao(formato="f9"), "o formato f9 virou o f4 B-roll"),
    (Edicao(formato="f2"), "formato 'f2' ainda não renderiza"),
    (Edicao(rosto=(0, 2)), "pessoa 2"),
    (Edicao(rosto=(3, 0)), "plano 3"),
])
def test_edicao_recusada(ed: Edicao, erro: str) -> None:
    with pytest.raises(ErroProducao, match=erro):
        aplicar(C, ed, TODAS, [2])


def test_legenda_mascarar_e_palavroes() -> None:
    novo = aplicar(C, Edicao(legenda={7: "ChatGPT.", 8: "", 2: "eu"}, mascarar_palavroes=True), TODAS, [])
    assert novo.edicoes.legenda == {7: "ChatGPT.", 8: ""} and novo.edicoes.mascaradas == (4,)
    de_volta = aplicar(novo, Edicao(legenda={7: None}, mascarar={4: False}), TODAS, [])
    assert de_volta.edicoes.legenda == {8: ""} and de_volta.edicoes.mascaradas == ()


def test_sem_mudanca_nao_marca_alterado() -> None:
    assert aplicar(C, Edicao(titulo="T"), TODAS, []).alterado is False
    assert aplicar(C, Edicao(rosto=(0, 1)), TODAS, [2]).edicoes.rostos == {0: 1}


def test_rosto_automatico_apaga_a_escolha_do_plano() -> None:
    """Pessoa AUTOMATICO (-1) desfaz a escolha manual: o plano volta à padrão e, no f7, a alternar."""
    escolhido = aplicar(C, Edicao(rosto=(0, 1)), TODAS, [2])
    de_volta = aplicar(escolhido, Edicao(rosto=(0, AUTOMATICO)), TODAS, [2])
    assert de_volta.edicoes.rostos == {} and de_volta.alterado is True
    assert aplicar(C, Edicao(rosto=(0, AUTOMATICO)), TODAS, [2]) == C
    with pytest.raises(ErroProducao, match="pessoa -2"):
        aplicar(C, Edicao(rosto=(0, -2)), TODAS, [2])


def test_mudar_trecho_e_escolher_rosto_junto_e_recusado() -> None:
    with pytest.raises(ErroProducao, match="escolha o rosto depois de mudar"):
        aplicar(C, Edicao(inicio_palavra=2, fim_palavra=6, rosto=(0, 1)), TODAS, [2])


def test_trilha_escolhida_auto_e_sem() -> None:
    c = aplicar(C, Edicao(trilha="B"), TODAS, [], camas=("A", "B", "C"))
    assert c.edicoes.trilha == "B" and c.alterado
    assert aplicar(c, Edicao(trilha="auto"), TODAS, [], camas=("A", "B", "C")).edicoes.trilha is None
    assert aplicar(c, Edicao(trilha="nenhuma"), TODAS, []).edicoes.trilha == "nenhuma"


def test_trilha_desconhecida_e_erro() -> None:
    with pytest.raises(ErroProducao, match="trilha 'Z'"):
        aplicar(C, Edicao(trilha="Z"), TODAS, [], camas=("A", "B", "C"))


def test_mudar_trilha_nao_mexe_no_resto() -> None:
    c = replace(C, edicoes=Edicoes(legenda={1: "oi"}, rostos={0: 1}))
    novo = aplicar(c, Edicao(trilha="nenhuma"), TODAS, [])
    assert novo.edicoes == replace(c.edicoes, trilha="nenhuma")
