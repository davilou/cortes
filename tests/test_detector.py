from typing import Any

from cortes.detector import detectar
from cortes.perfil import CRITERIOS, Perfil
from cortes.tipos import Frase

PERFIL = Perfil("f", "dinheiro", dict.fromkeys(CRITERIOS, 0.2), [], [], 20, 90, [], [])
FRASES = [Frase(0, "Quanto ganha um jogador?", 0, 15), Frase(1, "Dez milhões por mês.", 15, 30)]


def test_detectar_passa_prompt_e_schema_ao_llm_e_converte() -> None:
    recebido: dict[str, Any] = {}

    def llm_falso(prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
        recebido.update(prompt=prompt, schema=schema, sistema=sistema, modelo=modelo)
        return {"candidatos": [{"frase_inicio": 0, "frase_fim": 1, "notas": dict.fromkeys(CRITERIOS, 5),
                                "dentro_do_tema": True, "bonus": [], "penalidades": [],
                                "justificativa": "j", "titulo": "t"}]}

    aceitos, descartes = detectar(FRASES, [0.1] * 100, PERFIL, modelo="opus", chamar_llm=llm_falso)
    assert "[F1 00:15] Dez milhões por mês." in recebido["prompt"]
    assert recebido["modelo"] == "opus" and "Ignore" in recebido["sistema"]
    assert len(aceitos) == 1 and aceitos[0].fim == 30 and descartes == []
