"""f10 Motion v2, a cabeça que sai por cima do card: o trecho sem o fundo (`recorte.webm`, VP9 com
alfa), gerado na GPU por render/visao/recorte_fundo.py no Python do ComfyUI.

Como o fundo desfocado do f8 (render/assets.py), só depende do trecho: é gerado se faltar e apagado
quando o trecho é refeito. Sem o modelo ou sem CUDA o corte para com a causa — na CPU o recorte de
um minuto leva ~20 min e travaria a fila de render.
"""
from pathlib import Path

from cortes.render.processo import ErroRender, Rodar
from cortes.render.recorte import gerar_por_parcial

RECORTE = "recorte.webm"
SCRIPT = Path("render") / "visao" / "recorte_fundo.py"
MODELO = Path.home() / ".u2net" / "u2net_human_seg.onnx"   # o rembg baixa aqui


def args_recorte_fundo(py_visao: Path, script: Path, trecho: Path, modelo: Path, destino: Path) -> list[str]:
    return [str(py_visao), str(script), str(trecho), str(modelo), str(destino)]


def preparar_recorte(assets: Path, raiz: Path, py_visao: Path, modelo: Path, rodar: Rodar) -> None:
    """`assets` é a pasta do projeto do corte, onde já está `trecho.mp4`."""
    if (assets / RECORTE).exists():
        return
    if not modelo.exists():
        raise ErroRender(f"recorte da cabeça: modelo {modelo} não existe (o rembg baixa o "
                         "u2net_human_seg em ~/.u2net)")
    trecho = assets / "trecho.mp4"
    gerar_por_parcial(assets / RECORTE,
                      lambda p: args_recorte_fundo(py_visao, raiz / SCRIPT, trecho, modelo, p),
                      rodar, "recorte da cabeça")
