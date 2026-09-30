"""Baixa o episódio (yt-dlp), extrai o áudio (ffmpeg) e grava meta.json.

O YouTube às vezes só entrega miniaturas ao cliente padrão; o cliente android_vr destrava,
mas pode vir em baixa resolução — por isso a altura final é validada (qualidade > economia).
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from cortes.episodio import salvar_json

FORMATO = "bv*[height<=1080]+ba/b[height<=1080]"
ALTURA_MINIMA = 720
CLIENTE_ALTERNATIVO = "android_vr"


class ErroIngestao(RuntimeError):
    pass


def comando_download(url: str, destino: Path, cliente: str | None) -> list[str]:
    args = [sys.executable, "-m", "yt_dlp", "-f", FORMATO, "--merge-output-format", "mp4",
            "--write-info-json", "--no-progress", "--sleep-requests", "1.5",
            "-o", str(destino / "video.%(ext)s")]
    if cliente:
        args += ["--extractor-args", f"youtube:player_client={cliente}"]
    return args + [url]


def precisa_cliente_alternativo(stderr: str) -> bool:
    return "Requested format is not available" in stderr or "Only images are available" in stderr


def validar_altura(altura: int) -> None:
    if altura < ALTURA_MINIMA:
        raise ErroIngestao(f"só há vídeo em {altura}p (mínimo {ALTURA_MINIMA}p); tente mais tarde")


def extrair_meta(info: dict[str, Any]) -> dict[str, Any]:
    return {"titulo": info["title"], "canal": info["channel"], "duracao_s": info["duration"],
            "data": info["upload_date"], "id": info["id"]}


def _rodar(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _altura(video: Path) -> int:
    r = _rodar(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                "stream=height", "-of", "csv=p=0", str(video)])
    if r.returncode != 0:
        raise ErroIngestao(f"ffprobe falhou em {video}: {r.stderr[-300:]}")
    return int(r.stdout.strip())


def baixar(url: str, destino: Path) -> None:
    r = _rodar(comando_download(url, destino, cliente=None))
    if r.returncode != 0 and precisa_cliente_alternativo(r.stderr):
        r = _rodar(comando_download(url, destino, cliente=CLIENTE_ALTERNATIVO))
    if r.returncode != 0:
        raise ErroIngestao(f"yt-dlp falhou: {r.stderr[-500:]}")
    video = destino / "video.mp4"
    validar_altura(_altura(video))
    info = json.loads((destino / "video.info.json").read_text(encoding="utf-8"))
    salvar_json(destino / "meta.json", extrair_meta(info))


def extrair_audio(destino: Path) -> None:
    r = _rodar(["ffmpeg", "-y", "-v", "error", "-i", str(destino / "video.mp4"),
                "-ac", "1", "-ar", "16000", str(destino / "audio.wav")])
    if r.returncode != 0:
        raise ErroIngestao(f"ffmpeg falhou ao extrair áudio: {r.stderr[-300:]}")
