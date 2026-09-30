import pytest

from cortes.tipos import Palavra
from cortes.transcricao import palavras_de_segmentos


def test_achata_segmentos_e_limpa_espacos() -> None:
    segs = [
        {
            "words": [
                {"word": " Eu", "start": 0.0, "end": 0.2},
                {"word": " avisei,", "start": 0.2, "end": 0.61234},
            ]
        },
        {"words": [{"word": " tiozão.", "start": 0.7, "end": 1.1}]},
    ]
    assert palavras_de_segmentos(segs) == [
        Palavra("Eu", 0.0, 0.2),
        Palavra("avisei,", 0.2, 0.612),
        Palavra("tiozão.", 0.7, 1.1),
    ]


def test_descarta_palavra_vazia() -> None:
    segs = [{"words": [{"word": "  ", "start": 0.0, "end": 0.1}, {"word": "oi", "start": 0.1, "end": 0.2}]}]
    assert palavras_de_segmentos(segs) == [Palavra("oi", 0.1, 0.2)]


def test_sem_palavras_levanta() -> None:
    with pytest.raises(ValueError, match="sem palavras"):
        palavras_de_segmentos([{"words": []}])
