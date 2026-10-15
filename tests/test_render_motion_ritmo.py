from cortes.render.motion_params import Chat, Destaque, Ilustracao, Respiro
from cortes.render.motion_ritmo import Bruta, emendar, ritmo, trocas_por_10s

P = Chat("APP", "pergunta")


def _b(ini: float, fim: float, comp: str = "chat") -> Bruta:
    p = Respiro() if comp == "respiro" else Ilustracao("x", "X", "casa") if comp == "ilustracao" else P
    return Bruta(comp, ini, fim, p, ())


def _t(bs: list[Bruta]) -> list[tuple[float, float]]:
    return [(b.inicio, b.fim) for b in bs]


def test_paineis_colados_ficam_e_o_gancho_e_do_rosto() -> None:
    ficam, fora = ritmo([_b(1.0, 3.0), _b(2.0, 4.0), _b(4.0, 7.0), _b(7.0, 9.5)], 40)
    assert _t(ficam) == [(2.0, 4.0), (4.0, 7.0), (7.0, 9.5)]
    assert [d.motivo.split(" (")[0] for d in fora] == ["ritmo: começa no gancho"]


def test_capa_so_uma() -> None:
    ficam, fora = ritmo([_b(0.0, 2.0, "capa"), _b(0.0, 2.0, "capa"), _b(2.0, 4.0)], 40)
    assert [b.componente for b in ficam] == ["capa", "chat"]
    assert [d.motivo for d in fora] == ["ritmo: só uma capa, no gancho"]


def test_sobreposicao_e_aparada_se_ainda_dura_o_minimo() -> None:
    ficam, fora = ritmo([_b(3.0, 7.0), _b(5.5, 8.0)], 40)
    assert _t(ficam) == [(3.0, 5.5), (5.5, 8.0)] and fora == []
    ficam, fora = ritmo([_b(3.0, 5.0), _b(4.0, 6.5)], 40)
    assert _t(ficam) == [(3.0, 5.0)] and fora[0].motivo.startswith("ritmo: sobrepõe a cena chat")


def test_curta_no_fim_da_fala_sai() -> None:
    ficam, fora = ritmo([_b(18.0, 19.0)], 19.0)
    assert ficam == [] and fora[0].motivo.startswith("ritmo: só 1.0 s")


def test_respiro_nem_cedo_nem_colado_nem_terceiro_nem_longo() -> None:
    cenas = [_b(4.0, 5.5, "respiro"), _b(8.0, 10.0, "respiro"), _b(10.0, 12.0, "respiro"),
             _b(15.0, 17.0, "respiro"), _b(20.0, 22.0, "respiro"), _b(25.0, 28.5, "respiro"),
             _b(12.0, 15.0)]
    ficam, fora = ritmo(cenas, 40)
    assert [(b.componente, b.inicio) for b in ficam] == [("respiro", 8.0), ("chat", 12.0), ("respiro", 15.0)]
    assert [d.motivo.split(" (")[0] for d in fora] == [
        "ritmo: respiro antes de 6 s", "ritmo: respiro colado em outro respiro",
        "ritmo: no máximo 2 respiros", "ritmo: respiro de 3.5 s"]


def test_no_maximo_3_ilustracoes() -> None:
    cenas = [_b(2.0 + 3 * k, 4.5 + 3 * k, "ilustracao") for k in range(4)]
    ficam, fora = ritmo(cenas, 40)
    assert len(ficam) == 3 and fora[0].motivo == "ritmo: no máximo 3 ilustrações por Short"


def test_fixas_ficam_e_a_nova_nao_as_apara() -> None:
    fixa = _b(5.0, 8.0)
    ficam, fora = ritmo([_b(3.0, 6.0)], 40, [fixa])
    assert _t(ficam) == [(3.0, 5.0), (5.0, 8.0)] and fora == []


def test_emendar_estica_o_painel_ate_o_seguinte_se_o_vao_e_curto() -> None:
    """O painel anterior fica até o próximo entrar (a entrada continua na palavra); a capa e o
    respiro não esticam; vão de mais de 1 s fica."""
    cenas = [_b(0.0, 2.0, "capa"), _b(2.4, 5.0), _b(5.5, 9.0), _b(12.0, 14.0), _b(15.0, 17.0, "respiro")]
    assert _t(emendar(cenas, 18.0)) == [(0.0, 2.0), (2.4, 5.5), (5.5, 9.0), (12.0, 15.0), (15.0, 17.0)]
    assert _t(emendar([_b(2.0, 5.0)], 5.8)) == [(2.0, 5.8)]


def test_trocas_contam_entrada_e_saida_e_colagem_vale_uma() -> None:
    assert trocas_por_10s([_b(2.0, 4.0), _b(4.0, 6.0)], 20) == 1.5


def test_dois_destaques_seguidos_nao() -> None:
    d = Destaque("frase de opinião", "opinião")
    cenas = [Bruta("destaque", 2.0, 4.5, d, ()), Bruta("destaque", 4.5, 7.0, d, ()), _b(7.0, 9.0),
             Bruta("destaque", 9.0, 11.0, d, ())]
    ficam, fora = ritmo(cenas, 20)
    assert [b.componente for b in ficam] == ["destaque", "chat", "destaque"]
    assert fora[0].motivo.startswith("ritmo: dois destaques seguidos")
