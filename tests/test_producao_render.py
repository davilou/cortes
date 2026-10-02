import json
from datetime import datetime
from pathlib import Path

from cortes.producao.estado import gravar, ler, marcar, novo
from cortes.producao.fila import Fila
from cortes.producao.render import reabrir_render, render_pendente, rodar_render
from cortes.render.corte import Corte, cortes_do_episodio, gravar_corte, novo_corte, pasta_corte
from cortes.render.pipeline import DepRender

AGORA = datetime(2026, 10, 2, 9)
DEP = DepRender(Path("py"), Path("m.onnx"), "npx")
CANDS = [{"inicio": 10.0, "fim": 40.0, "titulo": "A", "nota_final": 50.0},
         {"inicio": 50.0, "fim": 80.0, "titulo": "B", "nota_final": 90.0},
         {"inicio": 90.0, "fim": 120.0, "titulo": "C", "nota_final": 70.0}]


def episodio(tmp: Path, n: int = 2) -> Path:
    pasta = tmp / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    e = novo("abcdefghijk", "https://youtu.be/abcdefghijk", "financas", n, "f7", AGORA)
    for nome in ("video", "legenda", "sinais", "momentos"):
        e = marcar(e, nome, "ok", AGORA)
    gravar(pasta, e)
    (pasta / "candidatos.json").write_text(json.dumps(CANDS), encoding="utf-8")
    return pasta


def test_planeja_os_melhores_e_renderiza_um_por_vez(tmp_path: Path) -> None:
    pasta, feitos = episodio(tmp_path), []

    def falso(p: Path, c: Corte, raiz: Path, dep: DepRender) -> None:
        feitos.append((c.indice, c.status))

    rodar_render(pasta, ler(pasta), tmp_path, DEP, falso)
    assert feitos == [(1, "na_fila"), (2, "na_fila")]
    cortes = [(c.indice, c.status, c.versao) for c in cortes_do_episodio(pasta)]
    assert cortes == [(1, "pronto", 1), (2, "pronto", 1)]


def test_um_corte_que_falha_nao_para_os_outros(tmp_path: Path) -> None:
    pasta = episodio(tmp_path)

    def falso(p: Path, c: Corte, raiz: Path, dep: DepRender) -> None:
        if c.indice == 1:
            raise RuntimeError("npx sumiu")

    rodar_render(pasta, ler(pasta), tmp_path, DEP, falso)
    um, dois = cortes_do_episodio(pasta)
    assert um.status == "erro" and um.erro == "RuntimeError: npx sumiu" and dois.status == "pronto"


def test_nao_replaneja(tmp_path: Path) -> None:
    pasta, feitos = episodio(tmp_path), []
    rodar_render(pasta, ler(pasta), tmp_path, DEP, lambda p, c, r, d: None)
    rodar_render(pasta, ler(pasta), tmp_path, DEP, lambda p, c, r, d: feitos.append(c.indice))
    assert feitos == [] and len(cortes_do_episodio(pasta)) == 2


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
