import json
from dataclasses import replace
from pathlib import Path

import pytest

from cortes.producao.estado import ErroProducao
from cortes.render.corte import (
    Corte,
    Edicoes,
    cancelar,
    concluir,
    cortes_do_episodio,
    falhar,
    gravar_corte,
    iniciar,
    ler_corte,
    novo_corte,
    pasta_corte,
    proximo,
    reenfileirar,
    video,
)

CANDS = [{"inicio": 10.0, "fim": 40.0, "titulo": "A", "nota_final": 50.0},
         {"inicio": 50.0, "fim": 80.0, "titulo": "B", "nota_final": 90.0},
         {"inicio": 90.0, "fim": 120.0, "titulo": "C", "nota_final": 70.0}]


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


def test_cancelar_com_versao_volta_a_pronto() -> None:
    pronto = concluir(iniciar(novo_corte(0, CANDS[0], "f7")))
    c = cancelar(reenfileirar(pronto, "f1"))
    assert c is not None and c.status == "pronto" and c.versao == 1 and c.erro is None


def test_cancelar_sem_versao_nem_edicao_some() -> None:
    assert cancelar(novo_corte(0, CANDS[0], "f7")) is None


@pytest.mark.parametrize("muda", [{"edicoes": Edicoes({3: "x"})}, {"alterado": True}])
def test_cancelar_sem_versao_com_edicao_fica_em_erro(muda: dict[str, object]) -> None:
    na_fila = replace(novo_corte(0, CANDS[0], "f7"), **muda)
    c = cancelar(na_fila)
    assert c is not None and c.status == "erro" and c.erro == "render cancelado"
    assert c.edicoes == na_fila.edicoes and c.versao == 0


def test_cancelar_recusa_quem_ja_comecou() -> None:
    with pytest.raises(ErroProducao, match="já começou"):
        cancelar(iniciar(novo_corte(0, CANDS[0], "f7")))


@pytest.mark.parametrize("status", ["pronto", "erro"])
def test_cancelar_so_quem_esta_na_fila(status: str) -> None:
    c = iniciar(novo_corte(0, CANDS[0], "f7"))
    c = concluir(c) if status == "pronto" else falhar(c, "x") if status == "erro" else c
    with pytest.raises(ErroProducao, match="só dá para cancelar"):
        cancelar(c)


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


def test_cancelar_renderizar_de_novo_volta_ao_formato_da_versao_pronta() -> None:
    pronto = concluir(iniciar(novo_corte(0, CANDS[0], "f7")))
    assert pronto.formato_pronto == "f7"
    c = cancelar(reenfileirar(pronto, "f1"))
    assert c is not None and c.formato == "f7" and c.formato_pronto == "f7"


def test_formato_pronto_vai_e_volta_do_disco(tmp_path: Path) -> None:
    c = reenfileirar(concluir(iniciar(novo_corte(1, CANDS[1], "f7"))), "f1")
    gravar_corte(pasta_corte(tmp_path, 1), c)
    assert ler_corte(pasta_corte(tmp_path, 1)) == c


@pytest.mark.parametrize(("versao", "status", "esperado"), [(0, "na_fila", None), (2, "pronto", "f7")])
def test_corte_sem_formato_pronto_migra(tmp_path: Path, versao: int, status: str,
                                        esperado: str | None) -> None:
    d = pasta_corte(tmp_path, 0)
    d.mkdir(parents=True)
    x = {"indice": 0, "inicio": 10.0, "fim": 40.0, "formato": "f7", "titulo": "A", "status": status,
         "versao": versao, "erro": None}
    (d / "corte.json").write_text(json.dumps(x), encoding="utf-8")
    assert ler_corte(d).formato_pronto == esperado


@pytest.mark.parametrize(("versao", "status", "formato_pronto"), [(0, "na_fila", "f7"), (1, "pronto", None),
                                                                  (1, "pronto", 7)])
def test_formato_pronto_incoerente_e_erro(tmp_path: Path, versao: int, status: str,
                                          formato_pronto: object) -> None:
    d = pasta_corte(tmp_path, 0)
    d.mkdir(parents=True)
    x = {"indice": 0, "inicio": 10.0, "fim": 40.0, "formato": "f7", "titulo": "A", "status": status,
         "versao": versao, "erro": None, "formato_pronto": formato_pronto}
    (d / "corte.json").write_text(json.dumps(x), encoding="utf-8")
    with pytest.raises(ErroProducao, match="formato_pronto"):
        ler_corte(d)


def test_cortes_do_episodio_ignora_corte_apagado_depois_do_glob(tmp_path: Path,
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    import cortes.render.corte as modulo
    for i in (0, 2):
        gravar_corte(pasta_corte(tmp_path, i), novo_corte(i, CANDS[i], "f7"))
    real = modulo.ler_corte

    def ler_depois_de_cancelar(d: Path) -> Corte:
        if d.name == "0":
            (d / "corte.json").unlink()   # o cancelar apagou entre o glob e a leitura
        return real(d)

    monkeypatch.setattr(modulo, "ler_corte", ler_depois_de_cancelar)
    assert [c.indice for c in cortes_do_episodio(tmp_path)] == [2]


def test_trilha_da_edicao_vai_e_volta_do_disco(tmp_path: Path) -> None:
    d = tmp_path / "0"
    c = replace(novo_corte(0, {"inicio": 1.0, "fim": 5.0, "titulo": "T"}, "f7"),
                edicoes=Edicoes(trilha="B"))
    gravar_corte(d, c)
    assert ler_corte(d).edicoes.trilha == "B"


def test_corte_antigo_sem_trilha_e_automatico(tmp_path: Path) -> None:
    d = tmp_path / "0"
    gravar_corte(d, novo_corte(0, {"inicio": 1.0, "fim": 5.0, "titulo": "T"}, "f7"))
    x = json.loads((d / "corte.json").read_text(encoding="utf-8"))
    del x["edicoes"]["trilha"]
    (d / "corte.json").write_text(json.dumps(x), encoding="utf-8")
    assert ler_corte(d).edicoes.trilha is None


def test_trilha_de_tipo_errado_e_erro(tmp_path: Path) -> None:
    d = tmp_path / "0"
    gravar_corte(d, novo_corte(0, {"inicio": 1.0, "fim": 5.0, "titulo": "T"}, "f7"))
    x = json.loads((d / "corte.json").read_text(encoding="utf-8"))
    x["edicoes"]["trilha"] = 3
    (d / "corte.json").write_text(json.dumps(x), encoding="utf-8")
    with pytest.raises(ErroProducao, match="trilha"):
        ler_corte(d)
