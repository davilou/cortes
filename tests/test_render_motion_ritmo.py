from cortes.render.motion_params import Chat
from cortes.render.motion_ritmo import Bruta, ritmo, trocas_por_10s

P = Chat("APP", "pergunta")


def _b(ini: float, fim: float, comp: str = "chat") -> Bruta:   # chat é div; valor_cheio, cheio
    return Bruta(comp, ini, fim, P, ())


def test_tira_o_que_cai_no_gancho_e_o_que_nao_deixa_o_rosto_voltar() -> None:
    v = "valor_cheio"
    cenas = [_b(0.5, 2.5), _b(3.0, 5.0, v), _b(5.5, 7.5, v), _b(6.5, 9.0, v), _b(9.0, 11.0, v)]
    ficam, fora = ritmo(cenas, 40)
    # a de 3,0 s é aparada para o rosto voltar antes da de 5,5 s; a de 6,5 s não cabe
    assert [(b.inicio, b.fim) for b in ficam] == [(3.0, 4.5), (5.5, 7.5), (9.0, 11.0)]
    assert [d.motivo.split(" (")[0] for d in fora] == [
        "ritmo: começa no gancho", "ritmo: sobrepõe a cena valor_cheio"]


def test_capa_so_uma_e_conta_para_o_rosto() -> None:
    v = "valor_cheio"
    ficam, fora = ritmo([_b(0.0, 2.2, "capa"), _b(0.0, 2.2, "capa"), _b(2.8, 4.8, v), _b(3.5, 6.0, v)], 40)
    assert [(b.componente, b.inicio) for b in ficam] == [("capa", 0.0), (v, 3.5)]
    assert [d.motivo.split(" (")[0] for d in fora] == [
        "ritmo: só uma capa, no gancho", "ritmo: menos de 1.0 s de rosto entre capa"]


def test_curta_no_fim_da_fala_sai() -> None:
    ficam, fora = ritmo([_b(18.0, 19.0)], 19.0)
    assert ficam == [] and fora[0].motivo.startswith("ritmo: só 1.0 s")


def test_passou_de_70_por_cento_saem_as_ultimas() -> None:
    cenas = [_b(1.0, 5.0), _b(6.0, 10.0), _b(11.0, 15.0)]   # 12 s de 16 s = 75%
    ficam, fora = ritmo(cenas, 16.0)
    assert len(ficam) == 2 and fora[0].inicio == 11.0 and "70%" in fora[0].motivo


def test_div_cola_no_vizinho_mas_cheio_atras_de_cheio_precisa_de_rosto() -> None:
    # manual: chat (div) até 11,6 e a comparação "PERDI DINHEIRO" (cheio) logo em seguida
    ficam, fora = ritmo([_b(9.0, 11.6), _b(11.6, 13.2, "comparacao"), _b(13.5, 15.5, "valor_cheio")], 40)
    assert [(b.componente, b.inicio) for b in ficam] == [("chat", 9.0), ("comparacao", 11.6)]
    assert fora[0].motivo.startswith("ritmo: menos de 1.0 s de rosto")


def test_cenas_nao_se_sobrepoem() -> None:
    ficam, fora = ritmo([_b(3.0, 5.0), _b(4.0, 6.0)], 40)
    assert len(ficam) == 1 and fora[0].motivo.startswith("ritmo: sobrepõe")


def test_fixas_ficam_e_a_nova_confere_os_dois_vizinhos() -> None:
    fixas = [_b(3.0, 5.0, "valor_cheio"), _b(9.0, 11.0, "comparacao")]
    ficam, fora = ritmo([_b(5.5, 8.5, "valor_cheio"), _b(6.0, 8.0)], 40, fixas)
    assert [(b.componente, b.inicio) for b in ficam] == [
        ("valor_cheio", 3.0), ("chat", 6.0), ("comparacao", 9.0)]
    assert [d.componente for d in fora] == ["valor_cheio"]


def test_passou_de_70_por_cento_saem_as_novas_nunca_as_fixas() -> None:
    fixas = [_b(10.0, 14.0)]
    ficam, fora = ritmo([_b(1.0, 5.0), _b(5.0, 9.0)], 16.0, fixas)
    assert _b(10.0, 14.0) in ficam and len(fora) == 1


def test_o_ritmo_deixa_passar_do_alvo_de_trocas() -> None:
    # pesquisa 03: alvo 0,6–0,8 trocas de plano por 10 s; uma cena a cada ~5 s dá bem mais
    cenas = [_b(0.0, 2.2, "capa"), *(_b(3.0 + 5 * k, 5.5 + 5 * k) for k in range(5))]
    ficam, fora = ritmo(cenas, 30.0)
    assert fora == [] and trocas_por_10s(ficam, 30.0) >= 0.8


def test_trocas_contam_entrada_e_saida_e_colagem_vale_uma() -> None:
    cenas = [_b(0.0, 2.2, "capa"), _b(3.0, 5.0), _b(5.0, 7.0, "comparacao"), _b(9.0, 20.0)]
    # capa sai (1), chat entra (1), chat → comparação (1), comparação sai (1), chat entra (1);
    # a última vai até o fim do Short e não sai
    assert trocas_por_10s(cenas, 20.0) == 2.5


def test_cena_que_invade_a_seguinte_e_aparada_se_ainda_dura_o_minimo() -> None:
    # teste cego: valor cheio 4,12–8,00 e o chat em 7,64 — o chat saía; agora o valor acaba em 7,64
    valor = Bruta("valor_cheio", 4.12, 8.0, P, (5.5, 7.9))
    ficam, fora = ritmo([valor, _b(7.64, 11.12)], 40)
    assert [(b.componente, b.inicio, b.fim) for b in ficam] == [
        ("valor_cheio", 4.12, 7.64), ("chat", 7.64, 11.12)] and fora == []
    assert ficam[0].batidas == (5.5, 7.24)   # a batida não entra depois do fim, com folga para ler


def test_aparar_entre_dois_cheios_deixa_o_segundo_de_rosto() -> None:
    ficam, _ = ritmo([_b(3.0, 7.0, "valor_cheio"), _b(6.0, 8.0, "comparacao")], 40)
    assert [(b.inicio, b.fim) for b in ficam] == [(3.0, 5.0), (6.0, 8.0)]


def test_nao_apara_abaixo_do_minimo_nem_a_capa_nem_as_fixas() -> None:
    ficam, fora = ritmo([_b(3.0, 6.0), _b(4.0, 6.0)], 40)
    assert [(b.inicio, b.fim) for b in ficam] == [(3.0, 6.0)] and len(fora) == 1
    ficam, fora = ritmo([_b(0.0, 2.2, "capa"), _b(2.0, 4.0)], 40)
    assert [b.componente for b in ficam] == ["capa"] and len(fora) == 1
    ficam, fora = ritmo([_b(7.0, 9.0)], 40, [_b(3.0, 8.0)])
    assert [(b.inicio, b.fim) for b in ficam] == [(3.0, 8.0)] and len(fora) == 1


def test_nova_que_invade_uma_fixa_seguinte_e_encurtada() -> None:
    # render real (Uber): a lista da 2ª chamada invadia o valor cheio aceito na 1ª e saía
    lista = Bruta("lista", 11.49, 15.49, P, (12.0, 15.2))
    valor = _b(15.23, 17.39, "valor_cheio")
    ficam, fora = ritmo([lista], 27.0, [valor])
    assert [(b.componente, b.inicio, b.fim) for b in ficam] == [
        ("lista", 11.49, 15.23), ("valor_cheio", 15.23, 17.39)] and fora == []
    assert ficam[0].batidas == (12.0, 14.83)


def test_sobreposicao_nomeia_a_cena_que_ja_estava() -> None:
    _, fora = ritmo([_b(14.5, 17.0)], 27.0, [_b(15.5, 18.0, "valor_cheio")])
    assert fora[0].motivo.startswith("ritmo: sobrepõe a cena valor_cheio (15.50")
