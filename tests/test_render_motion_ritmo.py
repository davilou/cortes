from cortes.render.motion_params import Chat
from cortes.render.motion_ritmo import Bruta, ritmo

P = Chat("APP", "pergunta")


def _b(ini: float, fim: float, comp: str = "chat") -> Bruta:
    return Bruta(comp, ini, fim, P, ())


def test_tira_o_que_cai_no_gancho_e_o_que_nao_deixa_o_rosto_voltar() -> None:
    ficam, fora = ritmo([_b(0.5, 2.5), _b(3.0, 5.0), _b(5.5, 7.5), _b(6.5, 9.0), _b(9.0, 11.0)], 40)
    assert [(b.inicio, b.fim) for b in ficam] == [(3.0, 5.0), (6.5, 9.0)]
    assert [d.motivo.split(" (")[0] for d in fora] == [
        "ritmo: começa no gancho", "ritmo: menos de 1.0 s de rosto depois da cena anterior",
        "ritmo: menos de 1.0 s de rosto depois da cena anterior"]


def test_capa_so_uma_e_conta_para_o_rosto() -> None:
    ficam, fora = ritmo([_b(0.0, 2.2, "capa"), _b(0.0, 2.2, "capa"), _b(2.8, 4.8), _b(3.5, 6.0)], 40)
    assert [(b.componente, b.inicio) for b in ficam] == [("capa", 0.0), ("chat", 3.5)]
    assert [d.motivo.split(" (")[0] for d in fora] == [
        "ritmo: só uma capa, no gancho", "ritmo: menos de 1.0 s de rosto depois da cena anterior"]


def test_curta_no_fim_da_fala_sai() -> None:
    ficam, fora = ritmo([_b(18.0, 19.0)], 19.0)
    assert ficam == [] and fora[0].motivo.startswith("ritmo: só 1.0 s")


def test_passou_de_70_por_cento_saem_as_ultimas() -> None:
    cenas = [_b(1.0, 5.0), _b(6.0, 10.0), _b(11.0, 15.0)]   # 12 s de 16 s = 75%
    ficam, fora = ritmo(cenas, 16.0)
    assert len(ficam) == 2 and fora[0].inicio == 11.0 and "70%" in fora[0].motivo
