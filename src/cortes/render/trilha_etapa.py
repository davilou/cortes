"""Etapa da trilha no `montar_projeto` (spec trilha §6): resolve a cama (escolha do editor ou mood
do LLM), mede a voz do trecho, copia a cama para `assets/trilha.m4a` e devolve o HTML dos
`<audio>` e o registro do que foi usado."""
import shutil
from dataclasses import dataclass
from pathlib import Path

from cortes.detector import ChamarLLM
from cortes.render.corte import Corte
from cortes.render.edicao import SEM_TRILHA
from cortes.render.trilha import ARQUIVO_ASSET, clipes, ganho, html_trilha
from cortes.render.trilha_biblioteca import (
    Cama,
    MedirLufs,
    cama_do_mood,
    cama_por_id,
    ler_plano,
    medida_da_cama,
)
from cortes.render.trilha_mood import preparar_mood


@dataclass(frozen=True)
class TrilhaUsada:
    cama: str | None
    origem: str            # "auto" (LLM) ou "manual" (editor)
    motivo: str | None     # o do LLM, quando automática
    volume: float | None   # data-volume da cama


def _escolher(d: Path, c: Corte, texto: str, camas: list[Cama],
              chamar: ChamarLLM) -> tuple[Cama, str, str | None]:
    if c.edicoes.trilha is None:
        m = preparar_mood(d, texto, chamar)
        return cama_do_mood(camas, m.mood), "auto", m.motivo
    return cama_por_id(camas, c.edicoes.trilha), "manual", None


def preparar_trilha(d: Path, c: Corte, texto: str, dur: float, biblioteca: Path, chamar: ChamarLLM,
                    medir: MedirLufs) -> tuple[str, TrilhaUsada]:
    assets = d / "projeto" / "assets"
    if c.edicoes.trilha == SEM_TRILHA:
        (assets / ARQUIVO_ASSET).unlink(missing_ok=True)
        return "", TrilhaUsada(None, "manual", None, None)
    cama, origem, motivo = _escolher(d, c, texto, ler_plano(biblioteca), chamar)
    mc = medida_da_cama(cama, biblioteca, medir)
    volume = ganho(medir(assets / "trecho.mp4").lufs, mc.lufs)
    shutil.copyfile(cama.arquivo, assets / ARQUIVO_ASSET)
    html = html_trilha(clipes(dur, mc.duracao, cama.bpm), volume)
    return html, TrilhaUsada(cama.id, origem, motivo, round(volume, 6))
