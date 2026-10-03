"""f4 B-roll, a folha de conferência mista (planos 2026-10-03-broll-automatico, Task 3, e
2026-10-03-melhora-f4).

Cada deixa ocupa um bloco: uma linha por vídeo, com os momentos dele lado a lado — cada momento é um
tile `D<k>-V<j>m<p>` com 3 quadros (início, meio e fim, de `broll_quadros.extrair_momentos`) — e,
na deixa literal, uma linha com as fotos (`D<k>-F<j>`). O rótulo fica numa faixa branca acima do
tile, sem cobrir a imagem.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from cortes.render.broll_quadros import Quadros
from cortes.render.ilustracao import Deixa
from cortes.render.processo import ErroRender, Rodar, exigir

LARGURA_QUADRO, ALTURA_QUADRO = 120, 213   # 9:16; 3 por momento = 360 px, 4 momentos ≈ 1,5 mil px
LADO_FOTO = 300
FAIXA_ROTULO = 40       # px acima de cada tile para o rótulo, sem cobrir a imagem
ESPACO_TILE = 16        # branco entre tiles: maior que os 4 px entre quadros, para um momento não
                        # parecer continuação do outro
ESPACO_DEIXA = 24       # branco a mais entre o bloco de uma deixa e o da próxima
# o modelo reduz a folha para ~1568 px no lado maior: um bloco literal (2 vídeos + fotos) tem
# 2 × 253 + 340 px, e 2 blocos (~1,7 mil px) mantêm a redução em ~0,9 — com 4 o quadro caía para
# ~70 px de largura e o produto deixava de ser legível
DEIXAS_POR_FOLHA = 2
FONTE = Path("C:/Windows/Fonts/arial.ttf")


@dataclass(frozen=True)
class LinhaFolha:
    k: int                                   # número da deixa no corte (D<k>)
    deixa: Deixa
    videos: tuple[tuple[Quadros, ...], ...]  # D<k>-V<j>: os momentos (m1, m2, ...) de cada vídeo
    fotos: tuple[Path, ...] = ()             # D<k>-F<j>; só deixa literal tem foto

    def rotulos(self) -> list[str]:
        return [f"V{j}m{p}" for j, ms in enumerate(self.videos, start=1) for p in range(1, len(ms) + 1)] + \
               [f"F{j}" for j in range(1, len(self.fotos) + 1)]


@dataclass(frozen=True)
class _Tile:
    rotulo: str
    imagens: tuple[Path, ...]   # 3 quadros (momento) ou 1 foto

    @property
    def largura(self) -> int:
        return 3 * LARGURA_QUADRO if len(self.imagens) == 3 else LADO_FOTO

    @property
    def altura(self) -> int:
        return (ALTURA_QUADRO if len(self.imagens) == 3 else LADO_FOTO) + FAIXA_ROTULO


def _linhas(ln: LinhaFolha) -> list[list[_Tile]]:
    """Uma linha de tiles por vídeo e, se houver, uma com as fotos."""
    linhas = [[_Tile(f"D{ln.k}-V{j}m{p}", q) for p, q in enumerate(ms, start=1)]
              for j, ms in enumerate(ln.videos, start=1) if ms]
    if ln.fotos:
        linhas.append([_Tile(f"D{ln.k}-F{j}", (f,)) for j, f in enumerate(ln.fotos, start=1)])
    return linhas


def _fonte_ffmpeg() -> str:
    return str(FONTE).replace("\\", "/").replace(":", "\\:")   # ':' separa opção no filtergraph


def _rotular(entrada: str, tile: _Tile, t: int) -> str:
    return (f"{entrada}pad={tile.largura}:{tile.altura}:0:{FAIXA_ROTULO}:white,"
            f"drawtext=fontfile='{_fonte_ffmpeg()}':text='{tile.rotulo}':x=6:y=6:fontsize=28:"
            f"fontcolor=black[t{t}]")


def _filtro(tile: _Tile, i: int, t: int) -> str:
    """O filtro do tile `t`, cujas imagens são as entradas i, i+1, ... do ffmpeg."""
    if len(tile.imagens) == 1:
        lado = LADO_FOTO
        return _rotular(f"[{i}:v]scale={lado}:{lado}:force_original_aspect_ratio=decrease,"
                        f"pad={lado}:{lado}:(ow-iw)/2:(oh-ih)/2:white,", tile, t)
    lq, aq = LARGURA_QUADRO, ALTURA_QUADRO   # 4 px de branco entre os quadros
    quadros = ";".join(f"[{i + q}:v]scale={lq - 4}:{aq}:force_original_aspect_ratio=decrease,"
                       f"pad={lq}:{aq}:(ow-iw)/2:(oh-ih)/2:white[q{t}_{q}]" for q in range(3))
    return f"{quadros};" + _rotular(f"[q{t}_0][q{t}_1][q{t}_2]hstack=inputs=3,", tile, t)


def dividir_folhas(linhas: Sequence[LinhaFolha]) -> list[list[LinhaFolha]]:
    """Puro. As deixas com candidato, em grupos de até DEIXAS_POR_FOLHA (uma folha cada)."""
    com = [ln for ln in linhas if ln.rotulos()]
    return [com[i:i + DEIXAS_POR_FOLHA] for i in range(0, len(com), DEIXAS_POR_FOLHA)]


def _juntar(n: int, posicoes: list[str]) -> str:
    if n == 1:
        return "[t0]null[folha]"
    rotulos = "".join(f"[t{i}]" for i in range(n))
    return f"{rotulos}xstack=inputs={n}:layout={'|'.join(posicoes)}:fill=white[folha]"


def folha_args(linhas: Sequence[LinhaFolha], destino: Path) -> list[str]:
    """Puro. Mosaico com um bloco por deixa (uma linha por vídeo, com os momentos, e uma com as
    fotos), cada tile com o rótulo acima. Deixa sem candidato não entra."""
    entradas: list[str] = []
    filtros: list[str] = []
    posicoes: list[str] = []
    y = 0
    for ln in (ln for ln in linhas if ln.rotulos()):
        for linha in _linhas(ln):
            x = 0
            for tile in linha:
                filtros.append(_filtro(tile, len(entradas) // 2, len(posicoes)))
                entradas += [a for img in tile.imagens for a in ("-i", str(img))]
                posicoes.append(f"{x}_{y}")
                x += tile.largura + ESPACO_TILE
            y += max(t.altura for t in linha)
        y += ESPACO_DEIXA
    if not posicoes:
        raise ErroRender("folha de conferência sem nenhum candidato baixado")
    return ["ffmpeg", "-v", "error", "-y", *entradas,
            "-filter_complex", ";".join([*filtros, _juntar(len(posicoes), posicoes)]),
            "-map", "[folha]", "-frames:v", "1", "-q:v", "3", str(destino)]


def gerar_folha(linhas: Sequence[LinhaFolha], destino: Path, rodar: Rodar) -> None:
    if not FONTE.exists():
        raise ErroRender(f"fonte da folha de conferência não encontrada: {FONTE}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(".parcial.jpg")
    try:
        exigir(rodar, folha_args(linhas, parcial), None, "folha de conferência")
        if not parcial.exists() or parcial.stat().st_size == 0:
            raise ErroRender("folha de conferência: ffmpeg não gerou a imagem")
        parcial.replace(destino)
    except ErroRender:
        parcial.unlink(missing_ok=True)
        raise
