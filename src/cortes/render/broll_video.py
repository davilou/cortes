"""f4 B-roll, passo 2 — vídeo do YouTube: busca, trecho de 3 s em tela cheia e os quadros da folha
(plano 2026-10-03-broll-automatico, Task 2). Protótipo: `testes/comum/buscar_broll.py`.

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
N_RESULTADOS = 8            # resultados pedidos à busca; o filtro de duração descarta parte
DUR_MIN_VIDEO_S = 20.0      # menos que isso é Short ou vinheta
DUR_MAX_VIDEO_S = 20 * 60.0  # mais que isso é live, aula ou compilação
MAX_CANDIDATOS = 2          # por deixa: cada candidato custa ~45 s de download (medido em 2026-10-03)
TRECHO_S = 3.0
# O yt-dlp baixa uma seção maior, sem `--force-keyframes-at-cuts`: a seção começa no keyframe antes
# do início pedido, e o ffmpeg de `args_cheio` (que recodifica de qualquer jeito) corta os TRECHO_S.
# Medido em 2026-10-03: ~43 s no yt-dlp com ou sem a recodificação e com 1080p ou 720p — o tempo é da
# leitura HTTP da seção, não do tamanho; o 720p sai visivelmente mais mole no 1080×1920, então fica 1080p.
# URL direta (`yt-dlp -g`) + `ffmpeg -ss <ini> -i <url>` não acelera: é o mesmo caminho que o yt-dlp usa
# na seção, e com ou sem os cabeçalhos dele passou de 90 s sem gravar nada (2026-10-03). Suspeita: sem runtime
# JS o yt-dlp não resolve o desafio "n" e a URL vem estrangulada (spec §11, tempo do trecho).
SECAO_S = 5.0
POSICAO_TRECHO = 0.25       # o trecho começa a 25% do vídeo: passa da vinheta e da apresentação
FORMATO = "bv*[height<=1080][ext=mp4]/bv*[height<=1080]"   # só vídeo, sem áudio, até 1080p
PRAZO_BUSCA_S = 30
PRAZO_TRECHO_S = 90         # ~45 s medidos (yt-dlp + ffmpeg); 60 s deixava folga de 25%
LARGURA, ALTURA = 1080, 1920
QUADROS_S = (0.1, TRECHO_S / 2, TRECHO_S - 0.2)   # início, meio e fim do trecho, para a folha
ALTURA_QUADRO = 640
ID_VIDEO = re.compile(r"^[A-Za-z0-9_-]{11}$")
CAMPOS_BUSCA = "%(id)s|%(duration)s|%(channel)s|%(title)s"
LICENCA = "desconhecida (YouTube)"
RISCO = "alto"
# Saídas do yt-dlp quando o YouTube limita ou bloqueia o IP (o 429 do bloqueio de 2026-09, spec §8)
SINAIS_BLOQUEIO = ("HTTP Error 429", "Too Many Requests", "not a bot", "rate-limited", "rate limited")
# cover: preenche o 9:16 cortando o centro do 16:9 (o #box-cheio do protótipo)
_VF_CHEIO = (f"scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,"
             f"crop={LARGURA}:{ALTURA},setsar=1")
_SAIDA = ["-an", "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
          "-movflags", "+faststart"]

rodar_busca_real: Rodar = rodar_com_prazo(PRAZO_BUSCA_S)
rodar_trecho_real: Rodar = rodar_com_prazo(PRAZO_TRECHO_S)


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
    """Puro. Até `n` candidatos de 20 s a 20 min, sem id repetido, na ordem da busca."""
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


def buscar_videos(busca: str, n: int = MAX_CANDIDATOS,
                  rodar: Rodar = rodar_busca_real) -> list[VideoCandidato]:
    """Nada achado é lista vazia; busca que falha (prazo, rede, bloqueio) é ErroBusca."""
    passo = f"busca de vídeo '{busca}'"
    try:
        codigo, saida = rodar(args_busca(busca), None)
    except ErroRender as e:   # prazo estourado (processo.py)
        raise ErroBusca(f"{passo}: {e}") from e
    if codigo != 0:
        erro = _falha_yt(codigo, saida, passo)
        raise erro if isinstance(erro, ErroBusca) else ErroBusca(str(erro))
    return ler_busca(saida, n)


def inicio_trecho(c: VideoCandidato) -> int:
    return int(c.dur * POSICAO_TRECHO)


def args_trecho(c: VideoCandidato, molde: Path) -> list[str]:
    """yt-dlp baixa só a seção (SECAO_S), só vídeo, sem recodificar. `molde` leva `%(ext)s`: o
    contêiner vem do formato."""
    ini = inicio_trecho(c)
    return [*YT, "--no-playlist", "--no-progress", "-f", FORMATO, "--download-sections",
            f"*{ini}-{ini + SECAO_S:.0f}", "-o", str(molde),
            "--", f"https://www.youtube.com/watch?v={validar_id(c.id)}"]


def args_cheio(bruto: Path, destino: Path) -> list[str]:
    return ["ffmpeg", "-v", "error", "-y", "-i", str(bruto), "-t", f"{TRECHO_S:.3f}", "-vf", _VF_CHEIO,
            *_SAIDA, str(destino)]


def _bruto(pasta: Path, stem: str) -> Path:
    achados = [p for p in pasta.glob(f"{stem}.*") if not p.name.endswith(".part")]
    if len(achados) != 1:
        raise ErroRender(f"yt-dlp não deixou um trecho só em {pasta} ({[p.name for p in achados]})")
    return achados[0]


def baixar_trecho(c: VideoCandidato, destino: Path, rodar: Rodar = rodar_trecho_real) -> None:
    """`destino` (.mp4): o trecho de TRECHO_S em 1080×1920, cover com corte central, sem áudio. O
    bruto do yt-dlp é apagado no fim, com ou sem erro; o MP4 só aparece inteiro (`.parcial`)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    stem = f"{destino.stem}.bruto"
    for velho in destino.parent.glob(f"{stem}.*"):
        velho.unlink()
    try:
        codigo, saida = rodar(args_trecho(c, destino.parent / f"{stem}.%(ext)s"), None)
        if codigo != 0:
            raise _falha_yt(codigo, saida, f"trecho de {c.url}")
        bruto = _bruto(destino.parent, stem)
        gerar_por_parcial(destino, lambda p: args_cheio(bruto, p), rodar, f"tela cheia de {c.url}")
    finally:
        for resto in destino.parent.glob(f"{stem}.*"):
            resto.unlink()


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
