"""Busca de fotos e download (plano 2026-10-02-ilustrado, Task 2) — no f4 B-roll, a foto de reserva
da deixa literal sem vídeo (a folha mista fica em `broll_folha.py`).

A busca é a de imagens do DuckDuckGo (`ddgs`, sem chave), injetável. O download e a folha são
ffmpeg atrás do executor injetável: o ffmpeg lê HTTP e normaliza jpg, png e webp para JPEG sem
precisar de Pillow.

Limites do download, por candidata: PRAZO_DOWNLOAD_S de relógio (mata a árvore), o que limita os
bytes baixados; MAX_PIXELS na decodificação, o que limita a memória. Não há teto de tamanho do
arquivo gravado: ele já sai normalizado a no máximo 1080 px em JPEG q3 (~100-200 KB), então um
teto ali nunca dispararia e não protegeria nada.
"""
import ipaddress
import socket
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from ddgs.exceptions import DDGSException

from cortes.render.processo import ErroRender, Rodar, exigir, rodar_com_prazo

TAM_MIN_PX = 400        # imagem menor que isso fica borrada na tela cheia
FOLGA_BUSCA = 3         # pede n × isso à busca: o filtro de tamanho e as repetidas descartam parte
REGIAO = "br-pt"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/129.0 Safari/537.36")   # loja que recusa o agente do ffmpeg aceita o de navegador
TIMEOUT_REDE_US = 15_000_000   # 15 s sem resposta do servidor da imagem: desiste dessa candidata
ESQUEMAS = frozenset({"http", "https"})   # a URL vem da web: nada de file:, data:, concat: etc.
# nomes que apontam para esta máquina ou para a rede local; IP literal é conferido por ipaddress
NOMES_LOCAIS = frozenset({"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"})
SUFIXOS_LOCAIS = (".localhost", ".local", ".internal", ".lan", ".home.arpa")
PROTOCOLOS = "http,https,tls,tcp"        # o que o ffmpeg pode abrir (redirecionamento incluído)
# demuxers de imagem: detecção por extensão (image2) e por conteúdo (*_pipe). Sem hls/concat/mov, que
# abririam outras URLs ou vídeo. Conferido com jpg, png e webp reais em 2026-10-02; avif (mov) fica fora.
DEMUXERS = "image2,jpeg_pipe,png_pipe,webp_pipe,gif_pipe,bmp_pipe,tiff_pipe"
MAX_PIXELS = 50_000_000   # ~7000×7000: acima disso é bomba de descompressão, não foto de produto
DOWNLOADS_SIMULTANEOS = 4   # candidatas de uma deixa baixadas ao mesmo tempo
PRAZO_DOWNLOAD_S = 30     # por candidata; o -rw_timeout só pega servidor parado, não o que pinga devagar


SEM_RESULTADO_DDGS = "No results found."   # o ddgs 9.16 diz "nada achado" assim (ddgs.py, _search_sync)
ERRO_BUSCA = "erro na busca de imagens"

# falha de download que outra tentativa pode resolver: prazo (processo.py), rede ou servidor 5xx.
# 404/403 e imagem que não decodifica não estão aqui: tentar de novo dá o mesmo.
SINAIS_TEMPORARIOS = ("foi interrompido", "não morreu", "timed out", "Connection refused",
                      "Connection reset", "Failed to resolve", "Network is unreachable",
                      "Temporary failure", "Server returned 5")

rodar_download_real: Rodar = rodar_com_prazo(PRAZO_DOWNLOAD_S)


def falha_temporaria(falha: str) -> bool:
    """Puro. A falha de download (a linha de `baixar_candidatas`) é de prazo, rede ou servidor 5xx."""
    return any(s.lower() in falha.lower() for s in SINAIS_TEMPORARIOS)


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


def _medida(v: Any) -> int | None:
    """A busca manda int, texto com número ou vazio. Sem número é "não informado"."""
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().isdigit():
        return int(v)
    return None


def _pequena(c: Candidata) -> bool:
    return any(m is not None and m < TAM_MIN_PX for m in (c.largura, c.altura))


def _ip_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """IP escrito na URL, inclusive nas formas que o resolvedor aceita (2130706433, 0x7f.1, 127.1).
    `inet_aton` só interpreta o texto: não consulta DNS."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    try:
        return ipaddress.IPv4Address(socket.inet_aton(host))
    except OSError:
        return None


def host_proibido(url: str) -> bool:
    """Puro (sem DNS). Sem host, nome local ou IP que não é público (loopback, privado, link-local,
    0.0.0.0, IPv4 dentro de IPv6): o ffmpeg abriria daqui o painel, o roteador ou os metadados da
    nuvem. Nome público que resolve para IP privado não é pego aqui."""
    host = (urlparse(url).hostname or "").rstrip(".").lower()
    if not host or host in NOMES_LOCAIS or host.endswith(SUFIXOS_LOCAIS):
        return True
    ip = _ip_literal(host)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip is not None and not ip.is_global


def buscar(busca: str, n: int, ddgs: BuscaImagens) -> list[Candidata]:
    """Até `n` candidatas http(s) de host público sem URL repetida, descartando as menores que
    TAM_MIN_PX quando o tamanho vem informado. Nenhum resultado é lista vazia; falha da busca
    (limite de uso, tempo, rede) é ErroBusca com a busca e a causa."""
    try:
        brutos = ddgs.images(busca, max_results=n * FOLGA_BUSCA, region=REGIAO, safesearch="moderate")
    except DDGSException as e:
        if type(e) is DDGSException and str(e) == SEM_RESULTADO_DDGS:
            return []
        raise ErroBusca(f"{ERRO_BUSCA} '{busca}': {e}") from e
    cands: list[Candidata] = []
    for r in brutos:
        url = str(r.get("image") or "")
        if urlparse(url).scheme.lower() not in ESQUEMAS or host_proibido(url):
            continue
        if any(c.url == url for c in cands):
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


def _baixar_uma(c: Candidata, destino: Path, rodar: Rodar) -> str | None:
    """A causa da falha, ou None se baixou."""
    try:
        baixar(c.url, destino, rodar)
    except ErroRender as e:
        return f"{c.url}: {e}"
    return None


def baixar_candidatas(cands: Sequence[Candidata], pasta: Path, prefixo: str,
                      rodar: Rodar) -> tuple[list[tuple[Candidata, Path]], list[str]]:
    """Baixa cada candidata em `<pasta>/<prefixo>-c<j>.jpg`, até DOWNLOADS_SIMULTANEOS ao mesmo
    tempo; o resultado sai na ordem das candidatas. Falha numa não para as outras: a causa vai para
    a lista de falhas, que entra no relatório da deixa."""
    destinos = [pasta / f"{prefixo}-c{j}.jpg" for j in range(1, len(cands) + 1)]
    with ThreadPoolExecutor(max_workers=max(1, min(DOWNLOADS_SIMULTANEOS, len(cands)))) as pool:
        causas = list(pool.map(lambda c, d: _baixar_uma(c, d, rodar), cands, destinos))
    baixadas = [(c, d) for c, d, causa in zip(cands, destinos, causas, strict=True) if causa is None]
    return baixadas, [causa for causa in causas if causa is not None]
