"""Rodada 2: para cada canal, acha o corte de 60 dias por busca binária na data e sorteia top/meio/fundo.

A aba de shorts vem da mais nova para a mais antiga, então a data é monotônica no índice.
Saída: corpus2/selecao.json
"""
import json
import statistics
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path(__file__).parent
CORTE = "20260801"  # 60 dias antes de 2026-09-30
CANAIS = ["PrimoCast", "OsEconomistas", "OsSociosCortes", "BrunoPerini", "IrmaosDias", "MindsetOutlier",
          "CortesDaEconomia", "ReflexaoDoDia", "RelevantesDeNegocios", "CodigosBilionarios", "MarcalNaIntegra",
          "JMCortes"]
N_TOP, N_MEIO, N_FUNDO = 10, 10, 5


def data(vid: str) -> str:
    r = subprocess.run(["python", "-m", "yt_dlp", "--skip-download", "--print", "upload_date",
                        f"https://www.youtube.com/shorts/{vid}"], capture_output=True, text=True)
    time.sleep(1.5)  # ritmo baixo: o YouTube bloqueou o IP antes com requisições rápidas
    d = r.stdout.strip()
    if not (len(d) == 8 and d.isdigit()):
        raise RuntimeError(f"sem data para {vid}: {r.stderr[-300:]}")
    return d


def data_idx(rows: list[list[str]], i: int) -> str:
    """Data do item i; se o vídeo exigir login, usa o vizinho mais antigo (erro após 5 tentativas)."""
    for j in range(i, min(i + 5, len(rows))):
        try:
            return data(rows[j][0])
        except RuntimeError:
            continue
    raise RuntimeError(f"5 vídeos seguidos sem data a partir do índice {i}")


def primeiro_antigo(rows: list[list[str]]) -> int:
    """Menor índice cuja data é anterior ao CORTE."""
    lo, hi = 0, len(rows) - 1
    if data_idx(rows, hi - 4) >= CORTE:
        raise RuntimeError("canal sem shorts com mais de 60 dias na lista")
    while lo < hi:
        mid = (lo + hi) // 2
        if data_idx(rows, mid) < CORTE:
            hi = mid
        else:
            lo = mid + 1
    return lo


def selecionar(canal: str) -> tuple[list[dict], str]:
    linhas = (BASE / "listas2" / f"{canal}.txt").read_text(encoding="utf-8", errors="replace").splitlines()
    rows = [l.split("|", 2) for l in linhas]
    rows = [r for r in rows if r[1].isdigit()]
    i = primeiro_antigo(rows)
    eleg = sorted(rows[i:], key=lambda r: -int(r[1]))
    m = len(eleg) // 2
    grupos = {"top": eleg[:N_TOP], "meio": eleg[m - N_MEIO // 2:m + N_MEIO // 2], "fundo": eleg[-N_FUNDO:]}
    sel = [{"canal": canal, "grupo": g, "id": r[0], "views": int(r[1])} for g, rs in grupos.items() for r in rs]
    v = [int(r[1]) for r in eleg]
    resumo = (f"{canal:22s} elegiveis={len(eleg):3d} (a partir do idx {i}) mediana={statistics.median(v):.0f} "
              f"top>={grupos['top'][-1][1]} meio={grupos['meio'][-1][1]}-{grupos['meio'][0][1]} fundo<={grupos['fundo'][0][1]}")
    return sel, resumo


def main() -> None:
    out = BASE / "corpus2"
    out.mkdir(exist_ok=True)
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(selecionar, CANAIS))
    sel = [s for r, _ in res for s in r]
    for _, resumo in res:
        print(resumo)
    (out / "selecao.json").write_text(json.dumps(sel, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(sel))


if __name__ == "__main__":
    main()
