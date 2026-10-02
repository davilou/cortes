from pathlib import Path

from cortes.producao.previas import Previas, SituacaoPrevia
from cortes.render.corte import Corte, gravar_corte, novo_corte, pasta_corte


def episodio(tmp: Path) -> Path:
    pasta = tmp / "episodios" / "abcdefghijk"
    gravar_corte(pasta_corte(pasta, 0), novo_corte(0, {"inicio": 1.0, "fim": 9.0, "titulo": "T"}, "f7"))
    return pasta


def test_pedido_vira_pronta(tmp_path: Path) -> None:
    episodio(tmp_path)
    feitos: list[int] = []
    p = Previas(tmp_path, lambda pasta, c: feitos.append(c.indice))
    p.pedir("abcdefghijk", 0)
    assert p.situacao("abcdefghijk", 0) == SituacaoPrevia("preparando") and p.preparando("abcdefghijk", 0)
    p.processar("abcdefghijk", 0)
    assert feitos == [0] and p.situacao("abcdefghijk", 0) == SituacaoPrevia("pronta")


def test_erro_fica_visivel(tmp_path: Path) -> None:
    episodio(tmp_path)

    def falha(pasta: Path, c: Corte) -> None:
        raise RuntimeError("ffmpeg sumiu")

    p = Previas(tmp_path, falha)
    p.pedir("abcdefghijk", 0)
    p.processar("abcdefghijk", 0)
    assert p.situacao("abcdefghijk", 0) == SituacaoPrevia("erro", "RuntimeError: ffmpeg sumiu")


def test_pedido_durante_o_preparo_continua_preparando(tmp_path: Path) -> None:
    episodio(tmp_path)
    p = Previas(tmp_path, lambda pasta, c: p.pedir("abcdefghijk", 0))
    p.pedir("abcdefghijk", 0)
    p._proximo()   # retira da fila como a thread faria
    p.processar("abcdefghijk", 0)
    assert p.preparando("abcdefghijk", 0)


def test_sem_pedido_nao_ha_situacao(tmp_path: Path) -> None:
    assert Previas(tmp_path, lambda pasta, c: None).situacao("abcdefghijk", 0) is None
