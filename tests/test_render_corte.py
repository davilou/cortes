import json
from pathlib import Path

import pytest

from cortes.producao.estado import ErroProducao
from cortes.render.corte import (
    PLANEJADO,
    Corte,
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


def test_planejar_uma_vez_sem_pisar_no_manual(tmp_path: Path) -> None:
    gravar_corte(pasta_corte(tmp_path, 1), novo_corte(1, CANDS[1], "f1"))   # Renderizar manual antes
    planejar(tmp_path, "f7", 2, CANDS)
    assert [(c.indice, c.formato) for c in cortes_do_episodio(tmp_path)] == [(1, "f1"), (2, "f7")]
    assert (tmp_path / "cortes" / PLANEJADO).exists()
