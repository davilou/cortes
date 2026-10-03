import json
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from cortes.producao.estado import ErroProducao, gravar, ler, marcar, novo
from cortes.producao.fila import Fila
from cortes.producao.render import reabrir_render, render_pendente, rodar_render
from cortes.producao.rotas_cortes import cancelar_render
from cortes.render.corte import Corte, cortes_do_episodio, gravar_corte, novo_corte, pasta_corte
from cortes.render.pipeline import DepRender

AGORA = datetime(2026, 10, 2, 9)
DEP = DepRender(Path("py"), Path("m.onnx"), "npx")
CANDS = [{"inicio": 10.0, "fim": 40.0, "titulo": "A", "nota_final": 50.0},
         {"inicio": 50.0, "fim": 80.0, "titulo": "B", "nota_final": 90.0},
         {"inicio": 90.0, "fim": 120.0, "titulo": "C", "nota_final": 70.0}]


def episodio(tmp: Path) -> Path:
    pasta = tmp / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    e = novo("abcdefghijk", "https://youtu.be/abcdefghijk", "financas", "f7", AGORA)
    for nome in ("video", "legenda", "sinais", "momentos"):
        e = marcar(e, nome, "ok", AGORA)
    gravar(pasta, e)
    (pasta / "candidatos.json").write_text(json.dumps(CANDS), encoding="utf-8")
    return pasta


def pedir(pasta: Path, *indices: int) -> None:
    for i in indices:
        gravar_corte(pasta_corte(pasta, i), novo_corte(i, CANDS[i], "f7"))


def test_episodio_novo_nao_ganha_corte_sozinho(tmp_path: Path) -> None:
    pasta, feitos = episodio(tmp_path), []
    rodar_render(pasta, ler(pasta), tmp_path, DEP, threading.Lock(),
                 lambda p, c, r, d: feitos.append(c.indice))
    assert feitos == [] and cortes_do_episodio(pasta) == []


def test_planejado_json_antigo_e_ignorado(tmp_path: Path) -> None:
    pasta, feitos = episodio(tmp_path), []
    (pasta / "cortes").mkdir()
    (pasta / "cortes" / "planejado.json").write_text('{"n": 5, "formato": "f7"}', encoding="utf-8")
    rodar_render(pasta, ler(pasta), tmp_path, DEP, threading.Lock(),
                 lambda p, c, r, d: feitos.append(c.indice))
    assert feitos == [] and cortes_do_episodio(pasta) == []


def test_renderiza_so_o_pedido_um_por_vez(tmp_path: Path) -> None:
    pasta, feitos = episodio(tmp_path), []
    pedir(pasta, 2, 0)

    def falso(p: Path, c: Corte, raiz: Path, dep: DepRender) -> None:
        feitos.append((c.indice, c.status))

    rodar_render(pasta, ler(pasta), tmp_path, DEP, threading.Lock(), falso)
    assert feitos == [(0, "renderizando"), (2, "renderizando")]
    cortes = [(c.indice, c.status, c.versao) for c in cortes_do_episodio(pasta)]
    assert cortes == [(0, "pronto", 1), (2, "pronto", 1)]


def test_um_corte_que_falha_nao_para_os_outros(tmp_path: Path) -> None:
    pasta = episodio(tmp_path)
    pedir(pasta, 1, 2)

    def falso(p: Path, c: Corte, raiz: Path, dep: DepRender) -> None:
        if c.indice == 1:
            raise RuntimeError("npx sumiu")

    rodar_render(pasta, ler(pasta), tmp_path, DEP, threading.Lock(), falso)
    um, dois = cortes_do_episodio(pasta)
    assert um.status == "erro" and um.erro == "RuntimeError: npx sumiu" and dois.status == "pronto"


def test_reabre_a_etapa_quando_um_render_foi_pedido_depois(tmp_path: Path) -> None:
    pasta = episodio(tmp_path)
    gravar(pasta, marcar(ler(pasta), "render", "ok", AGORA))
    assert not render_pendente(ler(pasta), cortes_do_episodio(pasta))
    gravar_corte(pasta_corte(pasta, 0), novo_corte(0, CANDS[0], "f1"))
    reabrir_render(pasta, AGORA)
    assert ler(pasta).etapas["render"].situacao == "pendente"


def test_fila_chama_o_gancho_antes_de_processar_e_na_subida(tmp_path: Path) -> None:
    episodio(tmp_path)
    vistos: list[str] = []
    f = Fila(tmp_path, lambda n, p, e: None, lambda: AGORA, antes=lambda p: vistos.append(p.name))
    f.recuperar()
    f.processar("abcdefghijk")
    assert vistos == ["abcdefghijk", "abcdefghijk"]


class TravaQueCancelaAntes:
    """Trava falsa: na primeira entrada, o "cancelar" da rota passa na frente (pegou a trava antes)."""

    def __init__(self, cancelar: Callable[[], None]) -> None:
        self.cancelar: Callable[[], None] | None = cancelar
        self.real = threading.Lock()

    def __enter__(self) -> None:
        if self.cancelar is not None:
            self.cancelar()
            self.cancelar = None
        self.real.acquire()

    def __exit__(self, *_: object) -> None:
        self.real.release()


def test_cancelar_depois_que_a_fila_pegou_o_corte_e_recusado(tmp_path: Path) -> None:
    pasta, escrita, recusas = episodio(tmp_path), threading.Lock(), []
    pedir(pasta, 0)

    def falso(p: Path, c: Corte, raiz: Path, dep: DepRender) -> None:
        assert escrita.acquire(blocking=False)   # o render não segura a trava das rotas
        escrita.release()
        with escrita, pytest.raises(ErroProducao, match="já começou") as ex:
            cancelar_render(pasta, 0)
        recusas.append(str(ex.value))

    rodar_render(pasta, ler(pasta), tmp_path, DEP, escrita, falso)
    assert len(recusas) == 1 and cortes_do_episodio(pasta)[0].status == "pronto"


def test_fila_pula_corte_cancelado_antes_de_reivindicar(tmp_path: Path) -> None:
    pasta, feitos = episodio(tmp_path), []
    pedir(pasta, 0, 2)
    trava = TravaQueCancelaAntes(lambda: cancelar_render(pasta, 0))
    rodar_render(pasta, ler(pasta), tmp_path, DEP, trava,  # type: ignore[arg-type]  # trava falsa
                 lambda p, c, r, d: feitos.append(c.indice))
    assert feitos == [2] and [c.indice for c in cortes_do_episodio(pasta)] == [2]


def test_corte_sumido_entre_glob_e_leitura_nao_derruba_a_etapa(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch) -> None:
    import cortes.render.corte as modulo
    pasta, feitos = episodio(tmp_path), []
    pedir(pasta, 0, 2)
    real = modulo.ler_corte

    def ler_e_sumir(d: Path) -> Corte:
        if d.name == "0" and (d / "corte.json").exists():
            (d / "corte.json").unlink()
        return real(d)

    monkeypatch.setattr(modulo, "ler_corte", ler_e_sumir)
    rodar_render(pasta, ler(pasta), tmp_path, DEP, threading.Lock(),
                 lambda p, c, r, d: feitos.append(c.indice))
    assert feitos == [2]
