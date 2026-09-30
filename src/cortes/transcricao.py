"""Whisper large-v3 na GPU, com tempo por palavra."""
from pathlib import Path
from typing import Any

from cortes.tipos import Palavra

MODELO = "large-v3"


def palavras_de_segmentos(segmentos: list[dict[str, Any]]) -> list[Palavra]:
    palavras = [
        Palavra(w["word"].strip(), round(float(w["start"]), 3), round(float(w["end"]), 3))
        for seg in segmentos for w in seg.get("words", []) if w["word"].strip()
    ]
    if not palavras:
        raise ValueError("transcrição sem palavras")
    return palavras


def transcrever(audio: Path, modelo: str = MODELO) -> list[Palavra]:
    import whisper  # import tardio: só carrega torch quando a etapa roda

    m = whisper.load_model(modelo, device="cuda")
    r = m.transcribe(str(audio), language="pt", word_timestamps=True, fp16=True)
    return palavras_de_segmentos(r["segments"])
