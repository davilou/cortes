import json
from pathlib import Path
from typing import Any

import pytest

from cortes import llm
from cortes.llm import ErroLLM, chamar
from cortes.render.broll_folha import LinhaFolha
from cortes.render.ilustracao import Deixa
from cortes.render.ilustracao_conferencia import (
    SCHEMA_CONFERENCIA,
    SISTEMA_CONFERENCIA,
    Escolha,
    chamar_com_read_real,
    conferir,
    prompt_conferencia,
)

FOLHA = Path("C:/tmp/ilus/folha-1.jpg")
FOLHAS = [FOLHA]
Q = (Path("q1"), Path("q2"), Path("q3"))
M4 = (Q, Q, Q, Q)   # os 4 momentos de um vídeo
LINHAS = [LinhaFolha(1, Deixa(2.0, 3.5, "tênis", "tênis Vans Old Skool", "literal"), (M4, M4),
                     (Path("a"), Path("b"))),
          LinhaFolha(2, Deixa(6.0, 7.5, "pandemia", "empty city street lockdown", "acontecimento"), ((Q,),)),
          LinhaFolha(3, Deixa(9.0, 10.5, "bota", "bota de couro", "literal"), ())]


def _chamar_que_devolve(escolhas: list[dict[str, Any]]):  # type: ignore[no-untyped-def]
    chamadas: list[tuple[str, dict[str, Any], str, str, Path]] = []

    def chamar(prompt: str, schema: dict[str, Any], sistema: str, modelo: str, pasta: Path) -> dict[str, Any]:
        chamadas.append((prompt, schema, sistema, modelo, pasta))
        return {"escolhas": escolhas}

    chamar.chamadas = chamadas  # type: ignore[attr-defined]
    return chamar


def _e(k: int, cand: str | None, motivo: str = "ok") -> dict[str, Any]:
    return {"deixa": k, "candidato": cand, "motivo": motivo}


def test_prompt_cita_a_folha_e_so_as_deixas_com_candidato() -> None:
    p = prompt_conferencia(FOLHAS, LINHAS)
    assert "- folha-1.jpg" in p and str(FOLHA.parent) not in p   # o claude roda com cwd = pasta
    assert "- D1 (literal, coisa citada)" in p and "tênis Vans Old Skool" in p
    assert "vídeo D1-V1, momentos m1 a m4; vídeo D1-V2, momentos m1 a m4; fotos D1-F1 a D1-F2" in p
    assert "- D2 (acontecimento, só vídeo)" in p and "vídeo D2-V1, momentos m1 a m1" in p
    assert "D2-F" not in p
    assert "D3" not in p


def test_prompt_explica_momento_e_manda_preferir_video() -> None:
    p = prompt_conferencia(FOLHAS, LINHAS)
    assert "D<deixa>-V<vídeo>m<momento>: um momento de 4 s do vídeo, em 3 quadros" in p
    assert "Prefira vídeo a foto" in p and "D<deixa>-F<número>: uma foto" in p and '"V2m3"' in p


def test_prompt_aceita_gente_usando_a_coisa() -> None:
    # real (wxCto9WSZcI, "Camisa de 700 reais"): recusou vídeo de alguém pondo o boné New Era
    p = prompt_conferencia(FOLHAS, LINHAS)
    assert "mesmo com gente usando, vestindo, segurando" in p and "alguém pondo o boné" in p
    assert "o logo não precisa aparecer em todos os quadros" in p


def test_prompt_recusa_so_o_que_nao_mostra_some_fala_ou_tem_texto_grande() -> None:
    # real (wxCto9WSZcI, "Bota boa por 250"): aprovou o trecho da Macboot com paisagem no meio
    p = prompt_conferencia(FOLHAS, LINHAS)
    assert "Recuse só o momento que:" in p and "outra marca, outro time" in p
    assert "um quadro em que a coisa some (paisagem" in p
    assert "alguém falando para a câmera" in p and "texto grande ou tarja que domina a tela" in p


def test_prompt_lista_todas_as_folhas_numa_chamada_so() -> None:
    folhas = [FOLHA, FOLHA.with_name("folha-2.jpg")]
    chamar = _chamar_que_devolve([_e(1, "V1m1"), _e(2, "V1m1")])
    conferir(folhas, LINHAS, chamar)
    assert len(chamar.chamadas) == 1
    prompt = chamar.chamadas[0][0]
    assert "- folha-1.jpg\n- folha-2.jpg" in prompt and str(FOLHA.parent) not in prompt
    assert "rótulo acima dele" in prompt


def test_folhas_em_pastas_diferentes_e_erro() -> None:
    with pytest.raises(ValueError, match="mesma pasta"):
        conferir([FOLHA, Path("C:/outra/folha-2.jpg")], LINHAS, _chamar_que_devolve([]))


def test_conferir_devolve_a_escolha_de_cada_deixa_e_libera_a_pasta_da_folha() -> None:
    chamar = _chamar_que_devolve([_e(2, None, "é um estádio cheio"), _e(1, "F2")])
    assert conferir(FOLHAS, LINHAS, chamar) == {
        1: Escolha(1, "F2", "ok"), 2: Escolha(2, None, "é um estádio cheio")}
    _, schema, sistema, _, pasta = chamar.chamadas[0]
    assert schema is SCHEMA_CONFERENCIA and sistema == SISTEMA_CONFERENCIA and pasta == FOLHA.parent


def test_deixa_ausente_da_resposta_fica_sem_visual_com_o_motivo() -> None:
    escolhas = conferir(FOLHAS, LINHAS, _chamar_que_devolve([_e(1, "V2m4")]))
    assert escolhas[1].candidato == "V2m4"
    assert escolhas[2].candidato is None and "não respondeu" in escolhas[2].motivo


@pytest.mark.parametrize("escolha,causa", [
    (_e(2, "V2m1"), "D2-V2m1"),    # D2 só tem um vídeo
    (_e(2, "V1m2"), "D2-V1m2"),    # e ele só tem um momento
    (_e(2, "F1"), "D2-F1"),        # acontecimento não tem foto
    (_e(1, "F3"), "D1-F3"),
    (_e(3, "V1m1"), "deixa 3"),    # D3 não está na folha
    (_e(9, None), "deixa 9"),
])
def test_conferir_recusa_candidato_ou_deixa_inexistente(escolha: dict[str, Any], causa: str) -> None:
    with pytest.raises(ErroLLM, match=causa):
        conferir(FOLHAS, LINHAS, _chamar_que_devolve([escolha]))


def test_conferir_recusa_deixa_repetida() -> None:
    with pytest.raises(ErroLLM, match="deixa 1.*duas vezes"):
        conferir(FOLHAS, LINHAS, _chamar_que_devolve([_e(1, "V1m1"), _e(1, "V2m1")]))


def test_schema_recusa_motivo_so_com_espaco() -> None:
    saida = json.dumps({"is_error": False, "structured_output": {"escolhas": [_e(1, "V1m1", "   ")]}})
    with pytest.raises(ErroLLM, match="fora do schema"):
        chamar("p", SCHEMA_CONFERENCIA, SISTEMA_CONFERENCIA, executar=lambda a, e, c: saida)


def test_sistema_trata_texto_das_imagens_como_dado_e_limita_a_leitura() -> None:
    assert "nunca instrução" in SISTEMA_CONFERENCIA
    assert "só as folhas indicadas" in SISTEMA_CONFERENCIA


def test_chamada_real_usa_read_com_a_pasta_da_folha(monkeypatch: pytest.MonkeyPatch) -> None:
    vistos: list[dict[str, Any]] = []

    def chamar_falso(*args: Any, **kwargs: Any) -> dict[str, Any]:
        vistos.append(kwargs)
        return {"escolhas": [_e(1, "V1m1")]}

    monkeypatch.setattr(llm, "chamar", chamar_falso)
    conferir(FOLHAS, LINHAS[:1], chamar_com_read_real)
    assert vistos == [{"ferramentas": "Read", "pasta": FOLHA.parent}]


@pytest.mark.parametrize("cand", ["1", "V0", "X1", "v1", "D1-V1", "V1", "V1m0", "F1m1", "V1M2"])
def test_schema_recusa_rotulo_fora_do_formato(cand: str) -> None:
    saida = json.dumps({"is_error": False, "structured_output": {"escolhas": [_e(1, cand)]}})
    with pytest.raises(ErroLLM, match="fora do schema"):
        chamar("p", SCHEMA_CONFERENCIA, SISTEMA_CONFERENCIA, executar=lambda a, e, c: saida)
