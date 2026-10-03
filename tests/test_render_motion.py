from typing import Any

import jsonschema
import pytest

from cortes.llm import ErroLLM
from cortes.render.motion import cenas_do_corte, prompt_cenas
from cortes.render.motion_params import Contador, Lista
from cortes.render.motion_prompt import SCHEMA_CENAS
from cortes.render.processo import ErroRender
from cortes.tipos import Palavra

FALA = ("Eu falei, porra, eu tive um apartamento no Rio de Janeiro também que eu comprei, assim, "
        "sei lá, por 400 mil reais, passou 10 anos, tava valendo 550, sabe assim? Aí você coloca "
        "no chat GPT, fala, quanto que renderia isso na renda fixa? Você fala, merda, perdi um dinheiro. "
        "Pra comprar e vender imóvel você tem que ter uma noção de oportunidade. Você tem que ter uma "
        "noção de localização.").split()
PALAVRAS = [Palavra(t, round(0.4 * i, 2), round(0.4 * i + 0.35, 2)) for i, t in enumerate(FALA)]
DUR = round(0.4 * len(FALA), 2)   # 28,4 s


def _i(texto: str) -> int:
    return next(i for i, w in enumerate(FALA) if w.startswith(texto))


def _cena(comp: str, ini: int, fim: int, **params: Any) -> dict[str, Any]:
    return {"componente": comp, "inicio_palavra": ini, "fim_palavra": fim, "params": params}


def _chamar(*cenas: dict[str, Any]) -> Any:
    def chamar(prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
        resposta = {"cenas": list(cenas)}
        jsonschema.validate(resposta, schema)
        return resposta
    return chamar


def test_prompt_numera_as_palavras_e_cita_as_regras() -> None:
    p = prompt_cenas(PALAVRAS)
    assert "[0] (0.0s) Eu" in p and "[19] 400" in p and '"contador"' in p and "de 40% a 70%" in p


def test_cenas_validas_com_tempo_das_palavras_e_batidas_na_fala() -> None:
    r = cenas_do_corte(PALAVRAS, DUR, _chamar(
        _cena("capa", 0, 3, rotulo="MAURÍCIO", titulo="Ele perdeu dinheiro com um apê", destaque="dinheiro"),
        _cena("contador", _i("400"), _i("anos"), rotulo="PAGOU", valor=400, prefixo="R$", sufixo="mil",
              marcos=["ANO 0", "ANO 10"]),
        _cena("lista", _i("oportunidade"), _i("localiza"), titulo="Pra comprar imóvel:",
              itens=["Oportunidade", "Localização"]),
    ))
    assert [c.componente for c in r.cenas] == ["capa", "contador", "lista"] and r.descartadas == []
    capa, cont, lista = r.cenas
    assert (capa.k, capa.inicio, capa.fim) == (1, 0.0, 2.2)
    assert cont.inicio == PALAVRAS[_i("400")].inicio and cont.params == Contador(
        "PAGOU", 400.0, "R$", "mil", ("ANO 0", "ANO 10"))
    assert cont.batidas == (PALAVRAS[_i("10")].inicio,)   # a barra enche no "10 anos"
    assert isinstance(lista.params, Lista)
    # "localização" é dita a 0,35 s do fim da fala: entra a FOLGA_FIM_S do fim, para dar para ler
    assert lista.batidas == (PALAVRAS[_i("oportunidade")].inicio, round(lista.fim - 0.4, 2))
    assert lista.fim - lista.inicio <= 4.0


def test_numero_nao_dito_descarta_a_cena_com_o_motivo() -> None:
    r = cenas_do_corte(PALAVRAS, DUR, _chamar(
        _cena("valor_cheio", _i("valendo"), _i("assim?"), rotulo="VALIA", valor=550, de=400, prefixo="R$",
              sufixo="mil", selo="+37,5%"),
    ))
    assert r.cenas == []
    (d,) = r.descartadas
    assert d.componente == "valor_cheio" and d.motivo == "número que a fala não disse: +37,5%"


def test_numero_dito_depois_da_cena_nao_vale() -> None:
    r = cenas_do_corte(PALAVRAS, DUR, _chamar(
        _cena("contador", _i("falei"), _i("tive"), rotulo="VALE", valor=550, sufixo="mil")))
    assert r.cenas == [] and "550 mil" in r.descartadas[0].motivo


def test_parametro_invalido_descarta_com_o_motivo() -> None:
    r = cenas_do_corte(PALAVRAS, DUR, _chamar(_cena("chat", _i("chat"), _i("fixa?"), app="CHATGPT")))
    assert r.cenas == [] and r.descartadas[0].motivo.startswith("parâmetro inválido: 'pergunta'")


def test_indice_invalido_e_erro_do_llm() -> None:
    with pytest.raises(ErroLLM, match="palavras 3 a 999 inválidas"):
        cenas_do_corte(PALAVRAS, DUR, _chamar(_cena("chat", 3, 999, app="X", pergunta="Y")))


def test_sem_palavras_ou_duracao_e_erro() -> None:
    with pytest.raises(ErroRender, match="sem palavras"):
        cenas_do_corte([], DUR, _chamar())
    with pytest.raises(ErroRender, match="duração"):
        cenas_do_corte(PALAVRAS, 0, _chamar())


def test_schema_aceita_so_componente_conhecido() -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"cenas": [_cena("grafico", 0, 1)]}, SCHEMA_CENAS)
