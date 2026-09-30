"""Rodada 2: desvenda os códigos cegos e compara top × meio × fundo, dentro de cada canal.

A pergunta principal é top × meio: o que leva um corte mediano ao topo.
Robustez = em quantos canais a direção top>meio se repete (só canais com os dois grupos).
"""
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).parent / "corpus2"
MAPA = Path(sys.argv[1])  # mapa código→id, guardado fora da pasta dos classificadores

CATS = ["formato_origem", "abertura_visual", "layout_principal", "legenda_estilo", "legenda_posicao",
        "gancho_tipo", "tema", "emocao_dominante", "desfecho", "fracao_tempo_visual"]
BOOLS = ["troca_de_falante_visivel", "titulo_fixo_na_tela", "zoom_variado", "insercoes_visuais",
         "marca_canal_visivel", "personagem_famoso"]
NUMS_CLASS = ["gancho_forca", "autocontido", "alternancia_layout"]
NUMS_MED = ["dur", "cortes_por_10s", "palavras_por_s"]
GRUPOS = ["top", "meio", "fundo"]


def carregar() -> list[dict]:
    mapa = json.loads(MAPA.read_text())
    med = {m["id"]: m for m in json.loads((BASE / "medidas.json").read_text(encoding="utf-8"))}
    linhas = []
    for f in sorted((BASE / "cego_res").glob("lote_*.json")):
        for c in json.loads(f.read_text(encoding="utf-8")):
            linhas.append({**c, **med[mapa[c["codigo"]]]})
    faltam = set(mapa) - {l["codigo"] for l in linhas}
    if faltam:
        raise RuntimeError(f"{len(faltam)} códigos sem classificação: {sorted(faltam)[:5]}...")
    return linhas


def pct(xs: list, pred) -> str:
    return f"{100 * sum(map(pred, xs)) / len(xs):4.0f}%" if xs else "   -"


def canais_na_direcao(rows: list[dict], valor) -> str:
    """Conta canais onde top > meio e top < meio para uma medida por linha."""
    mais = menos = 0
    for c in sorted({r["canal"] for r in rows}):
        t = [valor(r) for r in rows if r["canal"] == c and r["grupo"] == "top"]
        m = [valor(r) for r in rows if r["canal"] == c and r["grupo"] == "meio"]
        t, m = [x for x in t if x is not None], [x for x in m if x is not None]
        if not t or not m:
            continue
        d = st.mean(t) - st.mean(m)
        mais += d > 0
        menos += d < 0
    return f"canais top>meio {mais:2d} | top<meio {menos:2d}"


def main() -> None:
    rows = carregar()
    (BASE / "tabela_final.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    g = {k: [r for r in rows if r["grupo"] == k] for k in GRUPOS}
    print("n:", {k: len(v) for k, v in g.items()})
    print("\n== NUMÉRICOS (mediana top | meio | fundo)")
    for k in NUMS_MED + NUMS_CLASS:
        med = [st.median([r[k] for r in g[x] if r.get(k) is not None]) for x in GRUPOS]
        print(f"{k:26s} {med[0]:6.2f} | {med[1]:6.2f} | {med[2]:6.2f}   "
              + canais_na_direcao(rows, lambda r, k=k: r.get(k)))
    print("\n== BOOLEANOS (% top | meio | fundo)")
    for k in BOOLS:
        print(f"{k:26s} " + " | ".join(pct(g[x], lambda r, k=k: bool(r[k])) for x in GRUPOS)
              + "   " + canais_na_direcao(rows, lambda r, k=k: float(bool(r[k]))))
    tipos = Counter(t for r in rows for t in r["visual_externo_tipo"])
    print("\n== VISUAL EXTERNO por tipo (% top | meio | fundo)")
    for t in tipos:
        print(f"{t:26s} " + " | ".join(pct(g[x], lambda r, t=t: t in r["visual_externo_tipo"]) for x in GRUPOS)
              + "   " + canais_na_direcao(rows, lambda r, t=t: float(t in r["visual_externo_tipo"])))
    com_visual = [r for r in rows if r["visual_sincronizado"] is not None]
    print(f"{'sincronizado (dos c/ visual)':26s} "
          + " | ".join(pct([r for r in com_visual if r["grupo"] == x], lambda r: r["visual_sincronizado"]) for x in GRUPOS))
    for k in CATS:
        print(f"\n== {k} (% top | meio | fundo)")
        vals = Counter(r[k] for r in rows)
        for v, _ in vals.most_common():
            print(f"  {str(v):38s} " + " | ".join(pct(g[x], lambda r, v=v, k=k: r[k] == v) for x in GRUPOS)
                  + "   " + canais_na_direcao(rows, lambda r, v=v, k=k: float(r[k] == v)))


if __name__ == "__main__":
    main()
