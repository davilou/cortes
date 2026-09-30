import jsonschema
import pytest

from cortes.detector.prompt import formatar_transcricao, montar_prompt, schema_candidatos
from cortes.perfil import CRITERIOS, Perfil
from cortes.tipos import Frase

PERFIL = Perfil("financas", "É sobre dinheiro.", dict.fromkeys(CRITERIOS, 0.2), ["humor"],
                ["palestra_ou_palco"], 20, 90, [{"texto": "bom", "motivo": "espanto"}], [])
FRASES = [Frase(0, "Eu avisei.", 0.0, 1.2), Frase(1, "Ele bateu o carro.", 65.5, 67.0)]


def test_formatar_transcricao_numera_e_marca_tempo() -> None:
    assert formatar_transcricao(FRASES) == "[F0 00:00] Eu avisei.\n[F1 01:05] Ele bateu o carro."


def test_prompt_traz_tema_criterios_bonus_exemplos_e_transcricao() -> None:
    txt = montar_prompt(FRASES, PERFIL)
    for trecho in ["É sobre dinheiro.", "gancho_3s", "humor", "palestra_ou_palco", "bom",
                   "[F1 01:05] Ele bateu o carro.", "20", "90"]:
        assert trecho in txt


def test_schema_aceita_resposta_valida_e_recusa_bonus_fora_da_lista() -> None:
    schema = schema_candidatos(PERFIL)
    ok = {"candidatos": [{"frase_inicio": 0, "frase_fim": 1, "notas": dict.fromkeys(CRITERIOS, 3),
                          "dentro_do_tema": True, "bonus": ["humor"], "penalidades": [],
                          "justificativa": "x", "titulo": "y"}]}
    jsonschema.validate(ok, schema)
    ok["candidatos"][0]["bonus"] = ["inventado"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(ok, schema)


def test_lista_vazia_gera_schema_valido() -> None:
    vazio = Perfil("f", "t", dict.fromkeys(CRITERIOS, 0.2), [], [], 20, 90, [], [])
    jsonschema.Draft202012Validator.check_schema(schema_candidatos(vazio))
