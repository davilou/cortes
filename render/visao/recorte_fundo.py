"""Quem fala sem o fundo: o trecho com canal alfa, para a cabeça do f10 sair por cima do card.

Roda no Python do ComfyUI (tem cv2, numpy e onnxruntime com CUDA); o app chama por subprocesso
(src/cortes/render/recorte_fundo.py). Modelo: u2net_human_seg do rembg (~/.u2net), segmentação de
pessoa, só na GPU (sem CUDA sai com erro). A máscara é suavizada no tempo (média móvel) para a borda do cabelo
não tremer de um quadro para o outro.

Uso: <python com onnxruntime> recorte_fundo.py <trecho.mp4> <modelo.onnx> <saida.webm>
Grava um WebM VP9 com alfa (yuva420p), do mesmo tamanho e fps do trecho, sem áudio.
"""
import json
import subprocess
import sys

import cv2
import numpy as np
import onnxruntime as ort
import torch  # noqa: F401 — carrega as DLLs de CUDA (cuBLAS, cuDNN) que o onnxruntime-gpu procura

LADO = 320            # entrada do u2net
SUAVE = 0.6           # peso do quadro atual na média móvel da máscara
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def sondar(trecho: str) -> tuple[int, int, str]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate", "-of", "json", trecho],
        capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"]), str(s["r_frame_rate"])


def mascara(frame: np.ndarray, sessao: ort.InferenceSession, nome: str) -> np.ndarray:
    """Probabilidade de pessoa por pixel (0–1), no tamanho do quadro."""
    altura, largura = frame.shape[:2]
    im = cv2.resize(frame, (LADO, LADO), interpolation=cv2.INTER_AREA)[:, :, ::-1].astype(np.float32)
    im = (im / max(float(im.max()), 1e-6) - _MEAN) / _STD
    saida = sessao.run(None, {nome: np.transpose(im, (2, 0, 1))[None]})[0][0, 0]
    lo, hi = float(saida.min()), float(saida.max())
    m = (saida - lo) / max(hi - lo, 1e-6)
    return cv2.resize(m, (largura, altura), interpolation=cv2.INTER_LINEAR)


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    trecho, modelo, saida = sys.argv[1:]
    largura, altura, fps = sondar(trecho)
    sessao = ort.InferenceSession(modelo, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    if sessao.get_providers()[0] != "CUDAExecutionProvider":
        # na CPU um minuto de trecho leva ~20 min: melhor parar com a causa do que travar a fila
        print("recorte sem CUDA: o onnxruntime não abriu a GPU", file=sys.stderr)
        return 1
    nome = sessao.get_inputs()[0].name
    leitor = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", trecho, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        stdout=subprocess.PIPE)
    escritor = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{largura}x{altura}",
         "-r", fps, "-i", "-", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
         "-deadline", "realtime", "-cpu-used", "8", "-row-mt", "1", "-b:v", "0", "-crf", "32", saida],
        stdin=subprocess.PIPE)
    assert leitor.stdout is not None and escritor.stdin is not None
    tamanho = largura * altura * 3
    anterior: np.ndarray | None = None
    quadros = 0
    while len(buf := leitor.stdout.read(tamanho)) == tamanho:
        frame = np.frombuffer(buf, np.uint8).reshape(altura, largura, 3)
        m = mascara(frame, sessao, nome)
        anterior = m if anterior is None else SUAVE * m + (1 - SUAVE) * anterior
        alfa = (np.clip(anterior, 0, 1) * 255).astype(np.uint8)
        escritor.stdin.write(np.dstack([frame, alfa]).tobytes())
        quadros += 1
    escritor.stdin.close()
    if leitor.wait() != 0 or escritor.wait() != 0 or quadros == 0:
        print(f"recorte falhou: {quadros} quadros lidos", file=sys.stderr)
        return 1
    print(json.dumps({"quadros": quadros, "provedor": sessao.get_providers()[0]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
