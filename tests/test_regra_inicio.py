import pytest

from cortes.regra_inicio import comeca_no_meio


@pytest.mark.parametrize("texto", [
    "Também seguindo aquela... é quase um",          # R1, fundo, 491 views
    "Mas como é que foi família",                     # R1, fundo, 14 views
    "Até chegar na digital.",                          # R1, fundo
    "E o carro do vizinho também.",
    "Só que ninguém fala disso.",
    "Porque o juro lá é outro.",
    "Aí ele pegou e vendeu.",
    "— Mas não é bem assim.",
    "“Mas ninguém fala disso.”",              # aspas curvas da transcrição
])
def test_detecta_continuacao(texto: str) -> None:
    assert comeca_no_meio(texto) is True


@pytest.mark.parametrize("texto", [
    "Nenhuma força aérea do mundo tem capacidade",     # R2, top 1,3 mi
    "Cara, não sei se eu deveria falar",               # R1, top 696 mil
    "Eu avisei, tiozão, não faz isso não",             # exemplo Hype Automotivo
    "Sabe como é que é o financiamento na Europa?",    # R1, top 762 mil
    "Mais de um milhão de pessoas perderam",           # "mais" ≠ "mas"
    "Maria vendeu tudo.",                              # "Ma..." não é "mas"
    "Então, eu vendi a minha casa.",                   # "então" abre história
    "Empresário que quebra duas vezes",                # "E..." dentro da palavra
])
def test_aceita_inicio_autonomo(texto: str) -> None:
    assert comeca_no_meio(texto) is False
