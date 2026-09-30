import jsonschema
import pytest

from cortes.detector.prompt import MAX_EXEMPLOS, formatar_transcricao, montar_prompt, schema_candidatos
from cortes.perfil import CRITERIOS, Perfil
from cortes.tipos import Frase

PERFIL = Perfil("financas", "É sobre dinheiro.", dict.fromkeys(CRITERIOS, 0.2),
                {"humor": "o trecho faz rir"}, {"palestra_ou_palco": "gravado em palco"},
                25, 75, [{"texto": "bom", "motivo": "espanto"}], [])
FRASES = [Frase(0, "Eu avisei.", 0.0, 1.2), Frase(1, "Ele bateu o carro.", 65.5, 67.04)]


def test_formatar_transcricao_numera_e_marca_inicio_e_fim_em_segundos() -> None:
    assert formatar_transcricao(FRASES) == "[F0 0.0-1.2s] Eu avisei.\n[F1 65.5-67.0s] Ele bateu o carro."


def test_prompt_traz_tema_criterios_tags_descritas_e_exemplos() -> None:
    txt = montar_prompt(FRASES, PERFIL)
    for trecho in ["É sobre dinheiro.", "gancho_3s", "- humor: o trecho faz rir",
                   "- palestra_ou_palco: gravado em palco", "bom", "[F1 65.5-67.0s] Ele bateu o carro.",
                   "SOBRE O TEMA", "do início ao fim", "abre_com", "não podem se sobrepor",
                   "frase_inicio é a PRIMEIRA e frase_fim é a ÚLTIMA frase incluída no corte"]:
        assert trecho in txt


def test_prompt_traz_duracao_do_perfil() -> None:
    txt = montar_prompt(FRASES, PERFIL)
    linha = next(li for li in txt.splitlines() if "duração = fim da frase_fim" in li)
    assert "25" in linha and "75" in linha


def test_transcricao_vem_antes_da_tarefa() -> None:
    txt = montar_prompt(FRASES, PERFIL)
    assert txt.startswith("TRANSCRIÇÃO:")
    assert txt.index("[F0 0.0-1.2s]") < txt.index("TAREFA")


def test_tags_vazias_aparecem_como_nenhuma() -> None:
    vazio = Perfil("f", "t", dict.fromkeys(CRITERIOS, 0.2), {}, {}, 20, 90, [], [])
    assert "(nenhuma)" in montar_prompt(FRASES, vazio)


def test_espanto_nao_repete_numero_nem_virada() -> None:
    linha = next(li for li in montar_prompt(FRASES, PERFIL).splitlines() if li.startswith("- espanto:"))
    assert "número" not in linha and "virada" not in linha


def test_usa_os_exemplos_mais_recentes() -> None:
    exemplos = [{"texto": f"ex{i:02d}"} for i in range(MAX_EXEMPLOS + 3)]
    p = Perfil("f", "t", dict.fromkeys(CRITERIOS, 0.2), {}, {}, 20, 90, exemplos, [])
    txt = montar_prompt(FRASES, p)
    assert "ex00" not in txt and "ex02" not in txt
    assert "ex03" in txt and f"ex{MAX_EXEMPLOS + 2:02d}" in txt


def _item_ok() -> dict:  # type: ignore[type-arg]
    return {"frase_inicio": 0, "frase_fim": 1, "abre_com": "Eu avisei", "justificativa": "x",
            "dentro_do_tema": True, "notas": dict.fromkeys(CRITERIOS, 3), "bonus": ["humor"],
            "penalidades": [], "titulo": "y"}


def test_schema_aceita_resposta_valida_e_recusa_bonus_fora_da_lista() -> None:
    schema = schema_candidatos(PERFIL)
    ok = {"candidatos": [_item_ok()]}
    jsonschema.validate(ok, schema)
    ok["candidatos"][0]["bonus"] = ["inventado"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(ok, schema)


def test_schema_exige_abre_com_e_pede_justificativa_antes_das_notas() -> None:
    schema = schema_candidatos(PERFIL)
    item = schema["properties"]["candidatos"]["items"]
    for ordem in (list(item["properties"]), item["required"]):
        assert ordem.index("justificativa") < ordem.index("dentro_do_tema") < ordem.index("notas")
    sem = _item_ok()
    del sem["abre_com"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"candidatos": [sem]}, schema)


def test_lista_vazia_gera_schema_valido() -> None:
    vazio = Perfil("f", "t", dict.fromkeys(CRITERIOS, 0.2), {}, {}, 20, 90, [], [])
    jsonschema.Draft202012Validator.check_schema(schema_candidatos(vazio))
