from typing import Any

import pytest

from cortes.render.motion_params import (
    Capa,
    Coluna,
    Comparacao,
    Contador,
    ErroParams,
    Lista,
    Rota,
    ValorCheio,
    batidas,
    formatar,
    ler_params,
    params_json,
    textos_da_tela,
)

CONTADOR = {"rotulo": "PAGOU", "valor": 400, "prefixo": "R$", "sufixo": "mil", "marcos": ["ANO 0", "ANO 10"]}
COMPARACAO = {"colunas": [{"rotulo": "IMÓVEL", "valor_texto": "R$ 550 mil", "altura_rel": 0.6},
                          {"rotulo": "RENDA FIXA", "valor_texto": "mais", "altura_rel": 1}],
              "carimbo": "PERDI DINHEIRO"}


def test_le_cada_componente_tipado() -> None:
    assert ler_params("contador", CONTADOR) == Contador("PAGOU", 400.0, "R$", "mil", ("ANO 0", "ANO 10"))
    assert ler_params("capa", {"rotulo": "MAURÍCIO", "titulo": "Ele perdeu dinheiro, com um apê",
                               "destaque": "dinheiro"}) == Capa("MAURÍCIO", "Ele perdeu dinheiro, com um apê",
                                                                "dinheiro")
    c = ler_params("comparacao", COMPARACAO)
    assert isinstance(c, Comparacao) and c.colunas[1] == Coluna("RENDA FIXA", "mais", 1.0)
    assert ler_params("lista", {"titulo": "Pra comprar:", "itens": ["Oportunidade", "Localização"]}) == \
        Lista("Pra comprar:", ("Oportunidade", "Localização"))
    assert ler_params("rota", {"origem": "Rio", "destino": "Saquarema"}) == Rota("Rio", "Saquarema")


@pytest.mark.parametrize("componente, d, erro", [
    ("contador", {**CONTADOR, "valor": "400"}, "'valor' deveria ser número"),
    ("contador", {**CONTADOR, "valor": True}, "'valor' deveria ser número"),
    ("contador", {**CONTADOR, "rotulo": "  "}, "'rotulo' deveria ser texto não vazio"),
    ("contador", {**CONTADOR, "marcos": ["ANO 0"]}, "'marcos' deveria ser lista de 2 a 2"),
    ("chat", {"app": "CHATGPT", "pergunta": "x" * 91}, "'pergunta' com 91 caracteres"),
    ("lista", {"titulo": "T", "itens": ["a"]}, "'itens' deveria ser lista de 2 a 4"),
    ("lista", {"titulo": "T", "itens": ["a", "b", "c", "d", "e"]}, "'itens' deveria ser lista de 2 a 4"),
    ("capa", {"rotulo": "R", "titulo": "Ele perdeu", "destaque": "ganhou"}, "não é uma palavra do título"),
    ("valor_cheio", {"rotulo": "R", "valor": 400, "de": 550}, "'de' (550.0) deveria ser menor"),
    ("comparacao", {"colunas": [COMPARACAO["colunas"][0], {"rotulo": "x", "valor_texto": "y",
                                                           "altura_rel": 0}]}, "'altura_rel'"),
    ("grafico", {}, "componente 'grafico' não existe"),
    ("rota", ["Rio"], "parâmetros deveriam ser objeto"),
])
def test_parametro_invalido_diz_o_motivo(componente: str, d: Any, erro: str) -> None:
    with pytest.raises(ErroParams, match=erro.replace("(", r"\(").replace(")", r"\)")):
        ler_params(componente, d)


def test_volta_do_json_e_igual() -> None:
    for comp, d in (("contador", CONTADOR), ("comparacao", COMPARACAO)):
        p = ler_params(comp, d)
        assert ler_params(comp, params_json(p)) == p


def test_textos_da_tela_tem_o_valor_formatado() -> None:
    assert textos_da_tela(ler_params("contador", CONTADOR)) == ["PAGOU", "R$ 400 mil", "ANO 0", "ANO 10"]
    v = ValorCheio("VALIA", 550, 400, "R$", "mil", "+37,5%")
    assert textos_da_tela(v) == ["VALIA", "R$ 550 mil", "R$ 400 mil", "+37,5%"]
    assert formatar(1500) == "1.500" and formatar(37.5) == "37,5" and formatar(3.25) == "3,25"


def test_batidas_entram_quando_ditas() -> None:
    assert batidas(Lista("T", ("Oportunidade", "Localização"))) == ["Oportunidade", "Localização"]
    assert batidas(Rota("Rio", "Saquarema", "sem saco")) == ["Saquarema", "sem saco"]
    assert batidas(ler_params("contador", CONTADOR)) == ["ANO 10"]
