"""f4 B-roll, passo 2 — vídeo do YouTube: busca e vídeo inteiro baixado (plano 2026-10-03-broll-automatico,
Task 2). Protótipo: `testes/comum/buscar_broll.py`. O que o ffmpeg tira dele — os momentos da folha,
o trecho escolhido e a foto em tela cheia — fica em `broll_quadros.py`.

Tudo passa pelo executor injetável (`processo.Rodar`), com prazo próprio: nada de rede no check. O
YouTube já bloqueou este IP uma vez (spec §8): 429 ou "confirme que não é um robô" vira `ErroBusca`,
a falha transitória da deixa, e nunca é repetido em laço aqui. Quem chama faz busca e download em
série, sem paralelo no YouTube.

O vídeo baixado fica no disco até a conferência escolher o momento (plano 2026-10-03-melhora-f4):
quem chama apaga com `apagar_bruto`.
"""
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cortes.render.ilustracao_imagens import ErroBusca
from cortes.render.processo import CAUDA, ErroRender, Rodar, rodar_com_prazo

YT = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-warnings"]
N_RESULTADOS = 15           # resultados pedidos à busca (uma página só); o filtro de duração descarta parte
DUR_MIN_VIDEO_S = 15.0      # menos que isso é Short ou vinheta
DUR_MAX_VIDEO_S = 3 * 60.0  # o vídeo é baixado inteiro: acima disso o download passa do prazo
MAX_CANDIDATOS = 2          # por deixa
# O vídeo inteiro pelo downloader nativo do yt-dlp, só vídeo, e o ffmpeg corta o trecho local. Medido
# em 2026-10-03: `--download-sections` (o ffmpeg lendo a seção por HTTP) levava ~45 s por 5 s de vídeo e
# estourava o prazo em metade dos casos; o vídeo inteiro de 71 s/1080p/38 MB veio em 9 s (spec §11).
# O 720p sai visivelmente mais mole no 1080×1920, então fica 1080p.
FORMATO = "bv*[height<=1080][ext=mp4]/bv*[height<=1080]"   # só vídeo, sem áudio, até 1080p
MAX_TAMANHO = "120M"        # 3 min de 1080p só-vídeo ficam bem abaixo; acima é bitrate de 4K disfarçado
PRAZO_BUSCA_S = 30
PRAZO_VIDEO_S = 45          # download (~9 s medidos para 38 MB) e, à parte, cada ffmpeg
ID_VIDEO = re.compile(r"^[A-Za-z0-9_-]{11}$")
CAMPOS_BUSCA = "%(id)s|%(duration)s|%(channel)s|%(title)s"
LICENCA = "desconhecida (YouTube)"
RISCO = "alto"
# Saídas do yt-dlp quando o YouTube limita ou bloqueia o IP (o 429 do bloqueio de 2026-09, spec §8). No
# download o downloader nativo diz "unable to download video data: HTTP Error 403: Forbidden" (ou 429):
# o 403 da googlevideo vale para a sessão inteira (URL estrangulada ou sem PO Token), não para um vídeo.
SINAIS_BLOQUEIO = ("HTTP Error 429", "Too Many Requests", "not a bot", "rate-limited", "rate limited",
                   "HTTP Error 403")
# Saídas de rede do yt-dlp: a busca que falha assim é transitória. Outra falha (módulo ausente, extractor
# quebrado) é o yt-dlp quebrado, e derruba o corte com a mensagem dele.
SINAIS_REDE = ("Unable to download", "urlopen error", "getaddrinfo failed", "Failed to resolve",
               "timed out", "Connection reset", "Connection refused", "Connection aborted",
               "Network is unreachable", "Temporary failure", "Remote end closed", "HTTP Error 5")
MAIOR_QUE_O_TETO = "larger than max-filesize"

rodar_busca_real: Rodar = rodar_com_prazo(PRAZO_BUSCA_S)
rodar_trecho_real: Rodar = rodar_com_prazo(PRAZO_VIDEO_S)


@dataclass(frozen=True)
class VideoCandidato:
    id: str
    dur: float
    canal: str
    titulo: str

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.id}"


def fonte(c: VideoCandidato) -> dict[str, Any]:
    """O registro da fonte do clipe escolhido (política de fontes A da spec)."""
    return {"fonte_url": c.url, "canal": c.canal, "titulo": c.titulo, "licenca": LICENCA, "risco": RISCO}


def bloqueado(saida: str) -> bool:
    """Puro. A saída do yt-dlp diz que o YouTube limitou ou bloqueou o IP."""
    return any(s.lower() in saida.lower() for s in SINAIS_BLOQUEIO)


def validar_id(vid: str) -> str:
    if not ID_VIDEO.fullmatch(vid):
        raise ErroRender(f"id de vídeo do YouTube inválido: {vid!r}")
    return vid


def args_busca(busca: str) -> list[str]:
    """`ytsearchN:` na frente: a busca nunca é lida como opção nem como URL."""
    return [*YT, "--flat-playlist", "--print", CAMPOS_BUSCA, f"ytsearch{N_RESULTADOS}:{busca}"]


def _candidato(linha: str) -> VideoCandidato | None:
    """Puro. Uma linha de `--print`, ou None se não é uma (aviso na saída) ou se a duração não serve
    (sem duração é live ou estreia)."""
    partes = linha.split("|", 3)
    if len(partes) != 4 or not ID_VIDEO.fullmatch(partes[0]):
        return None
    vid, dur, canal, titulo = partes
    try:
        segundos = float(dur)
    except ValueError:
        return None
    if not DUR_MIN_VIDEO_S <= segundos <= DUR_MAX_VIDEO_S:
        return None
    return VideoCandidato(vid, segundos, canal, titulo)


def ler_busca(saida: str, n: int) -> list[VideoCandidato]:
    """Puro. Até `n` candidatos de 15 s a 3 min, sem id repetido, na ordem da busca."""
    cands: list[VideoCandidato] = []
    for linha in saida.splitlines():
        c = _candidato(linha.strip())
        if c is not None and all(x.id != c.id for x in cands):
            cands.append(c)
    return cands[:n]


def _falha_yt(codigo: int, saida: str, passo: str) -> ErroRender:
    """Bloqueio do YouTube é ErroBusca (transitório); outra falha, ErroRender com o fim do log. Só
    olha a saída de quem falhou: a de sucesso traz títulos, e um título pode dizer "not a bot"."""
    if bloqueado(saida):
        return ErroBusca(f"{passo}: o YouTube limitou ou bloqueou o acesso: {saida[-CAUDA:]}")
    return ErroRender(f"{passo} falhou (código {codigo}): {saida[-CAUDA:]}")


def falha_de_rede(saida: str) -> bool:
    """Puro. A saída do yt-dlp que falhou é de rede (sem conexão, DNS, tempo, servidor 5xx)."""
    return any(s.lower() in saida.lower() for s in SINAIS_REDE)


def buscar_videos(busca: str, n: int = MAX_CANDIDATOS,
                  rodar: Rodar = rodar_busca_real) -> list[VideoCandidato]:
    """Nada achado é lista vazia. Prazo, bloqueio e rede são ErroBusca (transitório); outra falha
    (módulo ausente, extractor quebrado) é o yt-dlp quebrado: ErroRender, que derruba o corte."""
    passo = f"busca de vídeo '{busca}'"
    try:
        codigo, saida = rodar(args_busca(busca), None)
    except ErroRender as e:   # prazo estourado (processo.py)
        raise ErroBusca(f"{passo}: {e}") from e
    if codigo != 0:
        erro = _falha_yt(codigo, saida, passo)
        if isinstance(erro, ErroBusca) or not falha_de_rede(saida):
            raise erro
        raise ErroBusca(str(erro))
    return ler_busca(saida, n)

def args_video(c: VideoCandidato, molde: Path) -> list[str]:
    """yt-dlp baixa o vídeo inteiro pelo downloader nativo, só vídeo, até MAX_TAMANHO. `molde` leva
    `%(ext)s`: o contêiner vem do formato."""
    return [*YT, "--no-playlist", "--no-progress", "-f", FORMATO, "--max-filesize", MAX_TAMANHO,
            "-o", str(molde), "--", f"https://www.youtube.com/watch?v={validar_id(c.id)}"]


def _bruto(pasta: Path, stem: str) -> Path:
    achados = [p for p in pasta.glob(f"{stem}.*") if not p.name.endswith(".part")]
    if len(achados) != 1:
        raise ErroRender(f"yt-dlp não deixou um vídeo só em {pasta} ({[p.name for p in achados]})")
    return achados[0]


def _apagar_brutos(pasta: Path, stem: str) -> list[str]:
    """Apaga o vídeo baixado (e o `.part`); devolve os que o sistema não deixou apagar."""
    presos = []
    for resto in pasta.glob(f"{stem}.*"):
        try:
            resto.unlink(missing_ok=True)
        except OSError as e:   # Windows: antivírus ou indexador com o arquivo aberto
            presos.append(f"{resto} ({e})")
    return presos


def apagar_bruto(pasta: Path, stem: str) -> None:
    """Apaga `<stem>.*`; o que o sistema não deixa apagar é ErroRender com o caminho."""
    presos = _apagar_brutos(pasta, stem)
    if presos:
        raise ErroRender(f"não consegui apagar o vídeo baixado: {'; '.join(presos)}")


def _baixar(c: VideoCandidato, pasta: Path, stem: str, rodar: Rodar) -> Path:
    codigo, saida = rodar(args_video(c, pasta / f"{stem}.%(ext)s"), None)
    if MAIOR_QUE_O_TETO in saida:
        raise ErroRender(f"vídeo de {c.url} passa de {MAX_TAMANHO}: {saida[-CAUDA:]}")
    if codigo != 0:
        raise _falha_yt(codigo, saida, f"vídeo de {c.url}")
    return _bruto(pasta, stem)


def baixar_bruto(c: VideoCandidato, pasta: Path, stem: str, rodar: Rodar = rodar_trecho_real) -> Path:
    """O vídeo inteiro em `<pasta>/<stem>.<ext>`, que FICA: quem chama apaga com `apagar_bruto` depois
    de cortar o momento escolhido. Na falha, o que o yt-dlp deixou é apagado; o que não se deixa
    apagar não esconde o erro original (vira nota nele)."""
    pasta.mkdir(parents=True, exist_ok=True)
    apagar_bruto(pasta, stem)
    try:
        return _baixar(c, pasta, stem, rodar)
    except BaseException as e:
        presos = _apagar_brutos(pasta, stem)
        if presos:
            e.add_note(f"vídeo baixado não apagado: {'; '.join(presos)}")
        raise
