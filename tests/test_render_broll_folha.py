"""Folha mista do f4: momentos de vídeo com 3 quadros (`D<k>-V<j>m<p>`) e fotos (`D<k>-F<j>`), sem
ffmpeg de verdade."""
from pathlib import Path

import pytest

from cortes.render.broll_folha import LinhaFolha, dividir_folhas, folha_args, gerar_folha
from cortes.render.ilustracao import Deixa
from cortes.render.processo import ErroRender

DEIXA = Deixa(2.0, 3.5, "tênis", "tênis Vans Old Skool", "literal")
EVENTO = Deixa(5.0, 6.5, "pandemia", "empty city street lockdown", "acontecimento")


def _q(nome: str) -> tuple[Path, Path, Path]:
    return (Path(f"{nome}-q1.jpg"), Path(f"{nome}-q2.jpg"), Path(f"{nome}-q3.jpg"))


def _v(nome: str, n: int = 2) -> tuple[tuple[Path, Path, Path], ...]:
    """Os n momentos de um vídeo."""
    return tuple(_q(f"{nome}-m{p}") for p in range(1, n + 1))


def _grafo(args: list[str]) -> str:
    return args[args.index("-filter_complex") + 1]


def test_bloco_da_deixa_tem_uma_linha_por_video_e_uma_de_fotos() -> None:
    linhas = [LinhaFolha(1, DEIXA, (_v("v1"), _v("v2")), (Path("f1.jpg"),)),
              LinhaFolha(2, EVENTO, ()),
              LinhaFolha(3, EVENTO, (_v("w1", 1),))]
    args = folha_args(linhas, Path("folha.jpg"))
    entradas = [args[i + 1] for i, a in enumerate(args) if a == "-i"]
    assert entradas == [*map(str, _v("v1")[0] + _v("v1")[1] + _v("v2")[0] + _v("v2")[1]), "f1.jpg",
                        *map(str, _v("w1", 1)[0])]
    grafo = _grafo(args)
    for rotulo in ("D1-V1m1", "D1-V1m2", "D1-V2m1", "D1-V2m2", "D1-F1", "D3-V1m1"):
        assert f"text='{rotulo}'" in grafo
    assert "D2-" not in grafo   # deixa sem candidato não entra
    # momento: 3 quadros 9:16 de 120 px (360); foto: quadrado de 300; rótulo numa faixa de 40 px
    assert "hstack=inputs=3" in grafo and "pad=360:253:0:40:white" in grafo
    assert "pad=300:340:0:40:white" in grafo
    # V1 em y=0, V2 em 253, fotos em 506; o bloco seguinte depois de 846 + 24 de espaço
    assert "layout=0_0|376_0|0_253|376_253|0_506|0_870:fill=white" in grafo
    assert args[-1] == "folha.jpg" and "arial.ttf" in grafo and "boxcolor" not in grafo


def test_quadros_de_cada_momento_usam_as_proprias_entradas() -> None:
    args = folha_args([LinhaFolha(1, DEIXA, (_v("a", 1),), (Path("f.jpg"),))], Path("x.jpg"))
    grafo = _grafo(args)
    assert "[0:v]scale=116:213" in grafo and "[2:v]scale=116:213" in grafo
    assert "[3:v]scale=300:300" in grafo   # a foto é a 4ª entrada


def test_rotulos_da_linha_com_video_e_momento() -> None:
    ln = LinhaFolha(1, DEIXA, (_v("a", 2), _v("b", 1)), (Path("f"),))
    assert ln.rotulos() == ["V1m1", "V1m2", "V2m1", "F1"]
    assert LinhaFolha(1, EVENTO, ()).rotulos() == []


def test_dividir_folhas_de_2_em_2_deixas_com_candidato() -> None:
    linhas = [LinhaFolha(k, DEIXA, (_v(str(k)),) if k != 3 else ()) for k in range(1, 7)]
    folhas = dividir_folhas(linhas)
    assert [[ln.k for ln in f] for f in folhas] == [[1, 2], [4, 5], [6]]
    assert dividir_folhas([LinhaFolha(1, DEIXA, ())]) == []


def test_folha_de_uma_foto_so_nao_usa_xstack() -> None:
    grafo = _grafo(folha_args([LinhaFolha(4, DEIXA, (), (Path("a.jpg"),))], Path("f.jpg")))
    assert "xstack" not in grafo and "text='D4-F1'" in grafo


def test_folha_sem_candidato_nenhum_e_erro() -> None:
    with pytest.raises(ErroRender, match="nenhum candidato"):
        folha_args([LinhaFolha(1, DEIXA, ())], Path("f.jpg"))


def test_gerar_folha_confere_o_arquivo(tmp_path: Path) -> None:
    linhas = [LinhaFolha(1, DEIXA, (_v("a"),))]
    with pytest.raises(ErroRender, match="não gerou"):
        gerar_folha(linhas, tmp_path / "folha.jpg", lambda a, c: (0, ""))

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        Path(args[-1]).write_bytes(b"jpg")
        return 0, ""

    gerar_folha(linhas, tmp_path / "folha.jpg", rodar)
    assert (tmp_path / "folha.jpg").exists() and not (tmp_path / "folha.parcial.jpg").exists()
