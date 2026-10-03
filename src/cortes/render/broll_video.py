"""f4 B-roll, passo 2 — vídeo do YouTube: busca, vídeo inteiro baixado e cortado em 3 s de tela cheia
e os quadros da folha (plano 2026-10-03-broll-automatico, Task 2). Protótipo: `testes/comum/buscar_broll.py`.

Tudo passa pelo executor injetável (`processo.Rodar`), com prazo próprio: nada de rede no check. O
YouTube já bloqueou este IP uma vez (spec §8): 429 ou "confirme que não é um robô" vira `ErroBusca`,
a falha transitória da deixa, e nunca é repetido em laço aqui. Quem chama faz busca e download em
série, sem paralelo no YouTube.

Também a foto de reserva em tela cheia (`args_foto_cheia`), para a deixa literal sem vídeo.
"""
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cortes.render.ilustracao_imagens import ErroBusca
from cortes.render.processo import CAUDA, ErroRender, Rodar, exigir, rodar_com_prazo
from cortes.render.recorte import gerar_por_parcial

YT = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-warnings"]
N_RESULTADOS = 15           # resultados pedidos à busca (uma página só); o filtro de duração descarta parte
DUR_MIN_VIDEO_S = 15.0      # menos que isso é Short ou vinheta
DUR_MAX_VIDEO_S = 3 * 60.0  # o vídeo é baixado inteiro: acima disso o download passa do prazo
MAX_CANDIDATOS = 2          # por deixa
TRECHO_S = 3.0
# O vídeo inteiro pelo downloader nativo do yt-dlp, só vídeo, e o ffmpeg corta os TRECHO_S local. Medido
# em 2026-10-03: `--download-sections` (o ffmpeg lendo a seção por HTTP) levava ~45 s por 5 s de vídeo e
# estourava o prazo em metade dos casos; o vídeo inteiro de 71 s/1080p/38 MB veio em 9 s (spec §11).
# O 720p sai visivelmente mais mole no 1080×1920, então fica 1080p.
POSICAO_TRECHO = 0.25       # o trecho começa a 25% do vídeo: passa da vinheta e da apresentação
FORMATO = "bv*[height<=1080][ext=mp4]/bv*[height<=1080]"   # só vídeo, sem áudio, até 1080p
MAX_TAMANHO = "120M"        # 3 min de 1080p só-vídeo ficam bem abaixo; acima é bitrate de 4K disfarçado
PRAZO_BUSCA_S = 30
PRAZO_VIDEO_S = 45          # download (~9 s medidos para 38 MB) e, à parte, o ffmpeg dos 3 s
LARGURA, ALTURA = 1080, 1920
QUADROS_S = (0.1, TRECHO_S / 2, TRECHO_S - 0.2)   # início, meio e fim do trecho, para a folha
ALTURA_QUADRO = 640
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
# cover: preenche o 9:16 cortando o centro do 16:9 (o #box-cheio do protótipo)
_VF_CHEIO = (f"scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,"
             f"crop={LARGURA}:{ALTURA},setsar=1")
_SAIDA = ["-an", "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
          "-movflags", "+faststart"]

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


def inicio_trecho(c: VideoCandidato) -> float:
    return c.dur * POSICAO_TRECHO


def args_video(c: VideoCandidato, molde: Path) -> list[str]:
    """yt-dlp baixa o vídeo inteiro pelo downloader nativo, só vídeo, até MAX_TAMANHO. `molde` leva
    `%(ext)s`: o contêiner vem do formato."""
    return [*YT, "--no-playlist", "--no-progress", "-f", FORMATO, "--max-filesize", MAX_TAMANHO,
            "-o", str(molde), "--", f"https://www.youtube.com/watch?v={validar_id(c.id)}"]


def args_cheio(bruto: Path, destino: Path, c: VideoCandidato) -> list[str]:
    """Puro. Os TRECHO_S a partir de POSICAO_TRECHO do vídeo, em cover 1080×1920, sem áudio."""
    return ["ffmpeg", "-v", "error", "-y", "-ss", f"{inicio_trecho(c):.3f}", "-i", str(bruto),
            "-t", f"{TRECHO_S:.3f}", "-vf", _VF_CHEIO, *_SAIDA, str(destino)]


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


def _exigir_apagados(pasta: Path, stem: str) -> None:
    presos = _apagar_brutos(pasta, stem)
    if presos:
        raise ErroRender(f"não consegui apagar o vídeo baixado: {'; '.join(presos)}")


def _baixar_e_cortar(c: VideoCandidato, destino: Path, stem: str, rodar: Rodar) -> None:
    codigo, saida = rodar(args_video(c, destino.parent / f"{stem}.%(ext)s"), None)
    if MAIOR_QUE_O_TETO in saida:
        raise ErroRender(f"vídeo de {c.url} passa de {MAX_TAMANHO}: {saida[-CAUDA:]}")
    if codigo != 0:
        raise _falha_yt(codigo, saida, f"vídeo de {c.url}")
    bruto = _bruto(destino.parent, stem)
    gerar_por_parcial(destino, lambda p: args_cheio(bruto, p, c), rodar, f"tela cheia de {c.url}")


def baixar_trecho(c: VideoCandidato, destino: Path, rodar: Rodar = rodar_trecho_real) -> None:
    """`destino` (.mp4): o trecho de TRECHO_S em 1080×1920, cover com corte central, sem áudio. O
    vídeo baixado é apagado no fim, com ou sem erro; o MP4 só aparece inteiro (`.parcial`). Vídeo
    que não se deixa apagar não esconde o erro original (vira nota nele)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    stem = f"{destino.stem}.bruto"
    _exigir_apagados(destino.parent, stem)
    try:
        _baixar_e_cortar(c, destino, stem, rodar)
    except BaseException as e:
        presos = _apagar_brutos(destino.parent, stem)
        if presos:
            e.add_note(f"vídeo baixado não apagado: {'; '.join(presos)}")
        raise
    _exigir_apagados(destino.parent, stem)


def quadros_args(trecho: Path, destinos: tuple[Path, Path, Path]) -> list[str]:
    """Puro. Um ffmpeg só, os 3 quadros do trecho (QUADROS_S) em JPEG de ALTURA_QUADRO px."""
    entradas: list[str] = []
    saidas: list[str] = []
    for i, (t, d) in enumerate(zip(QUADROS_S, destinos, strict=True)):
        entradas += ["-ss", f"{t:.2f}", "-i", str(trecho)]
        saidas += ["-map", f"{i}:v", "-frames:v", "1", "-vf", f"scale=-2:{ALTURA_QUADRO}", "-q:v", "3",
                   str(d)]
    return ["ffmpeg", "-v", "error", "-y", *entradas, *saidas]


def extrair_quadros(trecho: Path, prefixo: Path, rodar: Rodar) -> tuple[Path, Path, Path]:
    """`<prefixo>-q1.jpg` a `-q3.jpg`. Quadro que não saiu (trecho curto demais) é erro."""
    destinos = (prefixo.with_name(f"{prefixo.name}-q1.jpg"), prefixo.with_name(f"{prefixo.name}-q2.jpg"),
                prefixo.with_name(f"{prefixo.name}-q3.jpg"))
    for d in destinos:
        d.unlink(missing_ok=True)   # quadro de outro trecho não pode passar por deste
    exigir(rodar, quadros_args(trecho, destinos), None, f"quadros de {trecho.name}")
    faltam = [d.name for d in destinos if not d.exists() or d.stat().st_size == 0]
    if faltam:
        raise ErroRender(f"quadros de {trecho.name}: ffmpeg não gerou {', '.join(faltam)}")
    return destinos


def args_foto_cheia(foto: Path, destino: Path) -> list[str]:
    """Puro. A foto inteira (contain) sobre ela mesma desfocada e escurecida, em 1080×1920: o
    produto não é cortado e a tela não fica com faixa preta (mesma ideia do fundo do f8)."""
    fundo = (f"[0:v]scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,crop={LARGURA}:{ALTURA},"
             "boxblur=40:2,colorchannelmixer=rr=0.55:gg=0.55:bb=0.55[fundo]")
    frente = f"[1:v]scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=decrease[frente]"
    juntar = "[fundo][frente]overlay=(W-w)/2:(H-h)/2,setsar=1[cheia]"
    return ["ffmpeg", "-v", "error", "-y", "-i", str(foto), "-i", str(foto),
            "-filter_complex", ";".join([fundo, frente, juntar]), "-map", "[cheia]", "-frames:v", "1",
            "-q:v", "2", str(destino)]


def foto_cheia(foto: Path, destino: Path, rodar: Rodar) -> None:
    """Grava em `<nome>.parcial.jpg` e só renomeia no fim."""
    parcial = destino.with_name(destino.stem + ".parcial.jpg")
    try:
        exigir(rodar, args_foto_cheia(foto, parcial), None, f"foto em tela cheia de {foto.name}")
        if not parcial.exists() or parcial.stat().st_size == 0:
            raise ErroRender(f"foto em tela cheia de {foto.name}: ffmpeg não gerou a imagem")
    except ErroRender:
        parcial.unlink(missing_ok=True)
        raise
    parcial.replace(destino)
