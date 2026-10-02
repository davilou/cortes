"""Rosto por amostra de um trecho, ciente de troca de câmera.

Roda no Python do ComfyUI (tem cv2 e onnxruntime); o app chama por subprocesso
(src/cortes/render/rosto.py). Portado de testes/comum/rosto.py.

Uso: <python com onnxruntime> rosto.py <trecho.mp4> <modelo.onnx> <saida.json>
Grava {"largura", "altura", "pontos": [{"t", "x", "y", "corte"}]} em pixels da fonte;
corte=true no primeiro ponto depois de uma troca de câmera. Rosto em menos da metade das
amostras → sai com código 1 e a causa no stderr (trilha não confiável).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

LIMIAR = 0.6
PASSO_S = 0.25
CENA = 0.15   # scene > 0,15 = troca de câmera (testes/TEMPLATES.md)
_MEAN = -np.array([0.485, 0.456, 0.406], np.float32) / np.array([0.229, 0.224, 0.225], np.float32)
_STD = 1.0 / (np.array([0.229, 0.224, 0.225], np.float32) * 255.0)


def detectar(frame: np.ndarray, sessao: ort.InferenceSession) -> tuple[float, float] | None:
    im = cv2.resize(frame, (224, 224), interpolation=cv2.INTER_LINEAR)[:, :, ::-1] * _STD + _MEAN
    saida, maxpool = sessao.run([], {"input": np.transpose(im[None].astype(np.float32), (0, 3, 1, 2))})
    mapa = np.where(saida[0, 0] == maxpool[0, 0], saida[0, 0], 0)
    k = int(np.argmax(mapa))
    if mapa.flat[k] < LIMIAR:
        return None
    y, x = divmod(k, 56)
    return x * 4 * frame.shape[1] / 224, y * 4 * frame.shape[0] / 224


def cortes_de_camera(video: Path) -> list[float]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf",
                        f"scale=320:-1,select='gt(scene,{CENA})',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True, errors="replace")
    return [float(t) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def amostrar(video: Path, sessao: ort.InferenceSession, cortes: list[float]) -> tuple[int, int, list[dict], int]:
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    largura, altura = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    tempos = sorted({round(k * PASSO_S, 3) for k in range(int(dur / PASSO_S))} | {round(c + 0.05, 3) for c in cortes})
    pontos: list[dict] = []
    ultimo: int | None = None
    for t in tempos:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, frame = cap.read()
        if not ok or (r := detectar(frame, sessao)) is None:
            continue
        n = sum(1 for c in cortes if c <= t)
        pontos.append({"t": round(t, 2), "x": round(r[0]), "y": round(r[1]), "corte": ultimo is not None and n != ultimo})
        ultimo = n
    return largura, altura, pontos, len(tempos)


def main() -> None:
    trecho, modelo, saida = (Path(a) for a in sys.argv[1:4])
    sessao = ort.InferenceSession(str(modelo), providers=["CPUExecutionProvider"])
    largura, altura, pontos, n = amostrar(trecho, sessao, cortes_de_camera(trecho))
    if len(pontos) < 0.5 * n:
        sys.exit(f"rosto em só {len(pontos)} de {n} amostras — trilha não confiável")
    saida.write_text(json.dumps({"largura": largura, "altura": altura, "pontos": pontos}), encoding="utf-8")
    print(f"rosto em {len(pontos)}/{n} amostras; {sum(p['corte'] for p in pontos)} trocas de câmera")


if __name__ == "__main__":
    main()
