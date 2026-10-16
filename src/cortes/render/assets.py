"""Assets que alguns formatos usam além do trecho (spec produção §4.1), gerados no ffmpeg.

- f8 (desfoque): `fundo.mp4`, o próprio trecho a 540×960 e desfocado. O blur em tempo real do
  HyperFrames sobre o vídeo cheio estourava o tempo de carga (testes/comum/formatos/desfoque.tpl).
- f5 (gameplay): `gameplay.mp4`, um vídeo de `biblioteca/gameplay/` a 1708×960, repetido até a
  duração do Short (o gameplay de origem pode ser mais curto que o Short).
- f10 (Motion v2): os efeitos sonoros de `biblioteca/sfx/` (`sfx-<nome>.wav`, render/motion2.py),
  copiados como estão. O recorte da cabeça precisa da GPU e fica em render/recorte_fundo.py.

Só dependem do trecho: são gerados se faltarem e apagados quando o trecho é refeito (pipeline).
"""
import shutil
from pathlib import Path

from cortes.render.motion2 import SFX
from cortes.render.processo import ErroRender, Rodar
from cortes.render.recorte import gerar_por_parcial
from cortes.render.recorte_fundo import RECORTE

FUNDO = "fundo.mp4"
GAMEPLAY = "gameplay.mp4"
PASTA_GAMEPLAY = Path("biblioteca") / "gameplay"
PASTA_SFX = Path("biblioteca") / "sfx"
_VF_FUNDO = "scale=540:960:force_original_aspect_ratio=increase,crop=540:960,boxblur=20:2"
# 1708×960: a metade de baixo (1080×960) com o gameplay 16:9 centrado (template: left -314px).
# O crop protege de um gameplay que não seja 16:9 (sem ele, a imagem esticaria).
_VF_GAMEPLAY = "scale=1708:960:force_original_aspect_ratio=increase,crop=1708:960"
_SAIDA = ["-an", "-c:v", "libx264", "-crf", "20", "-preset", "fast", "-pix_fmt", "yuv420p"]


def args_fundo(trecho: Path, destino: Path) -> list[str]:
    return ["ffmpeg", "-v", "error", "-y", "-i", str(trecho), "-vf", _VF_FUNDO, *_SAIDA, str(destino)]


def args_gameplay(fonte: Path, destino: Path, dur: float) -> list[str]:
    return ["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-i", str(fonte), "-t", f"{dur:.3f}",
            "-vf", _VF_GAMEPLAY, *_SAIDA, str(destino)]


def escolher_gameplay(pasta: Path, indice: int) -> Path:
    """Determinística: o mesmo corte pega sempre o mesmo vídeo (enquanto a biblioteca não mudar)."""
    videos = sorted(pasta.glob("*.mp4")) if pasta.is_dir() else []
    if not videos:
        raise ErroRender("sem gameplay em biblioteca/gameplay: ponha um .mp4 lá")
    return videos[indice % len(videos)]


def preparar_assets(assets: Path, formato: str, indice: int, dur: float, raiz: Path, rodar: Rodar) -> None:
    """`assets` é a pasta do projeto do corte, onde já está `trecho.mp4`."""
    if formato == "f8" and not (assets / FUNDO).exists():
        gerar_por_parcial(assets / FUNDO, lambda p: args_fundo(assets / "trecho.mp4", p), rodar,
                          "fundo desfocado")
    if formato == "f5" and not (assets / GAMEPLAY).exists():
        fonte = escolher_gameplay(raiz / PASTA_GAMEPLAY, indice)
        gerar_por_parcial(assets / GAMEPLAY, lambda p: args_gameplay(fonte, p, dur), rodar, "gameplay")
    if formato == "f10":
        copiar_sfx(raiz / PASTA_SFX, assets)


def copiar_sfx(pasta: Path, assets: Path) -> None:
    for nome in SFX:
        destino = assets / f"sfx-{nome}.wav"
        if destino.exists():
            continue
        fonte = pasta / f"{nome}.wav"
        if not fonte.exists():
            raise ErroRender(f"efeito sonoro {fonte} não existe (biblioteca/sfx/LEIAME.md diz como gerar)")
        shutil.copyfile(fonte, destino)


def apagar_clipes(assets: Path) -> None:
    """Os clipes do f4 (`broll-<k>.mp4|jpg`) e os cartões do antigo f9 (`ilus-<k>.jpg`)."""
    for velho in [*assets.glob("broll-*.mp4"), *assets.glob("broll-*.jpg"), *assets.glob("ilus-*.jpg")]:
        velho.unlink()


def apagar_assets(assets: Path) -> None:
    """Também os clipes do f4 (vêm das deixas da fala do trecho anterior) e o recorte do f10."""
    for nome in (FUNDO, GAMEPLAY, RECORTE):
        (assets / nome).unlink(missing_ok=True)
    apagar_clipes(assets)
