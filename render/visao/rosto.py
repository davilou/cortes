"""Rostos por amostra de um trecho (até 3), cientes de troca de câmera.

Roda no Python do ComfyUI (tem cv2 e onnxruntime); o app chama por subprocesso
(src/cortes/render/rosto.py). Portado de testes/comum/rosto.py.

Uso: <python com onnxruntime> rosto.py <trecho.mp4> <modelo.onnx> <saida.json>
Grava (formato 2):
  {"formato": 2, "largura", "altura", "cortes": [instantes reais das trocas de câmera],
   "amostras": [{"t", "rostos": [{"x", "y", "r", "conf"}]}]}
em pixels da fonte; `r` é o raio do rosto. Até MAX_ROSTOS por amostra, como o `detect_faces` do
OpenSeeFace: os maiores picos do mapa de calor acima do limiar. Rosto em menos da metade das
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


MAX_ROSTOS = 3


def detectar(frame: np.ndarray, sessao: ort.InferenceSession) -> list[dict]:
    altura, largura = frame.shape[:2]
    im = cv2.resize(frame, (224, 224), interpolation=cv2.INTER_LINEAR)[:, :, ::-1] * _STD + _MEAN
    saida, maxpool = sessao.run([], {"input": np.transpose(im[None].astype(np.float32), (0, 3, 1, 2))})
    calor, raio = saida[0, 0], saida[0, 1]
    picos = np.where(calor == maxpool[0, 0], calor, 0)
    rostos: list[dict] = []
    for k in np.argsort(picos.ravel())[::-1][:MAX_ROSTOS]:
        conf = float(picos.flat[k])
        if conf < LIMIAR:
            break
        y, x = divmod(int(k), 56)
        r = float(raio[y, x]) * 112
        rostos.append({"x": round(x * 4 * largura / 224), "y": round(y * 4 * altura / 224),
                       "r": round(r * largura / 224), "conf": round(conf, 3)})
    return rostos


def _cortes_validos(brutos: list[float]) -> list[float]:
    """Arredonda, descarta trocas em t<=0 (ruído do primeiro quadro, não é corte real) e
    deduplica preservando a ordem (o detector de cena do ffmpeg pode marcar o mesmo instante
    mais de uma vez; duplicado vira intervalo de duração zero em `_pontos_por_intervalo`)."""
    vistos: set[float] = set()
    res: list[float] = []
    for t in (round(c, 2) for c in brutos):
        if t > 0 and t not in vistos:
            vistos.add(t)
            res.append(t)
    return res


def cortes_de_camera(video: Path) -> list[float]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf",
                        f"scale=320:-1,select='gt(scene,{CENA})',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        sys.exit(f"ffmpeg (trocas de câmera) falhou: {r.stderr[-1500:]}")
    brutos = [float(t) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]
    return _cortes_validos(brutos)


def amostrar(video: Path, sessao: ort.InferenceSession, cortes: list[float]) -> tuple[int, int, list[dict]]:
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    largura, altura = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    tempos = sorted({round(k * PASSO_S, 3) for k in range(int(dur / PASSO_S))}
                    | {round(c + 0.05, 3) for c in cortes})
    amostras: list[dict] = []
    for t in tempos:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, frame = cap.read()
        amostras.append({"t": round(t, 2), "rostos": detectar(frame, sessao) if ok else []})
    return largura, altura, amostras


def main() -> None:
    trecho, modelo, saida = (Path(a) for a in sys.argv[1:4])
    sessao = ort.InferenceSession(str(modelo), providers=["CPUExecutionProvider"])
    cortes = cortes_de_camera(trecho)
    largura, altura, amostras = amostrar(trecho, sessao, cortes)
    com_rosto = sum(1 for a in amostras if a["rostos"])
    if com_rosto < 0.5 * len(amostras):
        sys.exit(f"rosto em só {com_rosto} de {len(amostras)} amostras — trilha não confiável")
    saida.write_text(json.dumps({"formato": 2, "largura": largura, "altura": altura, "cortes": cortes,
                                 "amostras": amostras}), encoding="utf-8")
    varios = sum(1 for a in amostras if len(a["rostos"]) > 1)
    print(f"rosto em {com_rosto}/{len(amostras)} amostras; {varios} com 2+ rostos; {len(cortes)} trocas de câmera")


if __name__ == "__main__":
    main()
