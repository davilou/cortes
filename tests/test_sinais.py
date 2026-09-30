import numpy as np
import pytest

from cortes.sinais import energia_por_janela


def test_energia_rms_por_janela() -> None:
    taxa = 100  # janela de 0,5 s = 50 amostras
    silencio = np.zeros(50, dtype=np.float32)
    alto = np.full(50, 0.5, dtype=np.float32)
    sobra = np.ones(10, dtype=np.float32)  # incompleta: descartada
    e = energia_por_janela(np.concatenate([silencio, alto, sobra]), taxa=taxa)
    assert e == [0.0, 0.5]


def test_audio_curto_demais_levanta() -> None:
    with pytest.raises(ValueError, match="mais curto"):
        energia_por_janela(np.zeros(10, dtype=np.float32), taxa=100)
