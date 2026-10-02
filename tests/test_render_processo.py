from pathlib import Path

import pytest

from cortes.render.processo import ErroRender, exigir


def test_exigir_devolve_a_saida() -> None:
    assert exigir(lambda a, c: (0, "tudo certo"), ["x"], None, "teste") == "tudo certo"


def test_exigir_falha_alto_com_o_fim_do_log() -> None:
    log = "a" * 5000 + "causa real"

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        return 2, log

    with pytest.raises(ErroRender, match=r"recorte falhou \(código 2\).*causa real") as ex:
        exigir(rodar, ["ffmpeg"], None, "recorte")
    assert len(str(ex.value)) < 1700
