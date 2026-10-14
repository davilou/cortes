import pytest

from cortes.render.processo import ErroRender
from cortes.render.trilha import (
    FADE_IN_S,
    SOBREPOSICAO_S,
    Clipe,
    clipes,
    compasso,
    ganho,
    html_trilha,
    ler_ebur128,
)

LOG = """[Parsed_ebur128_0 @ 0x1] t: 0.1  TARGET:-23 LUFS    M:-120.7 S:-120.7     I: -70.0 LUFS
[Parsed_ebur128_0 @ 0x1] t: 89.9  TARGET:-23 LUFS    M: -30.2 S: -30.0     I: -31.4 LUFS
[Parsed_ebur128_0 @ 0x1] Summary:

  Integrated loudness:
    I:         -31.5 LUFS
    Threshold: -41.6 LUFS
"""


def test_ler_ebur128_pega_o_resumo_e_a_duracao() -> None:
    m = ler_ebur128(LOG)
    assert (m.lufs, m.duracao) == (-31.5, 89.9)


def test_ler_ebur128_sem_resumo_e_erro() -> None:
    with pytest.raises(ErroRender, match="ebur128"):
        ler_ebur128("ffmpeg: nada aqui")


def test_ganho_poe_a_cama_18_lu_abaixo_da_voz() -> None:
    # voz −16, cama −30: a cama precisa ir a −34, ou seja −4 dB
    assert ganho(-16.0, -30.0) == pytest.approx(10 ** (-4 / 20))


def test_ganho_nunca_amplifica() -> None:
    assert ganho(-10.0, -40.0) == 1.0


def test_ganho_com_trecho_sem_fala_fica_baixo_e_finito() -> None:
    g = ganho(-70.0, -30.0)   # −58 dB
    assert 0 < g < 0.002


def test_compasso_em_4_por_4() -> None:
    assert compasso(80) == pytest.approx(3.0)


def test_corte_curto_termina_na_barra_da_cama() -> None:
    [c] = clipes(10.0, 90.0, 80)   # compasso de 3 s: o fim cai em 12 s da cama
    assert c == Clipe(0.0, 10.0, 2.0, FADE_IN_S, 3.0)
    assert (c.media_inicio + c.duracao) % compasso(80) == pytest.approx(0.0)


def test_corte_menor_que_dois_compassos_encurta_o_fade() -> None:
    [c] = clipes(4.0, 90.0, 80)
    assert c.fade_out == 2.0


def test_corte_quase_do_tamanho_da_cama_comeca_do_zero() -> None:
    [c] = clipes(89.0, 90.0, 80)   # a barra de 90 s ainda cabe na cama de 90 s
    assert c.media_inicio == pytest.approx(1.0)
    [c] = clipes(89.5, 89.9, 80)   # a barra de 90 s passa do fim da cama: sem alinhar
    assert c.media_inicio == 0.0


def test_corte_mais_longo_que_a_cama_encadeia_com_crossfade() -> None:
    cs = clipes(200.0, 90.0, 80)
    assert [c.inicio for c in cs] == [0.0, 88.0, 176.0]
    assert [c.duracao for c in cs] == [90.0, 90.0, 24.0]
    assert cs[0].fade_in == FADE_IN_S and cs[1].fade_in == SOBREPOSICAO_S
    assert cs[0].fade_out == SOBREPOSICAO_S and cs[-1].fade_out == 3.0
    assert cs[-1].inicio + cs[-1].duracao == 200.0
    assert all(c.duracao > SOBREPOSICAO_S for c in cs)


def test_clipes_recusa_duracao_invalida() -> None:
    with pytest.raises(ErroRender):
        clipes(0.0, 90.0, 80)
    with pytest.raises(ErroRender):
        clipes(10.0, 3.0, 80)


def test_html_trilha_alterna_faixas_e_leva_volume_e_fades() -> None:
    h = html_trilha([Clipe(0.0, 90.0, 0.0, 0.3, 2.0), Clipe(88.0, 24.0, 0.0, 2.0, 3.0)], 0.25)
    assert h.count("<audio") == 2
    assert 'src="assets/trilha.m4a"' in h and 'data-audio-group="trilha"' in h
    assert 'data-track-index="11"' in h and 'data-track-index="12"' in h
    assert 'data-volume="0.25"' in h and 'data-fade-out="3.0"' in h and 'data-start="88.0"' in h


def test_html_trilha_vazia() -> None:
    assert html_trilha([], 0.5) == ""


def test_fonte_mono_mede_como_vai_tocar_no_mp4_estereo() -> None:
    """O MP4 sai estéreo com o mono nos dois canais: +10·log10(2) dB sobre a medida mono
    (achado no teste lento: diferença de 17 dB onde o volume 0,1 deu os 20 dB certos)."""
    mono = "  Stream #0:0[0x1](und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, mono, fltp, 69 kb/s\n"
    estereo = mono.replace("mono", "stereo")
    assert ler_ebur128(mono + LOG).lufs == pytest.approx(-31.5 + 3.0103, abs=1e-3)
    assert ler_ebur128(estereo + LOG).lufs == -31.5
