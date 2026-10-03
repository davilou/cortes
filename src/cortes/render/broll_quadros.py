"""f4 B-roll, o que o ffmpeg tira do vídeo baixado (plano 2026-10-03-melhora-f4): os momentos
candidatos para a folha, o trecho do momento escolhido em tela cheia e os quadros dele para o editor;
e a foto de reserva em tela cheia, para a deixa literal sem vídeo.

Antes o trecho era cortado às cegas a 25% da duração — e no render real o meio dos 3 s da Macboot
era paisagem. Agora cada vídeo dá MOMENTOS candidatos de TRECHO_S, com 3 quadros cada na folha, e
a conferência escolhe o vídeo e o momento. Tudo local, pelo executor injetável.
"""
from collections.abc import Sequence
from pathlib import Path

from cortes.render.ilustracao import DUR_MAX_S
from cortes.render.processo import ErroRender, Rodar, exigir
from cortes.render.recorte import gerar_por_parcial

TRECHO_S = DUR_MAX_S        # o clipe mais longo que a deixa pode pedir
MOMENTOS = (0.15, 0.35, 0.55, 0.75)   # posições dos momentos no vídeo: passa da vinheta, espalha
FOLGA_FIM_S = 0.3           # a duração da busca é arredondada: o último momento acaba antes do fim
LARGURA, ALTURA = 1080, 1920
QUADROS_S = (0.1, TRECHO_S / 2, TRECHO_S - 0.2)   # início, meio e fim de um momento, para a folha
LARGURA_QUADRO, ALTURA_QUADRO = 360, 640          # 9:16, como o clipe aparece na tela
Quadros = tuple[Path, Path, Path]


def _cover(largura: int, altura: int) -> str:
    """Preenche o 9:16 cortando o centro do 16:9 (o #box-cheio do protótipo)."""
    return (f"scale={largura}:{altura}:force_original_aspect_ratio=increase,"
            f"crop={largura}:{altura},setsar=1")


_VF_QUADRO = f"{_cover(LARGURA_QUADRO, ALTURA_QUADRO)},format=yuvj420p"
_SAIDA = ["-an", "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
          "-movflags", "+faststart"]


def inicios_momentos(dur: float) -> tuple[float, ...]:
    """Puro. O início de cada momento de TRECHO_S: as posições MOMENTOS da duração, sem passar do fim."""
    ultimo = max(0.0, dur - TRECHO_S - FOLGA_FIM_S)
    return tuple(round(min(p * dur, ultimo), 3) for p in MOMENTOS)


def args_cheio(bruto: Path, destino: Path, inicio: float) -> list[str]:
    """Puro. Os TRECHO_S a partir de `inicio`, em cover 1080×1920, sem áudio."""
    return ["ffmpeg", "-v", "error", "-y", "-ss", f"{inicio:.3f}", "-i", str(bruto),
            "-t", f"{TRECHO_S:.3f}", "-vf", _cover(LARGURA, ALTURA), *_SAIDA, str(destino)]


def cortar_momento(bruto: Path, inicio: float, destino: Path, rodar: Rodar) -> None:
    """`destino` (.mp4): o momento escolhido em tela cheia; só aparece inteiro (`.parcial`)."""
    gerar_por_parcial(destino, lambda p: args_cheio(bruto, p, inicio), rodar,
                      f"tela cheia de {bruto.name} em {inicio:.1f} s")


def quadros_args(entrada: Path, tempos: Sequence[float], destinos: Sequence[Path]) -> list[str]:
    """Puro. Um ffmpeg só, um quadro de `entrada` em cada tempo, em JPEG 9:16 de ALTURA_QUADRO px
    (cover: o que o clipe mostra na tela). Encoder sem threads e JPEG em faixa cheia: no render real
    o mjpeg com threads de quadro falhou ("ff_frame_thread_encoder_init failed", "Non full-range
    YUV is non-standard") em parte das saídas."""
    entradas: list[str] = []
    saidas: list[str] = []
    for i, (t, d) in enumerate(zip(tempos, destinos, strict=True)):
        entradas += ["-ss", f"{t:.2f}", "-i", str(entrada)]
        saidas += ["-map", f"{i}:v", "-frames:v", "1", "-vf", _VF_QUADRO, "-threads", "1", "-q:v", "3",
                   str(d)]
    return ["ffmpeg", "-v", "error", "-y", *entradas, *saidas]


def _gravar_quadros(entrada: Path, tempos: Sequence[float], destinos: Sequence[Path], rodar: Rodar) -> None:
    """Quadro que não saiu (vídeo curto demais) é erro; quadro velho não passa por novo."""
    for d in destinos:
        d.unlink(missing_ok=True)
    exigir(rodar, quadros_args(entrada, tempos, destinos), None, f"quadros de {entrada.name}")
    faltam = [d.name for d in destinos if not d.exists() or d.stat().st_size == 0]
    if faltam:
        raise ErroRender(f"quadros de {entrada.name}: ffmpeg não gerou {', '.join(faltam)}")


def _tres(prefixo: Path) -> Quadros:
    return (prefixo.with_name(f"{prefixo.name}-q1.jpg"), prefixo.with_name(f"{prefixo.name}-q2.jpg"),
            prefixo.with_name(f"{prefixo.name}-q3.jpg"))


def extrair_quadros(trecho: Path, prefixo: Path, rodar: Rodar) -> Quadros:
    """`<prefixo>-q1.jpg` a `-q3.jpg`: início, meio e fim do trecho cortado (o q2 é a miniatura)."""
    destinos = _tres(prefixo)
    _gravar_quadros(trecho, QUADROS_S, destinos, rodar)
    return destinos


def extrair_momentos(bruto: Path, inicios: Sequence[float], prefixo: Path,
                     rodar: Rodar) -> tuple[Quadros, ...]:
    """`<prefixo>-m<p>-q1.jpg` a `-q3.jpg` de cada momento, direto do vídeo baixado, um ffmpeg por
    momento: com 12 entradas de 1080p e 12 saídas num ffmpeg só, parte das saídas falhou no render
    real de 2026-10-03; 3 por vez é o que os quadros do trecho sempre fizeram."""
    momentos = tuple(_tres(prefixo.with_name(f"{prefixo.name}-m{p}")) for p in range(1, len(inicios) + 1))
    for ini, quadros in zip(inicios, momentos, strict=True):
        _gravar_quadros(bruto, [ini + t for t in QUADROS_S], quadros, rodar)
    return momentos


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
