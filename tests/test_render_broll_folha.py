"""Folha mista do f4: vídeos com 3 quadros (`D<k>-V<j>`) e fotos (`D<k>-F<j>`), sem ffmpeg de verdade."""
from pathlib import Path

import pytest

from cortes.render.broll_folha import LinhaFolha, dividir_folhas, folha_args, gerar_folha
from cortes.render.ilustracao import Deixa
from cortes.render.processo import ErroRender

DEIXA = Deixa(2.0, 3.5, "tênis", "tênis Vans Old Skool", "literal")
EVENTO = Deixa(5.0, 6.5, "pandemia", "empty city street lockdown", "acontecimento")


def _q(nome: str) -> tuple[Path, Path, Path]:
    return (Path(f"{nome}-q1.jpg"), Path(f"{nome}-q2.jpg"), Path(f"{nome}-q3.jpg"))


def _grafo(args: list[str]) -> str:
    return args[args.index("-filter_complex") + 1]


def test_linha_mista_tem_videos_antes_das_fotos_com_rotulos_v_e_f() -> None:
    linhas = [LinhaFolha(1, DEIXA, (_q("v1"), _q("v2")), (Path("f1.jpg"),)),
              LinhaFolha(2, EVENTO, ()),
              LinhaFolha(3, EVENTO, (_q("w1"),))]
    args = folha_args(linhas, Path("folha.jpg"))
    entradas = [args[i + 1] for i, a in enumerate(args) if a == "-i"]
    assert entradas == [*map(str, _q("v1")), *map(str, _q("v2")), "f1.jpg", *map(str, _q("w1"))]
    grafo = _grafo(args)
    for rotulo in ("D1-V1", "D1-V2", "D1-F1", "D3-V1"):
        assert f"text='{rotulo}'" in grafo
    assert "D2-" not in grafo   # deixa sem candidato não entra
    # vídeo: 3 quadros 9:16 lado a lado (540 px); foto: quadrado de 320; rótulo numa faixa de 48 px
    assert "hstack=inputs=3" in grafo and "pad=540:368:0:48:white" in grafo
    assert "pad=320:368:0:48:white" in grafo
    assert "xstack=inputs=4:layout=0_0|556_0|1112_0|0_368:fill=white" in grafo
    assert args[-1] == "folha.jpg" and "arial.ttf" in grafo and "boxcolor" not in grafo


def test_quadros_de_cada_video_usam_as_proprias_entradas() -> None:
    args = folha_args([LinhaFolha(1, DEIXA, (_q("a"),), (Path("f.jpg"),))], Path("x.jpg"))
    grafo = _grafo(args)
    assert "[0:v]scale=176:320" in grafo and "[2:v]scale=176:320" in grafo
    assert "[3:v]scale=320:320" in grafo   # a foto é a 4ª entrada


def test_rotulos_da_linha() -> None:
    assert LinhaFolha(1, DEIXA, (_q("a"), _q("b")), (Path("f"),)).rotulos() == ["V1", "V2", "F1"]
    assert LinhaFolha(1, EVENTO, ()).rotulos() == []


def test_dividir_folhas_de_4_em_4_deixas_com_candidato() -> None:
    linhas = [LinhaFolha(k, DEIXA, (_q(str(k)),) if k != 3 else ()) for k in range(1, 11)]
    folhas = dividir_folhas(linhas)
    assert [[ln.k for ln in f] for f in folhas] == [[1, 2, 4, 5], [6, 7, 8, 9], [10]]
    assert dividir_folhas([LinhaFolha(1, DEIXA, ())]) == []


def test_folha_de_uma_foto_so_nao_usa_xstack() -> None:
    grafo = _grafo(folha_args([LinhaFolha(4, DEIXA, (), (Path("a.jpg"),))], Path("f.jpg")))
    assert "xstack" not in grafo and "text='D4-F1'" in grafo


def test_folha_sem_candidato_nenhum_e_erro() -> None:
    with pytest.raises(ErroRender, match="nenhum candidato"):
        folha_args([LinhaFolha(1, DEIXA, ())], Path("f.jpg"))


def test_gerar_folha_confere_o_arquivo(tmp_path: Path) -> None:
    linhas = [LinhaFolha(1, DEIXA, (_q("a"),))]
    with pytest.raises(ErroRender, match="não gerou"):
        gerar_folha(linhas, tmp_path / "folha.jpg", lambda a, c: (0, ""))

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        Path(args[-1]).write_bytes(b"jpg")
        return 0, ""

    gerar_folha(linhas, tmp_path / "folha.jpg", rodar)
    assert (tmp_path / "folha.jpg").exists() and not (tmp_path / "folha.parcial.jpg").exists()
