"""Miniatura de uma pessoa num plano (editor, quem aparece): o quadro do meio do plano, recortado
num quadrado em volta do rosto. ffmpeg atrás do executor injetável."""
from pathlib import Path

from cortes.render.processo import ErroRender, Rodar, exigir
from cortes.render.rosto import Pessoa, Plano

LADO_PX = 160          # lado da miniatura na tela
FATOR = 3.2            # o quadrado cobre ~3,2× o raio do rosto (cabeça e um pouco de ombro)


def args_miniatura(trecho: Path, destino: Path, t: float, p: Pessoa, largura: int, altura: int) -> list[str]:
    lado = int(min(largura, altura, max(LADO_PX, FATOR * p.r)))
    x0 = int(min(max(0, round(p.x - lado / 2)), largura - lado))
    y0 = int(min(max(0, round(p.y - lado / 2)), altura - lado))
    return ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(trecho), "-frames:v", "1",
            "-vf", f"crop={lado}:{lado}:{x0}:{y0},scale={LADO_PX}:{LADO_PX}", "-q:v", "4", str(destino)]


def gerar_miniatura(trecho: Path, destino: Path, plano: Plano, j: int, largura: int, altura: int,
                    rodar: Rodar) -> None:
    """Grava em `<nome>.parcial.jpg` e só renomeia para o destino no fim: uma falha no meio (ou um
    pedido concorrente pela mesma miniatura) nunca deixa um arquivo pela metade no lugar final.
    ffmpeg que sai 0 sem gerar o arquivo (ou gera vazio) é tão erro quanto saída != 0 (item 2)."""
    if not 0 <= j < len(plano.pessoas):
        raise ErroRender(f"plano {plano.k}: pessoa {j} não existe (há {len(plano.pessoas)})")
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(".parcial.jpg")
    t = (plano.ini + plano.fim) / 2
    try:
        args = args_miniatura(trecho, parcial, t, plano.pessoas[j], largura, altura)
        exigir(rodar, args, None, "miniatura")
        if not parcial.exists() or parcial.stat().st_size == 0:
            raise ErroRender(f"miniatura do plano {plano.k} pessoa {j}: ffmpeg não gerou o arquivo")
        parcial.replace(destino)
    except ErroRender:
        parcial.unlink(missing_ok=True)
        raise
