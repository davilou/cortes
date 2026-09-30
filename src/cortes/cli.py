"""`cortes detectar URL --nicho financas`: cada etapa grava seu arquivo e é pulada se já existe."""
import argparse
import io
import sys
from dataclasses import asdict
from pathlib import Path

from cortes import ingestao, sinais, transcricao
from cortes.detector import detectar
from cortes.episodio import id_do_video, ler_json, pasta, salvar_json
from cortes.perfil import carregar_perfil
from cortes.segmentacao import frases
from cortes.tipos import Palavra


def _etapa(nome: str, pronto: bool) -> bool:
    print(f"[{'pula' if pronto else 'roda'}] {nome}", flush=True)
    return not pronto


def rodar_detectar(url: str, nicho: str, modelo: str) -> Path:
    d = pasta(id_do_video(url))
    perfil = carregar_perfil(Path("nichos") / nicho)
    if _etapa("download", (d / "video.mp4").exists()):
        ingestao.baixar(url, d)
    if _etapa("áudio", (d / "audio.wav").exists()):
        ingestao.extrair_audio(d)
    if _etapa("transcrição", (d / "palavras.json").exists()):
        salvar_json(d / "palavras.json", [asdict(p) for p in transcricao.transcrever(d / "audio.wav")])
    if _etapa("sinais", (d / "sinais.json").exists()):
        amostras = sinais.ler_wav_mono(d / "audio.wav")
        energia = sinais.energia_por_janela(amostras)
        salvar_json(d / "sinais.json", {"janela_s": sinais.JANELA_S, "energia": energia})
    palavras = [Palavra(**p) for p in ler_json(d / "palavras.json")]
    fs = frases(palavras)
    salvar_json(d / "frases.json", [asdict(f) for f in fs])
    _etapa("detector", False)
    aceitos, descartes = detectar(fs, ler_json(d / "sinais.json")["energia"], perfil, modelo)
    salvar_json(d / "candidatos.json", [asdict(c) for c in aceitos])
    salvar_json(d / "descartados.json", descartes)
    for c in aceitos:
        print(f"{c.nota_final:6.1f}  {c.inicio / 60:5.1f}min  {c.fim - c.inicio:4.0f}s  {c.titulo}")
    print(f"{len(aceitos)} candidatos, {len(descartes)} descartados → {d}")
    return d


def main() -> None:
    if isinstance(sys.stdout, io.TextIOWrapper):   # console cp1252 do Windows quebra com "→" e acentos
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="cortes")
    sub = ap.add_subparsers(dest="comando", required=True)
    det = sub.add_parser("detectar", help="baixa, transcreve e acha candidatos a corte")
    det.add_argument("url")
    det.add_argument("--nicho", default="financas")
    det.add_argument("--modelo", default="sonnet", help="modelo do claude -p (sonnet, opus, haiku)")
    args = ap.parse_args()
    if args.comando == "detectar":
        rodar_detectar(args.url, args.nicho, args.modelo)
