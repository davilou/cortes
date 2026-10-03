"""f9 Ilustrado, passo 2 — busca de imagens, download e a folha de conferência (plano
2026-10-02-ilustrado, Task 2).

A busca é a de imagens do DuckDuckGo (`ddgs`, sem chave), injetável. O download e a folha são
ffmpeg atrás do executor injetável: o ffmpeg lê HTTP e normaliza jpg, png e webp para JPEG sem
precisar de Pillow.

Limites do download, por candidata: PRAZO_DOWNLOAD_S de relógio (mata a árvore), o que limita os
bytes baixados; MAX_PIXELS na decodificação, o que limita a memória. Não há teto de tamanho do
arquivo gravado: ele já sai normalizado a no máximo 1080 px em JPEG q3 (~100-200 KB), então um
teto ali nunca dispararia e não protegeria nada.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from ddgs.exceptions import DDGSException

from cortes.render.ilustracao import Deixa
from cortes.render.processo import ErroRender, Rodar, exigir, rodar_com_prazo

TAM_MIN_PX = 400        # imagem menor que isso estoura no cartão de 860 px
FOLGA_BUSCA = 3         # pede n × isso à busca: o filtro de tamanho e as repetidas descartam parte
REGIAO = "br-pt"
LADO_TILE = 320
FAIXA_ROTULO = 48       # px acima de cada foto para o rótulo D<k>-<j>, sem cobrir a foto
# o modelo reduz a folha para ~1568 px no lado maior: 6 linhas de 368 px (2208) ainda deixam a foto
# com ~230 px; com 12 linhas ela caía para ~130 px e marca/modelo deixavam de ser legíveis
DEIXAS_POR_FOLHA = 6
FONTE = Path("C:/Windows/Fonts/arial.ttf")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/129.0 Safari/537.36")   # loja que recusa o agente do ffmpeg aceita o de navegador
TIMEOUT_REDE_US = 15_000_000   # 15 s sem resposta do servidor da imagem: desiste dessa candidata
ESQUEMAS = frozenset({"http", "https"})   # a URL vem da web: nada de file:, data:, concat: etc.
PROTOCOLOS = "http,https,tls,tcp"        # o que o ffmpeg pode abrir (redirecionamento incluído)
# demuxers de imagem: detecção por extensão (image2) e por conteúdo (*_pipe). Sem hls/concat/mov, que
# abririam outras URLs ou vídeo. Conferido com jpg, png e webp reais em 2026-10-02; avif (mov) fica fora.
DEMUXERS = "image2,jpeg_pipe,png_pipe,webp_pipe,gif_pipe,bmp_pipe,tiff_pipe"
MAX_PIXELS = 50_000_000   # ~7000×7000: acima disso é bomba de descompressão, não foto de produto
PRAZO_DOWNLOAD_S = 30     # por candidata; o -rw_timeout só pega servidor parado, não o que pinga devagar


SEM_RESULTADO_DDGS = "No results found."   # o ddgs 9.16 diz "nada achado" assim (ddgs.py, _search_sync)
ERRO_BUSCA = "erro na busca de imagens"

rodar_download_real: Rodar = rodar_com_prazo(PRAZO_DOWNLOAD_S)


class ErroBusca(ErroRender):
    """A busca não respondeu (limite de uso, tempo, rede) — diferente de não achar nada."""


class BuscaImagens(Protocol):
    def images(self, query: str, **kwargs: Any) -> list[dict[str, Any]]: ...


def ddgs_real() -> BuscaImagens:
    from ddgs import DDGS
    return DDGS()


@dataclass(frozen=True)
class Candidata:
    url: str              # a imagem
    origem: str           # a página onde ela está (fonte_url; licença desconhecida)
    largura: int | None   # a busca nem sempre informa
    altura: int | None


@dataclass(frozen=True)
class LinhaFolha:
    k: int                     # número da deixa no corte (D<k>)
    deixa: Deixa
    imagens: tuple[Path, ...]  # candidatas baixadas, na ordem das colunas (D<k>-1, D<k>-2, ...)


def _medida(v: Any) -> int | None:
    """A busca manda int, texto com número ou vazio. Sem número é "não informado"."""
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().isdigit():
        return int(v)
    return None


def _pequena(c: Candidata) -> bool:
    return any(m is not None and m < TAM_MIN_PX for m in (c.largura, c.altura))


def buscar(busca: str, n: int, ddgs: BuscaImagens) -> list[Candidata]:
    """Até `n` candidatas http(s) sem URL repetida, descartando as menores que TAM_MIN_PX quando o tamanho
    vem informado. Nenhum resultado é lista vazia; falha da busca (limite de uso, tempo, rede) é
    ErroBusca com a busca e a causa."""
    try:
        brutos = ddgs.images(busca, max_results=n * FOLGA_BUSCA, region=REGIAO, safesearch="moderate")
    except DDGSException as e:
        if type(e) is DDGSException and str(e) == SEM_RESULTADO_DDGS:
            return []
        raise ErroBusca(f"{ERRO_BUSCA} '{busca}': {e}") from e
    cands: list[Candidata] = []
    for r in brutos:
        url = str(r.get("image") or "")
        if urlparse(url).scheme.lower() not in ESQUEMAS or any(c.url == url for c in cands):
            continue
        c = Candidata(url, str(r.get("url") or ""), _medida(r.get("width")), _medida(r.get("height")))
        if not _pequena(c):
            cands.append(c)
    return cands[:n]


def args_baixar(url: str, destino: Path) -> list[str]:
    return ["ffmpeg", "-v", "error", "-y", "-user_agent", USER_AGENT, "-rw_timeout", str(TIMEOUT_REDE_US),
            "-protocol_whitelist", PROTOCOLOS, "-format_whitelist", DEMUXERS,
            "-max_pixels", str(MAX_PIXELS), "-i", url, "-frames:v", "1",
            "-vf", "scale=1080:1080:force_original_aspect_ratio=decrease", "-q:v", "3", str(destino)]


def baixar(url: str, destino: Path, rodar: Rodar) -> None:
    """Grava em `<nome>.parcial.jpg` e só renomeia no fim, como a miniatura de rosto."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(".parcial.jpg")
    try:
        exigir(rodar, args_baixar(url, parcial), None, f"download de {url}")
        if not parcial.exists() or parcial.stat().st_size == 0:
            raise ErroRender(f"download de {url}: ffmpeg não gerou a imagem")
        parcial.replace(destino)
    except ErroRender:
        parcial.unlink(missing_ok=True)
        raise


def baixar_candidatas(cands: Sequence[Candidata], pasta: Path, prefixo: str,
                      rodar: Rodar) -> tuple[list[tuple[Candidata, Path]], list[str]]:
    """Baixa cada candidata em `<pasta>/<prefixo>-c<j>.jpg`. Falha numa não para as outras: a causa
    vai para a lista de falhas, que entra no relatório da deixa."""
    baixadas: list[tuple[Candidata, Path]] = []
    falhas: list[str] = []
    for j, c in enumerate(cands, start=1):
        destino = pasta / f"{prefixo}-c{j}.jpg"
        try:
            baixar(c.url, destino, rodar)
        except ErroRender as e:
            falhas.append(f"{c.url}: {e}")
            continue
        baixadas.append((c, destino))
    return baixadas, falhas


def _fonte_ffmpeg() -> str:
    return str(FONTE).replace("\\", "/").replace(":", "\\:")   # ':' separa opção no filtergraph


def _tile(i: int, rotulo: str) -> str:
    lado, faixa = LADO_TILE, FAIXA_ROTULO
    return (f"[{i}:v]scale={lado}:{lado}:force_original_aspect_ratio=decrease,"
            f"pad={lado}:{lado}:(ow-iw)/2:(oh-ih)/2:white,"
            f"pad={lado}:{lado + faixa}:0:{faixa}:white,"
            f"drawtext=fontfile='{_fonte_ffmpeg()}':text='{rotulo}':x=8:y=7:fontsize=34:"
            f"fontcolor=black[t{i}]")


def dividir_folhas(linhas: Sequence[LinhaFolha]) -> list[list[LinhaFolha]]:
    """Puro. As deixas com candidata baixada, em grupos de até DEIXAS_POR_FOLHA (uma folha cada)."""
    com = [ln for ln in linhas if ln.imagens]
    return [com[i:i + DEIXAS_POR_FOLHA] for i in range(0, len(com), DEIXAS_POR_FOLHA)]


def folha_args(linhas: Sequence[LinhaFolha], destino: Path) -> list[str]:
    """Puro. Mosaico com uma linha por deixa e uma coluna por candidata, cada foto com `D<k>-<j>`
    numa faixa acima dela. Deixa sem candidata baixada não entra."""
    entradas: list[str] = []
    tiles: list[str] = []
    posicoes: list[str] = []
    for r, linha in enumerate(ln for ln in linhas if ln.imagens):
        for j, img in enumerate(linha.imagens):
            i = len(posicoes)
            entradas += ["-i", str(img)]
            tiles.append(_tile(i, f"D{linha.k}-{j + 1}"))
            posicoes.append(f"{j * LADO_TILE}_{r * (LADO_TILE + FAIXA_ROTULO)}")
    if not posicoes:
        raise ErroRender("folha de conferência sem nenhuma imagem baixada")
    if len(posicoes) == 1:
        juntar = "[t0]null[folha]"
    else:
        rotulos = "".join(f"[t{i}]" for i in range(len(posicoes)))
        juntar = f"{rotulos}xstack=inputs={len(posicoes)}:layout={'|'.join(posicoes)}:fill=white[folha]"
    return ["ffmpeg", "-v", "error", "-y", *entradas, "-filter_complex", ";".join([*tiles, juntar]),
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
