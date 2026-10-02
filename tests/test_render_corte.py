import json
from dataclasses import replace
from pathlib import Path

import pytest

from cortes.producao.estado import ErroProducao
from cortes.render.corte import (
    PLANEJADO,
    Corte,
    Edicoes,
    concluir,
    cortes_do_episodio,
    falhar,
    gravar_corte,
    iniciar,
    ler_corte,
    melhores,
    novo_corte,
    pasta_corte,
    planejar,
    proximo,
    reenfileirar,
    video,
)

CANDS = [{"inicio": 10.0, "fim": 40.0, "titulo": "A", "nota_final": 50.0},
         {"inicio": 50.0, "fim": 80.0, "titulo": "B", "nota_final": 90.0},
         {"inicio": 90.0, "fim": 120.0, "titulo": "C", "nota_final": 70.0}]


def test_melhores_pela_nota() -> None:
    assert melhores(CANDS, 2) == [1, 2] and melhores(CANDS, 10) == [1, 2, 0]


def test_transicoes() -> None:
    c = novo_corte(1, CANDS[1], "f7")
    assert c == Corte(1, 50.0, 80.0, "f7", "B", "na_fila")
    pronto = concluir(iniciar(c))
    assert pronto.status == "pronto" and pronto.versao == 1
    erro = falhar(iniciar(pronto), "ErroRender: x")
    assert erro.status == "erro" and erro.versao == 1 and erro.erro == "ErroRender: x"
    de_novo = reenfileirar(erro, "f1")
    assert de_novo.status == "na_fila" and de_novo.formato == "f1" and de_novo.erro is None


@pytest.mark.parametrize("status", ["na_fila", "renderizando"])
def test_reenfileirar_recusa_quem_ja_esta_na_fila(status: str) -> None:
    c = novo_corte(0, CANDS[0], "f7")
    c = iniciar(c) if status == "renderizando" else c
    with pytest.raises(ErroProducao, match="já está na fila"):
        reenfileirar(c, "f7")


def test_proximo_retoma_quem_ficou_renderizando() -> None:
    a, b = novo_corte(0, CANDS[0], "f7"), iniciar(novo_corte(2, CANDS[2], "f7"))
    assert proximo([a, b]) == b
    assert proximo([a, concluir(b)]) == a and proximo([concluir(a)]) is None


def test_gravar_ler_e_listar(tmp_path: Path) -> None:
    c = novo_corte(2, CANDS[2], "f1")
    gravar_corte(pasta_corte(tmp_path, 2), c)
    assert ler_corte(pasta_corte(tmp_path, 2)) == c
    assert cortes_do_episodio(tmp_path) == [c] and video(tmp_path, c) is None
    assert video(tmp_path, concluir(c)) == tmp_path / "cortes" / "2" / "short-v1.mp4"


def test_corte_invalido(tmp_path: Path) -> None:
    d = pasta_corte(tmp_path, 0)
    d.mkdir(parents=True)
    (d / "corte.json").write_text(json.dumps({"indice": 0, "status": "voando"}), encoding="utf-8")
    with pytest.raises(ErroProducao, match="corte.json"):
        ler_corte(d)


def _corte_json(**sobrescreve: object) -> dict[str, object]:
    base: dict[str, object] = {"indice": 2, "inicio": 10.0, "fim": 40.0, "formato": "f7",
                               "titulo": "T", "status": "na_fila", "versao": 0, "erro": None}
    return {**base, **sobrescreve}


def test_indice_do_json_tem_que_bater_com_a_pasta(tmp_path: Path) -> None:
    d = pasta_corte(tmp_path, 2)
    d.mkdir(parents=True)
    (d / "corte.json").write_text(json.dumps(_corte_json(indice=3)), encoding="utf-8")
    with pytest.raises(ErroProducao, match="corte.json"):
        ler_corte(d)


def test_versao_negativa_e_erro(tmp_path: Path) -> None:
    d = pasta_corte(tmp_path, 2)
    d.mkdir(parents=True)
    (d / "corte.json").write_text(json.dumps(_corte_json(versao=-1)), encoding="utf-8")
    with pytest.raises(ErroProducao, match="corte.json"):
        ler_corte(d)


def test_status_pronto_exige_versao_maior_ou_igual_a_1(tmp_path: Path) -> None:
    d = pasta_corte(tmp_path, 2)
    d.mkdir(parents=True)
    (d / "corte.json").write_text(json.dumps(_corte_json(status="pronto", versao=0)), encoding="utf-8")
    with pytest.raises(ErroProducao, match="corte.json"):
        ler_corte(d)


def test_inicio_tem_que_ser_menor_que_fim(tmp_path: Path) -> None:
    d = pasta_corte(tmp_path, 2)
    d.mkdir(parents=True)
    (d / "corte.json").write_text(json.dumps(_corte_json(inicio=40.0, fim=40.0)), encoding="utf-8")
    with pytest.raises(ErroProducao, match="corte.json"):
        ler_corte(d)


def test_cortes_do_episodio_com_pasta_nao_numerica_e_erro_de_producao(tmp_path: Path) -> None:
    d = tmp_path / "cortes" / "abc"
    d.mkdir(parents=True)
    (d / "corte.json").write_text(json.dumps(_corte_json(indice=0)), encoding="utf-8")
    with pytest.raises(ErroProducao, match="abc"):
        cortes_do_episodio(tmp_path)


def test_cortes_do_episodio_ordena_por_indice_numerico(tmp_path: Path) -> None:
    gravar_corte(pasta_corte(tmp_path, 10), novo_corte(10, CANDS[1], "f7"))
    gravar_corte(pasta_corte(tmp_path, 2), novo_corte(2, CANDS[2], "f7"))
    assert [c.indice for c in cortes_do_episodio(tmp_path)] == [2, 10]


def test_planejar_uma_vez_sem_pisar_no_manual(tmp_path: Path) -> None:
    gravar_corte(pasta_corte(tmp_path, 1), novo_corte(1, CANDS[1], "f1"))   # Renderizar manual antes
    planejar(tmp_path, "f7", 2, CANDS)
    assert [(c.indice, c.formato) for c in cortes_do_episodio(tmp_path)] == [(1, "f1"), (2, "f7")]
    assert (tmp_path / "cortes" / PLANEJADO).exists()


def test_edicoes_vao_e_voltam_do_disco(tmp_path: Path) -> None:
    ed = Edicoes({5: "ChatGPT", 6: ""}, (9,), {1: 0})
    c = replace(novo_corte(2, CANDS[2], "f7"), edicoes=ed, alterado=True)
    gravar_corte(pasta_corte(tmp_path, 2), c)
    assert ler_corte(pasta_corte(tmp_path, 2)) == c


def test_corte_do_plano_b_sem_edicoes_migra(tmp_path: Path) -> None:
    d = pasta_corte(tmp_path, 0)
    d.mkdir(parents=True)
    x = {"indice": 0, "inicio": 10.0, "fim": 40.0, "formato": "f7", "titulo": "A", "status": "na_fila",
         "versao": 0, "erro": None}
    (d / "corte.json").write_text(json.dumps(x), encoding="utf-8")
    c = ler_corte(d)
    assert c.edicoes == Edicoes() and c.alterado is False


def test_concluir_limpa_alterado() -> None:
    c = replace(iniciar(novo_corte(0, CANDS[0], "f7")), alterado=True)
    assert concluir(c).alterado is False


@pytest.mark.parametrize("edicoes", [
    {"legenda": {"x": "a"}, "mascaradas": [], "rostos": {}},
    {"legenda": {"1": 3}, "mascaradas": [], "rostos": {}},
    {"legenda": {}, "mascaradas": ["a"], "rostos": {}},
    {"legenda": {}, "mascaradas": [], "rostos": {"0": "a"}},
    {"legenda": [], "mascaradas": [], "rostos": {}},
    {"legenda": {}, "mascaradas": [], "rostos": []},
    {"legenda": {}, "mascaradas": "12", "rostos": {}},
    {"legenda": {}, "mascaradas": [1.9], "rostos": {}},
    {"legenda": {}, "mascaradas": [], "rostos": {"0": "1"}},
])
def test_edicoes_invalidas(tmp_path: Path, edicoes: dict[str, object]) -> None:
    d = pasta_corte(tmp_path, 0)
    gravar_corte(d, novo_corte(0, CANDS[0], "f7"))
    x = json.loads((d / "corte.json").read_text(encoding="utf-8"))
    (d / "corte.json").write_text(json.dumps({**x, "edicoes": edicoes}), encoding="utf-8")
    with pytest.raises(ErroProducao, match="edicoes"):
        ler_corte(d)
