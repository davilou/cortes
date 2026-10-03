from cortes.render.motion_params import Lista, Rota
from cortes.render.motion_sincronia import ancora, tempos_das_batidas
from cortes.tipos import Palavra

FALA = "noção de oportunidade e de localização ver em saco arema se funciona".split()
P = [Palavra(t, float(i), i + 0.8) for i, t in enumerate(FALA)]


def test_ancora_e_o_numero_ou_a_palavra_mais_longa() -> None:
    assert ancora("ANO 10") == "10" and ancora("sem saco") == "saco"
    assert ancora("Localização") == "localizacao"


def test_batida_entra_na_palavra_que_a_diz() -> None:
    assert tempos_das_batidas(Lista("T", ("Oportunidade", "Localização")), P, 0.0, 8.0) == (2.0, 5.0)


def test_batida_que_a_fala_nao_diz_entra_no_passo_regular() -> None:
    # "Saquarema" foi transcrito "saco arema": o destino entra no passo, o selo na palavra dita
    assert tempos_das_batidas(Rota("Rio", "Saquarema", "sem saco"), P, 6.0, 10.0) == (6.2, 8.0)


def test_batida_nunca_passa_do_fim_menos_a_folga() -> None:
    (t,) = tempos_das_batidas(Rota("Rio", "Localização"), P, 0.0, 5.2)   # dita em 5,0 s
    assert t == 4.8


UBER = [Palavra(t, float(i), i + 0.8) for i, t in enumerate(
    "Tá fazendo Uber à noite. Após o trabalho. Das seis à meia -noite.".split())]


def test_sem_a_palavra_mais_longa_tenta_as_outras() -> None:
    # render real: "MEIA-NOITE" (a mais longa) foi transcrita "meia -noite"; "seis" foi dita
    lista = Lista("ROTINA", ("UBER À NOITE", "APÓS O TRABALHO", "SEIS À MEIA-NOITE"))
    assert tempos_das_batidas(lista, UBER, 0.0, 13.0) == (4.0, 7.0, 9.0)


def test_batida_sem_ancora_entra_depois_da_anterior_nunca_junto() -> None:
    lista = Lista("T", ("Oportunidade", "Xablau", "Zureta"))
    t = tempos_das_batidas(lista, P, 0.0, 8.0)
    assert t[0] == 2.0 and t[0] < t[1] < t[2] <= 7.6
