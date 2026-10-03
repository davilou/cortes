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


def _d(ini: int, fim: int, coisa: str = "tênis", busca: str = "tênis Vans Old Skool",
       tipo: str = "literal") -> dict[str, Any]:
    return {"inicio_palavra": ini, "fim_palavra": fim, "coisa": coisa, "busca": busca, "tipo": tipo}


DUR = 30.0   # longo o bastante para o limite de 60% não pesar, salvo nos testes dele


def test_prompt_numera_as_palavras() -> None:
    p = prompt_deixas([Palavra("comprei", 0.0, 0.3), Palavra("um", 0.3, 0.4), Palavra("Vans", 0.4, 0.8)])
    assert "[0] (0.0s) comprei [1] um [2] Vans" in p   # o tempo vai a cada 10 palavras
    assert "primeiro 1 s" in p and "1.5 a 3 s" in p and "1.5 s de rosto" in p and "60%" in p


def test_prompt_explica_os_dois_tipos_e_a_busca_de_video() -> None:
    p = prompt_deixas([Palavra("pandemia", 0.0, 0.5)])
    assert '"literal"' in p and '"acontecimento"' in p and "rua vazia" in p
    assert "YouTube" in p and "inglês" in p


def test_prompt_nao_remarca_a_mesma_coisa_com_busca_generica() -> None:
    # real (wxCto9WSZcI, "Camisa de 700 reais"): "camiseta", dita da camisa do Corinthians, virou
    # "camisa de time de futebol" e o cartão mostrou a camisa da seleção
    p = prompt_deixas([Palavra("camiseta", 0.0, 0.5)])
    assert "Cada coisa entra uma vez só" in p
    assert '"a camiseta" depois de "camisa do Corinthians"' in p


def test_schema_limita_a_12_deixas_e_exige_o_tipo() -> None:
    item = SCHEMA_DEIXAS["properties"]["deixas"]["items"]
    assert SCHEMA_DEIXAS["properties"]["deixas"]["maxItems"] == 12
    assert "tipo" in item["required"] and item["properties"]["tipo"]["enum"] == ["literal", "acontecimento"]


def test_indice_vira_tempo_no_trecho_com_o_tipo() -> None:
    chamar = _chamar_que_devolve([_d(4, 7, tipo="acontecimento")])   # p4 começa 2,0; p7 termina 3,9
    assert deixas_do_corte(_palavras(20), DUR, chamar) == [
        Deixa(2.0, 3.9, "tênis", "tênis Vans Old Skool", "acontecimento")]
    prompt, schema, sistema, _ = chamar.chamadas[0]
    assert schema is SCHEMA_DEIXAS and sistema == SISTEMA_DEIXAS and "[4] p4" in prompt


def test_tipo_desconhecido_e_erro() -> None:
    with pytest.raises(ErroLLM, match="tipo 'foto'"):
        deixas_do_corte(_palavras(20), DUR, _chamar_que_devolve([_d(4, 7, tipo="foto")]))


def test_deixa_curta_estica_ate_1_5s_e_longa_corta_em_3s() -> None:
    chamar = _chamar_que_devolve([_d(4, 4), _d(12, 19)])   # 2,0-2,4 e 6,0-9,9
    curta, longa = deixas_do_corte(_palavras(30), DUR, chamar)
    assert (curta.inicio, curta.fim) == (2.0, 3.5)
    assert (longa.inicio, longa.fim) == (6.0, 9.0)


def test_esticar_nao_passa_do_fim_da_fala_e_descarta_o_que_nao_cabe() -> None:
    chamar = _chamar_que_devolve([_d(8, 9)])   # 4,0-4,9; esticar daria 5,5, a fala acaba em 4,9
    assert deixas_do_corte(_palavras(10), DUR, chamar) == []


def test_descarta_o_gancho() -> None:
    chamar = _chamar_que_devolve([_d(1, 3), _d(2, 3), _d(10, 11)])   # p1 em 0,5 e p2 em 1,0
    assert [d.inicio for d in deixas_do_corte(_palavras(30), DUR, chamar)] == [1.0, 5.0]


def test_rosto_de_1_5s_entre_o_fim_de_um_clipe_e_o_proximo() -> None:
    # 2,0-3,5; p10 em 5,0 (1,5 s de rosto: fica, até 6,5); p15 em 7,5 (só 1,0 s: sai); p19 em 9,5
    chamar = _chamar_que_devolve([_d(4, 4), _d(10, 10), _d(15, 15), _d(19, 19)])
    assert [(d.inicio, d.fim) for d in deixas_do_corte(_palavras(30), DUR, chamar)] == [
        (2.0, 3.5), (5.0, 6.5), (9.5, 11.0)]


def test_passou_de_60_por_cento_descarta_as_ultimas_sem_cortar_as_do_meio() -> None:
    # três clipes de 2,9 s (8,7 s): num Short de 12 s o teto é 7,2 s e a última sai, sem encurtar nada
    chamar = _chamar_que_devolve([_d(2, 7), _d(11, 16), _d(20, 25)])   # 1,0-3,9; 5,5-8,4; 10,0-12,9
    assert [(d.inicio, d.fim) for d in deixas_do_corte(_palavras(30), 12.0, chamar)] == [
        (1.0, 3.9), (5.5, 8.4)]
    assert len(deixas_do_corte(_palavras(30), 15.0, chamar)) == 3   # teto 9,0 s


def test_ordena_por_inicio() -> None:
    chamar = _chamar_que_devolve([_d(20, 21, "bota"), _d(4, 5, "camisa")])
    assert [d.coisa for d in deixas_do_corte(_palavras(30), DUR, chamar)] == ["camisa", "bota"]


@pytest.mark.parametrize("ini,fim", [(5, 30), (-1, 3), (8, 6)])
def test_indice_invalido_e_erro_com_a_causa(ini: int, fim: int) -> None:
    with pytest.raises(ErroLLM, match=f"{ini}.*{fim}"):
        deixas_do_corte(_palavras(20), DUR, _chamar_que_devolve([_d(ini, fim)]))


def test_sem_palavras_e_erro_sem_chamar_o_llm() -> None:
    with pytest.raises(ErroRender, match="sem palavras"):
        deixas_do_corte([], DUR, _chamar_que_devolve([]))


def test_duracao_invalida_e_erro() -> None:
    with pytest.raises(ErroRender, match="duração"):
        deixas_do_corte(_palavras(5), 0.0, _chamar_que_devolve([]))


@pytest.mark.parametrize("campo", ["coisa", "busca"])
def test_schema_recusa_coisa_ou_busca_so_com_espaco(campo: str) -> None:
    item = {**_d(3, 4), campo: "  \n "}
    saida = json.dumps({"is_error": False, "structured_output": {"deixas": [item]}})
    with pytest.raises(ErroLLM, match="fora do schema"):
        chamar("p", SCHEMA_DEIXAS, SISTEMA_DEIXAS, executar=lambda a, e, c: saida)


def test_schema_recusa_tipo_fora_da_lista() -> None:
    saida = json.dumps({"is_error": False, "structured_output": {"deixas": [_d(3, 4, tipo="foto")]}})
    with pytest.raises(ErroLLM, match="fora do schema"):
        chamar("p", SCHEMA_DEIXAS, SISTEMA_DEIXAS, executar=lambda a, e, c: saida)


def test_prompt_nao_marca_peca_ou_caracteristica_vaga_de_produto() -> None:
    # real (wxCto9WSZcI, "Bota boa por 250, não 600"): "um negócio que evita torção" (peça de uma
    # bota) virou busca vaga e trouxe uma bota de motociclista
    p = prompt_deixas([Palavra("bota", 0.0, 0.5)])
    assert "peça ou característica de um produto" in p
    assert '"negócio que evita torção"' in p and '"sola ultra resistente"' in p
    assert "a coisa inteira, que dá para nomear" in p
