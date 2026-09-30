"""Mede cada short do corpus: duração, ritmo de cortes, fala, transcrição e folha de quadros.

Saída: corpus/medidas.json e corpus/folhas/<id>.jpg (6 quadros lado a lado, para classificar layout).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import whisper

BASE = Path(__file__).parent / sys.argv[1]
VIDEOS = BASE / "videos"
FOLHAS = BASE / "folhas"
FOLHAS.mkdir(exist_ok=True)


def run(args: list[str]) -> str:
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"{args[0]} falhou: {r.stderr[-500:]}")
    return r.stdout + r.stderr


def probe(p: Path) -> tuple[float, int, int]:
    out = json.loads(run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height",
                          "-select_streams", "v:0", "-of", "json", str(p)]))
    s = out["streams"][0]
    return float(out["format"]["duration"]), int(s["width"]), int(s["height"])


def cortes(p: Path) -> list[float]:
    """Instantes de troca de plano (score de cena > 0.3)."""
    out = run(["ffmpeg", "-hide_banner", "-i", str(p), "-vf", "select='gt(scene,0.3)',showinfo",
               "-an", "-f", "null", "-"])
    return [float(t) for t in re.findall(r"pts_time:([\d.]+)", out)]


def folha(p: Path, dur: float, vid: str) -> None:
    # 3 quadros de abertura + 9 distribuídos no resto: mostra alternância de layout ao longo do vídeo
    fim = dur - 0.3
    if dur < 6.0:  # short curtíssimo: 12 quadros distribuídos no que existe
        tempos = [0.1 + (fim - 0.1) * k / 11 for k in range(12)]
    else:
        tempos = [0.5, 1.5, 3.0] + [min(3.0 + (dur - 3.5) * k / 9, fim) for k in range(1, 10)]
    quadros = []
    for i, t in enumerate(tempos):
        q = FOLHAS / f"_{vid}_{i}.jpg"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(p), "-frames:v", "1",
             "-vf", "scale=270:480:force_original_aspect_ratio=decrease,pad=270:480:(ow-iw)/2:(oh-ih)/2",
             str(q)])
        quadros.append(q)
    args = ["ffmpeg", "-y", "-v", "error"]
    for q in quadros:
        args += ["-i", str(q)]
    linha1 = "".join(f"[{i}]" for i in range(6)) + "hstack=6[a]"
    linha2 = "".join(f"[{i}]" for i in range(6, 12)) + "hstack=6[b]"
    args += ["-filter_complex", f"{linha1};{linha2};[a][b]vstack", str(FOLHAS / f"{vid}.jpg")]
    run(args)
    for q in quadros:
        q.unlink()


def main() -> None:
    sel = json.loads((BASE / "selecao.json").read_text(encoding="utf-8"))
    saida = BASE / "medidas.json"
    feitos = {m["id"]: m for m in json.loads(saida.read_text(encoding="utf-8"))} if saida.exists() else {}
    modelo = whisper.load_model("medium", device="cuda")
    for s in sel:
        vid = s["id"]
        if vid in feitos:
            continue
        p = VIDEOS / f"{vid}.mp4"
        if not p.exists():
            print(f"FALTANDO {vid} (download falhou) — fica fora da amostra", flush=True)
            continue
        info = json.loads((VIDEOS / f"{vid}.info.json").read_text(encoding="utf-8"))
        dur, w, h = probe(p)
        cs = cortes(p)
        folha(p, dur, vid)
        tr = modelo.transcribe(str(p), language="pt", word_timestamps=True, fp16=True)
        palavras = [w_ for seg in tr["segments"] for w_ in seg.get("words", [])]
        feitos[vid] = {
            **s,
            "titulo_pt": info.get("title"),
            "upload": info.get("upload_date"),
            "likes": info.get("like_count"),
            "comentarios": info.get("comment_count"),
            "dur": round(dur, 1), "w": w, "h": h,
            "n_cortes": len(cs),
            "cortes_por_10s": round(len(cs) / dur * 10, 2),
            "primeiro_corte": cs[0] if cs else None,
            "palavras_por_s": round(len(palavras) / dur, 2),
            "silencio_inicial": round(palavras[0]["start"], 2) if palavras else None,
            "abertura_3s": " ".join(x["word"].strip() for x in palavras if x["start"] < 3.0),
            "transcricao": tr["text"].strip(),
            "ultima_frase": tr["segments"][-1]["text"].strip() if tr["segments"] else "",
        }
        saida.write_text(json.dumps(list(feitos.values()), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(feitos)}/{len(sel)} {vid}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
