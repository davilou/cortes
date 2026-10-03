"""Candidatos do B-roll guardados antes da conferência: ida e volta, arquivo sumido e cache ruim."""
from pathlib import Path

import pytest

from cortes.render.broll_candidatos import Achadas, VideoBaixado
from cortes.render.broll_candidatos_cache import ARQUIVO, gravar_achadas, ler_achadas
from cortes.render.broll_video import VideoCandidato
from cortes.render.ilustracao import Deixa
from cortes.render.ilustracao_cache import Chave
from cortes.render.ilustracao_imagens import Candidata
from cortes.render.processo import ErroRender

CHAVE = Chave(10.0, 20.0, "abc")
D1 = Deixa(1.5, 3.0, "Vans", "tênis Vans", "literal")


def _achadas(pasta: Path) -> Achadas:
    nomes = ["D1-v1.mp4", "D1-v1-q1.jpg", "D1-v1-q2.jpg", "D1-v1-q3.jpg", "D1-c1.jpg"]
    for n in nomes:
        (pasta / n).write_bytes(b"x")
    q1, q2, q3 = (pasta / n for n in nomes[1:4])
    cand = VideoCandidato("abcDEF_12-x", 90.0, "Canal", "Título")
    video = VideoBaixado(cand, pasta / nomes[0], (q1, q2, q3))
    foto = (Candidata("http://img/1.jpg", "http://loja/1", 1000, None), pasta / nomes[4])
    return Achadas([video], [foto], ["foto: 404"], "", False)


def test_ida_e_volta(tmp_path: Path) -> None:
    a = _achadas(tmp_path)
    gravar_achadas(tmp_path, CHAVE, [(1, D1)], {1: a})
    assert ler_achadas(tmp_path, CHAVE, [(1, D1)]) == {1: a}


def test_outra_chave_outra_deixa_ou_arquivo_sumido_nao_vale(tmp_path: Path) -> None:
    gravar_achadas(tmp_path, CHAVE, [(1, D1)], {1: _achadas(tmp_path)})
    assert ler_achadas(tmp_path, Chave(10.0, 21.0, "abc"), [(1, D1)]) == {}
    assert ler_achadas(tmp_path, CHAVE, [(1, Deixa(1.5, 3.0, "Nike", "tênis Nike", "literal"))]) == {}
    (tmp_path / "D1-v1-q2.jpg").unlink()
    assert ler_achadas(tmp_path, CHAVE, [(1, D1)]) == {}


def test_cache_adulterado_e_erro_claro(tmp_path: Path) -> None:
    gravar_achadas(tmp_path, CHAVE, [(1, D1)], {1: _achadas(tmp_path)})
    arq = tmp_path / ARQUIVO
    arq.write_text(arq.read_text(encoding="utf-8").replace('"D1-c1.jpg"', '"../fora.jpg"'), encoding="utf-8")
    with pytest.raises(ErroRender, match="candidatos do B-roll inválidos"):
        ler_achadas(tmp_path, CHAVE, [(1, D1)])
