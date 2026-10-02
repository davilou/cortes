import pytest

from cortes.producao.legenda_yt import FIM_MAX_S, ErroLegenda
from cortes.producao.transcricao_colada import (
    FOLGA_BLOCO,
    MINIMO_PALAVRAS,
    S_POR_PALAVRA,
    ErroTranscricao,
    palavras_da_transcricao,
)
from tests.amostras import AMOSTRA


def blocos_curtos(n_palavras: int) -> str:
    """Transcrição válida com n palavras, uma por bloco, a cada 5 s."""
    return "".join(f"{5 * i // 60}:{5 * i % 60:02d}\npalavra{i}\n" for i in range(n_palavras))


def test_amostra_real_vira_palavras_com_tempo() -> None:
    ps = palavras_da_transcricao(AMOSTRA)
    assert ps[0].texto == "Fala" and ps[0].inicio == 10.0
    textos = [p.texto for p in ps]
    i_hoje = textos.index("Hoje")
    assert ps[i_hoje].inicio == 18.0
    assert ps[textos.index("nisso")].inicio == 3603.0          # 1:00:03
    assert ps[textos.index("cuidado")].inicio == 4572.0        # 1:16:12
    assert ps[textos.index("você")].inicio == 8125.0           # 2:15:25
    assert textos[-1] == "galera."


def test_bloco_em_varias_linhas_vira_um_texto_so() -> None:
    textos = [p.texto for p in palavras_da_transcricao(AMOSTRA)]
    i = textos.index("colocar")
    assert textos[i + 1: i + 3] == ["aqui", "quatro"]


def test_marcas_entre_colchetes_e_troca_de_locutor_somem() -> None:
    texto = AMOSTRA.replace("Valeu, galera.", ">> Valeu, galera.")
    textos = [p.texto for p in palavras_da_transcricao(texto)]
    assert not any("[" in t or "]" in t or ">>" in t for t in textos)
    assert "garganta]" not in textos and "risadas" not in " ".join(textos)


def test_palavras_do_bloco_ficam_dentro_do_bloco_e_crescem() -> None:
    ps = palavras_da_transcricao(AMOSTRA)
    primeiro = [p for p in ps if 10.0 <= p.inicio < 18.0]
    assert len(primeiro) == 14                                   # "Fala galera, … hein?"
    assert all(a.inicio < b.inicio for a, b in zip(primeiro, primeiro[1:], strict=False))


def test_invariantes_na_amostra_inteira() -> None:
    ps = palavras_da_transcricao(AMOSTRA)
    assert all(a.inicio <= b.inicio for a, b in zip(ps, ps[1:], strict=False))
    assert all(p.inicio < p.fim <= p.inicio + FIM_MAX_S for p in ps)


def test_ultimo_bloco_dura_numero_de_palavras_vezes_s_por_palavra() -> None:
    ps = palavras_da_transcricao(AMOSTRA)
    ultimo = [p for p in ps if p.inicio >= 8125.0]
    n = len(ultimo)
    assert n == 14
    duracao = 8125.0 + n * S_POR_PALAVRA
    assert ultimo[-1].inicio < duracao and ultimo[1].inicio > 8125.0


def test_bloco_seguido_de_pausa_longa_nao_espalha_as_palavras() -> None:
    texto = "0:00\num dois três\n5:00\n" + "palavra " * 60
    ps = palavras_da_transcricao(texto)
    assert [p.texto for p in ps[:3]] == ["um", "dois", "três"]
    assert all(p.inicio < 2.0 for p in ps[:3])
    assert ps[2].inicio < 3 * S_POR_PALAVRA * FOLGA_BLOCO and ps[2].fim <= ps[2].inicio + FIM_MAX_S
    assert ps[3].inicio == 300.0


def test_bloco_so_de_marcas_entre_dois_blocos_nao_gera_palavras() -> None:
    texto = "0:10\n" + "antes " * 30 + "\n0:40\n[música]\n1:20\n" + "depois " * 30
    ps = palavras_da_transcricao(texto)
    teto_do_primeiro = 10 + 30 * S_POR_PALAVRA * FOLGA_BLOCO
    assert len(ps) == 60 and not any(teto_do_primeiro < p.inicio < 80 for p in ps)
    assert ps[30].texto == "depois" and ps[30].inicio == 80.0


def test_crlf_e_linhas_em_branco_sao_tolerados() -> None:
    com_crlf = AMOSTRA.replace("\n", "\r\n\r\n   ")
    assert palavras_da_transcricao(com_crlf) == palavras_da_transcricao(AMOSTRA)


def test_largura_zero_e_nbsp_sao_tolerados() -> None:
    sujo = AMOSTRA.replace("0:18", "​0:18⁠").replace("Fala galera,", "Fala ‍galera,")
    sujo = "﻿" + sujo.replace("Valeu,", "Va​leu,").replace("tua família", "tua‌ família")
    assert palavras_da_transcricao(sujo) == palavras_da_transcricao(AMOSTRA)


def test_linhas_antes_do_primeiro_tempo_sao_ignoradas() -> None:
    """Título do vídeo ou de capítulo copiado junto com a transcrição."""
    com_titulo = "\nIntrodução\nPrimoCast 536\n" + AMOSTRA
    assert palavras_da_transcricao(com_titulo) == palavras_da_transcricao(AMOSTRA)


def test_tempo_que_nao_cresce_e_erro_com_linha() -> None:
    texto = AMOSTRA.replace("1:16:12", "0:18")
    with pytest.raises(ErroTranscricao, match=r"linha 11: tempo 0:18 não é maior que o anterior \(1:00:03\)"):
        palavras_da_transcricao(texto)


@pytest.mark.parametrize("tempo", ["0:60", "1:60:00", "1:00:75"])
def test_tempo_invalido_e_erro_com_linha(tempo: str) -> None:
    with pytest.raises(ErroTranscricao, match=rf"linha 3: tempo inválido '{tempo}'"):
        palavras_da_transcricao(AMOSTRA.replace("0:18", tempo, 1))


def test_sem_palavras_e_erro() -> None:
    with pytest.raises(ErroTranscricao, match="sem palavras"):
        palavras_da_transcricao("0:01\n[música]\n0:05\n[risadas]\n")


def test_vazia_e_erro() -> None:
    with pytest.raises(ErroTranscricao, match="sem palavras"):
        palavras_da_transcricao("  \r\n ")


def test_texto_sem_nenhum_tempo_e_erro() -> None:
    with pytest.raises(ErroTranscricao, match="sem linhas de tempo"):
        palavras_da_transcricao("Fala galera, tudo beleza pessoal? Bora começar\n")


def test_curta_demais_e_erro() -> None:
    with pytest.raises(ErroTranscricao, match=f"curta demais: 49 palavras \\(mínimo {MINIMO_PALAVRAS}\\)"):
        palavras_da_transcricao(blocos_curtos(49))
    assert len(palavras_da_transcricao(blocos_curtos(50))) == 50


def test_erro_da_transcricao_e_erro_de_legenda() -> None:
    assert issubclass(ErroTranscricao, ErroLegenda)
