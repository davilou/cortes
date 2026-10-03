import json
from typing import Any

import pytest

from cortes.llm import ErroLLM, chamar
from cortes.render.ilustracao import SCHEMA_DEIXAS, SISTEMA_DEIXAS, Deixa, deixas_do_corte, prompt_deixas
from cortes.render.processo import ErroRender
from cortes.tipos import Palavra


def _palavras(n: int, passo: float = 0.5) -> list[Palavra]:
    """Palavra i vai de i*passo a i*passo + 0,4 s."""
    return [Palavra(f"p{i}", round(i * passo, 3), round(i * passo + 0.4, 3)) for i in range(n)]


def _chamar_que_devolve(deixas: list[dict[str, Any]]):  # type: ignore[no-untyped-def]
    chamadas: list[tuple[str, dict[str, Any], str, str]] = []

    def chamar(prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
        chamadas.append((prompt, schema, sistema, modelo))
        return {"deixas": deixas}

    chamar.chamadas = chamadas  # type: ignore[attr-defined]
    return chamar


def _d(ini: int, fim: int, coisa: str = "tênis", busca: str = "tênis Vans Old Skool") -> dict[str, Any]:
    return {"inicio_palavra": ini, "fim_palavra": fim, "coisa": coisa, "busca": busca}


def test_prompt_numera_as_palavras() -> None:
    p = prompt_deixas([Palavra("comprei", 0.0, 0.3), Palavra("um", 0.3, 0.4), Palavra("Vans", 0.4, 0.8)])
    assert "[0] (0.0s) comprei [1] um [2] Vans" in p   # o tempo vai a cada 10 palavras
    assert "1 s" in p and "3 s" in p   # as regras de tempo vão no texto


def test_schema_limita_a_12_deixas() -> None:
    assert SCHEMA_DEIXAS["properties"]["deixas"]["maxItems"] == 12


def test_indice_vira_tempo_no_trecho() -> None:
    chamar = _chamar_que_devolve([_d(4, 7)])   # p4 começa 2,0; p7 termina 3,9
    assert deixas_do_corte(_palavras(20), chamar) == [Deixa(2.0, 3.9, "tênis", "tênis Vans Old Skool")]
    prompt, schema, sistema, _ = chamar.chamadas[0]
    assert schema is SCHEMA_DEIXAS and sistema == SISTEMA_DEIXAS and "[4] p4" in prompt


def test_deixa_curta_estica_ate_1_2s_e_longa_corta_em_3s() -> None:
    chamar = _chamar_que_devolve([_d(4, 4), _d(12, 19)])   # 2,0-2,4 e 6,0-9,9
    curta, longa = deixas_do_corte(_palavras(30), chamar)
    assert (curta.inicio, curta.fim) == (2.0, 3.2)
    assert (longa.inicio, longa.fim) == (6.0, 9.0)


def test_esticar_nao_passa_do_fim_da_fala_e_descarta_o_que_nao_cabe() -> None:
    chamar = _chamar_que_devolve([_d(9, 9)])   # última palavra: 4,5-4,9; esticar daria 5,7
    assert deixas_do_corte(_palavras(10), chamar) == []


def test_descarta_o_gancho_e_o_que_fica_a_menos_de_3s_da_anterior() -> None:
    chamar = _chamar_que_devolve([_d(10, 11), _d(1, 3), _d(14, 15), _d(16, 17)])
    # p1 começa 0,5 (gancho); p10 em 5,0; p14 em 7,0 (2 s depois); p16 em 8,0 (3 s depois)
    assert [d.inicio for d in deixas_do_corte(_palavras(30), chamar)] == [5.0, 8.0]


def test_ordena_por_inicio() -> None:
    chamar = _chamar_que_devolve([_d(20, 21, "bota"), _d(4, 5, "camisa")])
    assert [d.coisa for d in deixas_do_corte(_palavras(30), chamar)] == ["camisa", "bota"]


@pytest.mark.parametrize("ini,fim", [(5, 30), (-1, 3), (8, 6)])
def test_indice_invalido_e_erro_com_a_causa(ini: int, fim: int) -> None:
    with pytest.raises(ErroLLM, match=f"{ini}.*{fim}"):
        deixas_do_corte(_palavras(20), _chamar_que_devolve([_d(ini, fim)]))


def test_sem_palavras_e_erro_sem_chamar_o_llm() -> None:
    with pytest.raises(ErroRender, match="sem palavras"):
        deixas_do_corte([], _chamar_que_devolve([]))


@pytest.mark.parametrize("campo", ["coisa", "busca"])
def test_schema_recusa_coisa_ou_busca_so_com_espaco(campo: str) -> None:
    item = {**_d(3, 4), campo: "  \n "}
    saida = json.dumps({"is_error": False, "structured_output": {"deixas": [item]}})
    with pytest.raises(ErroLLM, match="fora do schema"):
        chamar("p", SCHEMA_DEIXAS, SISTEMA_DEIXAS, executar=lambda a, e, c: saida)
