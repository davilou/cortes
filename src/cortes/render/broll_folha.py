"""f4 B-roll, a folha de conferência mista (plano 2026-10-03-broll-automatico, Task 3).

Uma linha por deixa. Cada vídeo é um tile `D<k>-V<j>` com 3 quadros do trecho (início, meio e fim,
de `broll_video.extrair_quadros`); cada foto, um tile `D<k>-F<j>`. Os vídeos vêm primeiro na linha.
O rótulo fica numa faixa branca acima do tile, sem cobrir a imagem.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from cortes.render.ilustracao import Deixa
from cortes.render.processo import ErroRender, Rodar, exigir

LADO_TILE = 320         # altura de todo tile; a foto é um quadrado de 320
LARGURA_QUADRO = 180    # quadro 9:16 do trecho a 320 de altura; 3 lado a lado = 540
FAIXA_ROTULO = 48       # px acima de cada tile para o rótulo, sem cobrir a imagem
ESPACO_TILE = 16        # branco entre tiles: maior que os 4 px entre quadros, para um vídeo não
                        # parecer continuação do outro
# o modelo reduz a folha para ~1568 px no lado maior: uma linha cheia (2 vídeos + 2 fotos) tem
# 1768 px, e 4 linhas de 368 px (1472) mantêm a redução em ~0,9 — com 6 linhas (2208) os quadros
# caíam para ~125 px de largura e o produto deixava de ser legível
DEIXAS_POR_FOLHA = 4
FONTE = Path("C:/Windows/Fonts/arial.ttf")

Quadros = tuple[Path, Path, Path]


@dataclass(frozen=True)
class LinhaFolha:
    k: int                          # número da deixa no corte (D<k>)
    deixa: Deixa
    videos: tuple[Quadros, ...]     # D<k>-V1, D<k>-V2, ...
    fotos: tuple[Path, ...] = ()    # D<k>-F1, ...; só deixa literal tem foto

    def rotulos(self) -> list[str]:
        return [f"V{j}" for j in range(1, len(self.videos) + 1)] + \
               [f"F{j}" for j in range(1, len(self.fotos) + 1)]


@dataclass(frozen=True)
class _Tile:
    rotulo: str
    imagens: tuple[Path, ...]   # 3 quadros (vídeo) ou 1 foto

    @property
    def largura(self) -> int:
        return 3 * LARGURA_QUADRO if len(self.imagens) == 3 else LADO_TILE


def _tiles(ln: LinhaFolha) -> list[_Tile]:
    return [_Tile(f"D{ln.k}-V{j}", q) for j, q in enumerate(ln.videos, start=1)] + \
           [_Tile(f"D{ln.k}-F{j}", (f,)) for j, f in enumerate(ln.fotos, start=1)]


def _fonte_ffmpeg() -> str:
    return str(FONTE).replace("\\", "/").replace(":", "\\:")   # ':' separa opção no filtergraph


def _rotular(entrada: str, largura: int, rotulo: str, t: int) -> str:
    return (f"{entrada}pad={largura}:{LADO_TILE + FAIXA_ROTULO}:0:{FAIXA_ROTULO}:white,"
            f"drawtext=fontfile='{_fonte_ffmpeg()}':text='{rotulo}':x=8:y=7:fontsize=34:"
            f"fontcolor=black[t{t}]")


def _filtro(tile: _Tile, i: int, t: int) -> str:
    """O filtro do tile `t`, cujas imagens são as entradas i, i+1, ... do ffmpeg."""
    if len(tile.imagens) == 1:
        lado = LADO_TILE
        return _rotular(f"[{i}:v]scale={lado}:{lado}:force_original_aspect_ratio=decrease,"
                        f"pad={lado}:{lado}:(ow-iw)/2:(oh-ih)/2:white,", lado, tile.rotulo, t)
    lq = LARGURA_QUADRO   # 4 px de branco entre os quadros
    quadros = ";".join(f"[{i + q}:v]scale={lq - 4}:{LADO_TILE}:force_original_aspect_ratio=decrease,"
                       f"pad={lq}:{LADO_TILE}:(ow-iw)/2:(oh-ih)/2:white[q{t}_{q}]" for q in range(3))
    return f"{quadros};" + _rotular(f"[q{t}_0][q{t}_1][q{t}_2]hstack=inputs=3,", tile.largura,
                                    tile.rotulo, t)


def dividir_folhas(linhas: Sequence[LinhaFolha]) -> list[list[LinhaFolha]]:
    """Puro. As deixas com candidato, em grupos de até DEIXAS_POR_FOLHA (uma folha cada)."""
    com = [ln for ln in linhas if ln.rotulos()]
    return [com[i:i + DEIXAS_POR_FOLHA] for i in range(0, len(com), DEIXAS_POR_FOLHA)]


def folha_args(linhas: Sequence[LinhaFolha], destino: Path) -> list[str]:
    """Puro. Mosaico com uma linha por deixa: os vídeos (3 quadros cada) e depois as fotos, cada
    tile com `D<k>-V<j>` ou `D<k>-F<j>` acima. Deixa sem candidato não entra."""
    entradas: list[str] = []
    filtros: list[str] = []
    posicoes: list[str] = []
    for r, ln in enumerate(ln for ln in linhas if ln.rotulos()):
        x = 0
        for tile in _tiles(ln):
            filtros.append(_filtro(tile, len(entradas) // 2, len(posicoes)))
            entradas += [a for img in tile.imagens for a in ("-i", str(img))]
            posicoes.append(f"{x}_{r * (LADO_TILE + FAIXA_ROTULO)}")
            x += tile.largura + ESPACO_TILE
    if not posicoes:
        raise ErroRender("folha de conferência sem nenhum candidato baixado")
    if len(posicoes) == 1:
        juntar = "[t0]null[folha]"
    else:
        rotulos = "".join(f"[t{i}]" for i in range(len(posicoes)))
        juntar = f"{rotulos}xstack=inputs={len(posicoes)}:layout={'|'.join(posicoes)}:fill=white[folha]"
    return ["ffmpeg", "-v", "error", "-y", *entradas, "-filter_complex", ";".join([*filtros, juntar]),
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
