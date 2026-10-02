"""Etapa `render` do episódio (spec produção §4.4): planeja os N melhores uma vez e renderiza, um
por vez, os cortes na fila. Um corte que falha fica em erro com a causa no corte.json e os outros
seguem; a etapa só fica em erro se nem o planejamento der certo.

"Renderizar" manual grava um corte `na_fila` e enfileira o episódio; se a etapa já tinha fechado
(ok), `reabrir_render` — o gancho `antes` da fila, que roda na thread da fila — reabre a etapa.
Por rodar na mesma thread que marca a etapa como ok, não há corrida entre os dois.
"""
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from cortes.producao import curadoria
from cortes.producao.estado import EstadoEpisodio, gravar, ler, marcar
from cortes.render.corte import (
    PLANEJADO,
    Corte,
    concluir,
    cortes_do_episodio,
    falhar,
    gravar_corte,
    iniciar,
    pasta_corte,
    planejar,
    proximo,
)
from cortes.render.pipeline import DepRender, renderizar_corte

Renderizar = Callable[[Path, Corte, Path, DepRender], None]


def rodar_render(pasta: Path, e: EstadoEpisodio, raiz: Path, dep: DepRender,
                 renderizar: Renderizar = renderizar_corte) -> None:
    if not (pasta / "cortes" / PLANEJADO).exists():
        planejar(pasta, e.formato, e.n_shorts, curadoria.candidatos(pasta))
    while (c := proximo(cortes_do_episodio(pasta))) is not None:   # relê o disco: pega pedido novo
        _um(pasta, c, raiz, dep, renderizar)


def _um(pasta: Path, c: Corte, raiz: Path, dep: DepRender, renderizar: Renderizar) -> None:
    d = pasta_corte(pasta, c.indice)
    gravar_corte(d, iniciar(c))
    try:
        renderizar(pasta, c, raiz, dep)
    except Exception as ex:   # um corte ruim não para os outros; a causa fica visível no corte.json
        traceback.print_exc()
        gravar_corte(d, falhar(c, f"{type(ex).__name__}: {ex}"))
        return
    gravar_corte(d, concluir(c))


def render_pendente(e: EstadoEpisodio, cortes: list[Corte]) -> bool:
    return e.etapas["render"].situacao == "ok" and proximo(cortes) is not None


def reabrir_render(pasta: Path, agora: datetime) -> None:
    e = ler(pasta)
    if render_pendente(e, cortes_do_episodio(pasta)):
        gravar(pasta, marcar(e, "render", "pendente", agora))
