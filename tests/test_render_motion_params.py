from typing import Any

import pytest

from cortes.render.motion_params import (
    Capa,
    Check,
    Coluna,
    Comodo,
    Comparacao,
    Contador,
    Destaque,
    ErroParams,
    Fluxo,
    Grade,
    Grafico,
    Ilustracao,
    Lista,
    Passo,
    Planta,
    Ponto,
    Respiro,
    Rota,
    Timer,
    Valor,
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
    ("valor", {"rotulo": "R", "valor": 400, "de": 550}, "'de' (550.0) deveria ser menor"),
    ("comparacao", {"colunas": [COMPARACAO["colunas"][0], {"rotulo": "x", "valor_texto": "y",
                                                           "altura_rel": 0}]}, "'altura_rel'"),
    ("grafico3d", {}, "componente 'grafico3d' não existe"),
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
    v = Valor("VALIA", 550, 400, "R$", "mil", "+37,5%")
    assert textos_da_tela(v) == ["VALIA", "R$ 550 mil", "R$ 400 mil", "+37,5%"]
    assert formatar(1500) == "1.500" and formatar(37.5) == "37,5" and formatar(3.25) == "3,25"


def test_batidas_entram_quando_ditas() -> None:
    assert batidas(Lista("T", ("Oportunidade", "Localização"))) == ["Oportunidade", "Localização"]
    assert batidas(Rota("Rio", "Saquarema", "sem saco")) == ["Saquarema", "sem saco"]
    assert batidas(ler_params("contador", CONTADOR)) == ["ANO 10"]


GRAFICO = {"rotulo": "EFEITO", "pontos": [{"x": "dia 1", "y": 0}, {"x": "dia 3", "y": 80}],
           "ponto_destaque": 1}
FLUXO = {"passos": [{"icone": "microfone", "texto": "você fala"}, {"icone": "lampada", "texto": "a IA"}],
         "ativo": 1}
PLANTA = {"comodos": [{"nome": "Sala", "m2": 30}, {"nome": "Quarto"}], "total_m2": 72}
ILUS = {"descricao": "rosto com os músculos da testa", "rotulo": "TESTA", "icone": "pessoa"}


def test_le_os_componentes_novos() -> None:
    g = ler_params("grafico", GRAFICO)
    assert isinstance(g, Grafico) and g.pontos[1] == Ponto("dia 3", 80.0) and g.ponto_destaque == 1
    f = ler_params("fluxo", FLUXO)
    assert isinstance(f, Fluxo) and f.passos[0] == Passo("microfone", "você fala") and f.ativo == 1
    assert ler_params("timer", {"rotulo": "LUZ", "valor": 8, "unidade": "min"}) == Timer("LUZ", 8, "min")
    assert ler_params("check", {"texto": "A IA faz", "sinal": "sim"}) == Check("A IA faz", "sim")
    d = {"frase": "Conteúdo 2.0", "palavra": "conteúdo"}
    assert ler_params("destaque", d) == Destaque("Conteúdo 2.0", "conteúdo")
    p = ler_params("planta", PLANTA)
    assert isinstance(p, Planta) and p.comodos[1] == Comodo("Quarto", None) and p.total_m2 == 72
    assert ler_params("ilustracao", ILUS) == Ilustracao("rosto com os músculos da testa", "TESTA", "pessoa")
    assert ler_params("respiro", {}) == Respiro()
    assert isinstance(ler_params("grade", {"blocos": FLUXO["passos"]}), Grade)


@pytest.mark.parametrize("componente, d, erro", [
    ("grafico", {**GRAFICO, "pontos": GRAFICO["pontos"][:1]}, "'pontos' deveria ser lista de 2 a 6"),
    ("grafico", {**GRAFICO, "ponto_destaque": 2}, "'ponto_destaque' deveria ser inteiro de 0 a 1"),
    ("fluxo", {**FLUXO, "passos": [{"icone": "unicornio", "texto": "x"}] * 2}, "ícone 'unicornio'"),
    ("fluxo", {**FLUXO, "ativo": True}, "'ativo' deveria ser inteiro"),
    ("timer", {"rotulo": "T", "valor": 8, "unidade": "dias"}, "'unidade' deveria ser um de"),
    ("check", {"texto": "x", "sinal": "talvez"}, "'sinal' deveria ser um de"),
    ("grade", {"blocos": [{"icone": "casa", "texto": "x"}] * 7}, "'blocos' deveria ser lista de 2 a 6"),
    ("destaque", {"frase": "Conteúdo 2.0", "palavra": "vídeo"}, "não está na frase"),
    ("planta", {"comodos": [{"nome": "Sala", "m2": 0}, {"nome": "Q"}]}, "'m2' deveria ser maior que zero"),
    ("ilustracao", {**ILUS, "descricao": "x" * 141}, "'descricao' com 141 caracteres"),
    ("respiro", {"x": 1}, "respiro não tem parâmetros"),
])
def test_componente_novo_invalido_diz_o_motivo(componente: str, d: Any, erro: str) -> None:
    with pytest.raises(ErroParams, match=erro):
        ler_params(componente, d)


def test_textos_e_batidas_dos_novos() -> None:
    assert textos_da_tela(ler_params("grafico", GRAFICO)) == ["EFEITO", "dia 1", "0", "dia 3", "80"]
    assert batidas(ler_params("grafico", GRAFICO)) == ["dia 3"]
    assert textos_da_tela(Timer("LUZ", 8, "min")) == ["LUZ", "8 min"]
    assert textos_da_tela(ler_params("planta", PLANTA)) == ["Sala", "Quarto", "30 m²", "72 m²"]
    assert batidas(ler_params("fluxo", FLUXO)) == ["você fala", "a IA"]
    assert batidas(Destaque("Conteúdo 2.0", "conteúdo")) == ["conteúdo"]
    assert textos_da_tela(Respiro()) == [] and batidas(Respiro()) == []


def test_novos_voltam_do_json_iguais() -> None:
    for comp, d in (("grafico", GRAFICO), ("fluxo", FLUXO), ("planta", PLANTA), ("ilustracao", ILUS)):
        p = ler_params(comp, d)
        assert ler_params(comp, params_json(p)) == p


@pytest.mark.parametrize("unidade, valor", [("s", 90), ("min", 60), ("h", 100)])
def test_timer_so_com_valor_que_aparece_sem_conversao(unidade: str, valor: int) -> None:
    """90 segundos apareceria "01:30": número que ninguém disse (revisão final)."""
    with pytest.raises(ErroParams, match="'valor' deveria ser inteiro de 1 a"):
        ler_params("timer", {"rotulo": "T", "valor": valor, "unidade": unidade})


def test_item_da_lista_cabe_noção_de_oportunidade() -> None:
    # render real: "noção de oportunidade" (21) derrubava a lista inteira
    assert ler_params("lista", {"titulo": "T", "itens": ["noção de oportunidade", "noção de localização"]})


def test_palavra_destacada_cabe_desindustrializando() -> None:
    # render real (Sardinha): a frase-chave com "desindustrializando" (19) era recusada
    d = {"frase": "Um país se desindustrializando", "palavra": "desindustrializando"}
    assert ler_params("destaque", d) == Destaque("Um país se desindustrializando", "desindustrializando")
