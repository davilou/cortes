"""O que o ffmpeg tira do vídeo do B-roll (f4): momentos, trecho escolhido, quadros e foto cheia."""
from pathlib import Path

import pytest

from cortes.render.broll_quadros import (
    MOMENTOS,
    TRECHO_S,
    args_cheio,
    args_foto_cheia,
    cortar_momento,
    extrair_momentos,
    extrair_quadros,
    foto_cheia,
    inicios_momentos,
    quadros_args,
)
from cortes.render.ilustracao import DUR_MAX_S
from cortes.render.processo import ErroRender
from tests.test_render_broll_video import Rodar


def _ss(args: list[str]) -> list[str]:
    return [args[i + 1] for i, a in enumerate(args) if a == "-ss"]


def test_trecho_cobre_o_clipe_mais_longo() -> None:
    assert TRECHO_S == DUR_MAX_S == 4.0


def test_quatro_momentos_espalhados_sem_passar_do_fim() -> None:
    assert MOMENTOS == (0.15, 0.35, 0.55, 0.75)
    assert inicios_momentos(100.0) == (15.0, 35.0, 55.0, 75.0)
    # 15 s: o último começaria em 11,25 e acabaria em 15,25; vai para 15 - 4 - 0,3
    assert inicios_momentos(15.0) == (2.25, 5.25, 8.25, 10.7)


def test_args_tela_cheia_cortam_4s_do_momento_em_cover_sem_audio() -> None:
    args = args_cheio(Path("b.mp4"), Path("d.mp4"), 33.5)
    vf = args[args.index("-vf") + 1]
    assert "scale=1080:1920:force_original_aspect_ratio=increase" in vf and "crop=1080:1920" in vf
    assert "-an" in args and args[args.index("-t") + 1] == "4.000"
    assert _ss(args) == ["33.500"] and args.index("-ss") < args.index("-i")


def test_cortar_momento_grava_por_parcial(tmp_path: Path) -> None:
    cortar_momento(tmp_path / "b.mp4", 10.0, tmp_path / "D1-v1.mp4", Rodar())
    assert [p.name for p in tmp_path.iterdir()] == ["D1-v1.mp4"]
    with pytest.raises(ErroRender, match="tela cheia de b.mp4 em 10.0 s"):
        cortar_momento(tmp_path / "b.mp4", 10.0, tmp_path / "D1-v2.mp4", Rodar((1, "Invalid data")))
    assert not (tmp_path / "D1-v2.mp4").exists()


def test_quadros_em_cover_9_16_num_ffmpeg_so() -> None:
    ds = (Path("q1.jpg"), Path("q2.jpg"), Path("q3.jpg"))
    args = quadros_args(Path("t.mp4"), (0.1, 2.0, 3.8), ds)
    assert _ss(args) == ["0.10", "2.00", "3.80"]
    assert [args[i + 1] for i, a in enumerate(args) if a == "-map"] == ["0:v", "1:v", "2:v"]
    assert "crop=360:640" in args[args.index("-vf") + 1] and args[-1] == "q3.jpg"
    # sem encoder com threads de quadro (ff_frame_thread_encoder_init) e JPEG em faixa cheia
    assert args.count("-threads") == 3 and args[args.index("-threads") + 1] == "1"
    assert args[args.index("-vf") + 1].endswith("format=yuvj420p")


def test_extrair_quadros_do_trecho_inicio_meio_e_fim(tmp_path: Path) -> None:
    rodar = Rodar()
    qs = extrair_quadros(tmp_path / "t.mp4", tmp_path / "D1-v1", rodar)
    assert [q.name for q in qs] == ["D1-v1-q1.jpg", "D1-v1-q2.jpg", "D1-v1-q3.jpg"]
    assert _ss(rodar.chamadas[0]) == ["0.10", "2.00", "3.80"]


def test_extrair_momentos_tira_3_quadros_de_cada_um_ffmpeg_por_momento(tmp_path: Path) -> None:
    # real (2026-10-03, bota): um ffmpeg só com 12 entradas de 1080p e 12 saídas JPEG falhou em 2 de 8
    # vídeos com "ff_frame_thread_encoder_init failed" em parte das saídas; 3 por vez é o que já rodava
    rodar = Rodar()
    ms = extrair_momentos(tmp_path / "D1-v1.bruto.mp4", (15.0, 35.0), tmp_path / "D1-v1", rodar)
    assert [[q.name for q in m] for m in ms] == [
        ["D1-v1-m1-q1.jpg", "D1-v1-m1-q2.jpg", "D1-v1-m1-q3.jpg"],
        ["D1-v1-m2-q1.jpg", "D1-v1-m2-q2.jpg", "D1-v1-m2-q3.jpg"]]
    assert [_ss(a) for a in rodar.chamadas] == [["15.10", "17.00", "18.80"], ["35.10", "37.00", "38.80"]]


def test_quadro_que_nao_saiu_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="não gerou D1-v1-m1-q1.jpg"):
        extrair_momentos(tmp_path / "b.mp4", (1.0,), tmp_path / "D1-v1", Rodar(cria=False))


def test_foto_cheia_contain_sobre_ela_mesma_desfocada() -> None:
    args = args_foto_cheia(Path("f.jpg"), Path("d.jpg"))
    grafo = args[args.index("-filter_complex") + 1]
    assert "force_original_aspect_ratio=increase,crop=1080:1920,boxblur" in grafo
    assert "force_original_aspect_ratio=decrease[frente]" in grafo and "overlay=(W-w)/2:(H-h)/2" in grafo
    assert args[-1] == "d.jpg" and args.count("f.jpg") == 2


def test_foto_cheia_grava_por_parcial(tmp_path: Path) -> None:
    foto_cheia(tmp_path / "f.jpg", tmp_path / "broll-1.jpg", Rodar())
    assert [p.name for p in tmp_path.iterdir()] == ["broll-1.jpg"]
    with pytest.raises(ErroRender, match="tela cheia"):
        foto_cheia(tmp_path / "f.jpg", tmp_path / "broll-2.jpg", Rodar((1, "erro")))
    assert not (tmp_path / "broll-2.jpg").exists()
