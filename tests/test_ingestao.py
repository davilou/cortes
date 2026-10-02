import subprocess
import sys
from pathlib import Path

import pytest

from cortes import ingestao
from cortes.ingestao import (
    ALTURA_MINIMA,
    ErroIngestao,
    altura_de_saida,
    comando_download,
    extrair_meta,
    precisa_cliente_alternativo,
    validar_altura,
)


def test_comando_padrao_pede_1080_e_info_json(tmp_path: Path) -> None:
    cmd = comando_download("https://youtu.be/x", tmp_path, cliente=None)
    assert cmd[:3] == [sys.executable, "-m", "yt_dlp"]
    assert "--write-info-json" in cmd and "--extractor-args" not in cmd
    assert "height<=1080" in cmd[cmd.index("-f") + 1]
    assert cmd[cmd.index("--remux-video") + 1] == "mp4"
    assert cmd[-1] == "https://youtu.be/x"


def test_altura_de_saida_converte_stdout() -> None:
    assert altura_de_saida("1080\n", Path("v.mp4")) == 1080


def test_altura_de_saida_vazia_levanta_erro_claro() -> None:
    with pytest.raises(ErroIngestao, match="não retornou altura"):
        altura_de_saida("", Path("v.mp4"))


def test_comando_com_cliente_alternativo(tmp_path: Path) -> None:
    cmd = comando_download("u", tmp_path, cliente="android_vr")
    assert cmd[cmd.index("--extractor-args") + 1] == "youtube:player_client=android_vr"


@pytest.mark.parametrize("stderr,esperado", [
    ("ERROR: [youtube] abc: Requested format is not available. Use --list-formats", True),
    ("WARNING: Only images are available for download", True),
    ("ERROR: Sign in to confirm you're not a bot", False),
    ("", False),
])
def test_precisa_cliente_alternativo(stderr: str, esperado: bool) -> None:
    assert precisa_cliente_alternativo(stderr) is esperado


def test_validar_altura_recusa_baixa_resolucao() -> None:
    validar_altura(ALTURA_MINIMA)
    with pytest.raises(ErroIngestao, match="360"):
        validar_altura(360)


def test_extrair_meta() -> None:
    info = {"title": "Ep 1", "channel": "Podcast", "duration": 3600, "upload_date": "20260901",
            "id": "abc", "outros": "ignorado"}
    assert extrair_meta(info) == {"titulo": "Ep 1", "canal": "Podcast", "duracao_s": 3600,
                                  "data": "20260901", "id": "abc"}


def test_extrair_audio_grava_atomico_so_audio_wav_fica(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_sucesso(args: list[str]) -> subprocess.CompletedProcess[str]:
        Path(args[-1]).write_bytes(b"audio")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(ingestao, "_rodar", fake_sucesso)
    ingestao.extrair_audio(tmp_path)
    assert (tmp_path / "audio.wav").exists()
    assert not (tmp_path / "audio.tmp.wav").exists()


def test_extrair_audio_falha_nao_deixa_audio_wav(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_falha(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, "", "ffmpeg explodiu")

    monkeypatch.setattr(ingestao, "_rodar", fake_falha)
    with pytest.raises(ErroIngestao, match="ffmpeg"):
        ingestao.extrair_audio(tmp_path)
    assert not (tmp_path / "audio.wav").exists()


def test_baixar_altura_rejeitada_remove_video_e_info_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[0] == "ffprobe":
            return subprocess.CompletedProcess(args, 0, "360\n", "")
        (tmp_path / "video.mp4").write_bytes(b"x")
        (tmp_path / "video.info.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(ingestao, "_rodar", fake)
    with pytest.raises(ErroIngestao, match="360"):
        ingestao.baixar("u", tmp_path)
    assert not (tmp_path / "video.mp4").exists()
    assert not (tmp_path / "video.info.json").exists()
    assert not (tmp_path / "meta.json").exists()
