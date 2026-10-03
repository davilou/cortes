import json
from pathlib import Path
from typing import Any

import pytest

from cortes.llm import ErroLLM, chamar
from cortes.render.ilustracao import Deixa
from cortes.render.ilustracao_conferencia import (
    SCHEMA_CONFERENCIA,
    SISTEMA_CONFERENCIA,
    Escolha,
    conferir,
    prompt_conferencia,
)
from cortes.render.ilustracao_imagens import LinhaFolha

FOLHA = Path("C:/tmp/ilus/folha.jpg")
LINHAS = [LinhaFolha(1, Deixa(2.0, 3.5, "tênis", "tênis Vans Old Skool"), (Path("a"), Path("b"))),
          LinhaFolha(2, Deixa(6.0, 7.5, "camisa", "camisa do Corinthians"), (Path("c"),)),
          LinhaFolha(3, Deixa(9.0, 10.5, "bota", "bota de couro"), ())]


def _chamar_que_devolve(escolhas: list[dict[str, Any]]):  # type: ignore[no-untyped-def]
    chamadas: list[tuple[str, dict[str, Any], str, str, Path]] = []

    def chamar(prompt: str, schema: dict[str, Any], sistema: str, modelo: str, pasta: Path) -> dict[str, Any]:
        chamadas.append((prompt, schema, sistema, modelo, pasta))
        return {"escolhas": escolhas}

    chamar.chamadas = chamadas  # type: ignore[attr-defined]
    return chamar


def _e(k: int, img: int | None, motivo: str = "ok") -> dict[str, Any]:
    return {"deixa": k, "imagem": img, "motivo": motivo}


def test_prompt_cita_a_folha_e_so_as_deixas_com_candidata() -> None:
    p = prompt_conferencia(FOLHA, LINHAS)
    assert str(FOLHA) in p
    assert "D1" in p and "tênis Vans Old Skool" in p and "D1-1 a D1-2" in p
    assert "D2-1" in p and "D3" not in p


def test_conferir_devolve_a_escolha_de_cada_deixa_e_libera_a_pasta_da_folha() -> None:
    chamar = _chamar_que_devolve([_e(2, None, "é uma camisa do Palmeiras"), _e(1, 2)])
    assert conferir(FOLHA, LINHAS, chamar) == {
        1: Escolha(1, 2, "ok"), 2: Escolha(2, None, "é uma camisa do Palmeiras")}
    _, schema, sistema, _, pasta = chamar.chamadas[0]
    assert schema is SCHEMA_CONFERENCIA and sistema == SISTEMA_CONFERENCIA and pasta == FOLHA.parent


def test_deixa_ausente_da_resposta_fica_sem_imagem_com_o_motivo() -> None:
    escolhas = conferir(FOLHA, LINHAS, _chamar_que_devolve([_e(1, 1)]))
    assert escolhas[2].imagem is None and "não respondeu" in escolhas[2].motivo


@pytest.mark.parametrize("escolha,causa", [
    (_e(2, 2), "D2-2"),            # D2 só tem uma candidata
    (_e(1, 0), "D1-0"),
    (_e(3, 1), "deixa 3"),         # D3 não está na folha
    (_e(9, None), "deixa 9"),
])
def test_conferir_recusa_imagem_ou_deixa_inexistente(escolha: dict[str, Any], causa: str) -> None:
    with pytest.raises(ErroLLM, match=causa):
        conferir(FOLHA, LINHAS, _chamar_que_devolve([escolha]))


def test_conferir_recusa_deixa_repetida() -> None:
    with pytest.raises(ErroLLM, match="deixa 1.*duas vezes"):
        conferir(FOLHA, LINHAS, _chamar_que_devolve([_e(1, 1), _e(1, 2)]))


def test_schema_recusa_motivo_so_com_espaco() -> None:
    saida = json.dumps({"is_error": False, "structured_output": {"escolhas": [_e(1, 1, "   ")]}})
    with pytest.raises(ErroLLM, match="fora do schema"):
        chamar("p", SCHEMA_CONFERENCIA, SISTEMA_CONFERENCIA, executar=lambda a, e: saida)
