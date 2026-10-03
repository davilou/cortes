from pathlib import Path
from typing import Any

import pytest
from ddgs.exceptions import DDGSException

from cortes.render.ilustracao import Deixa
from cortes.render.ilustracao_imagens import (
    Candidata,
    LinhaFolha,
    args_baixar,
    baixar,
    baixar_candidatas,
    buscar,
    folha_args,
    gerar_folha,
)
from cortes.render.processo import ErroRender

DEIXA = Deixa(2.0, 3.5, "tênis", "tênis Vans Old Skool")


class DdgsFalso:
    def __init__(self, resultados: list[dict[str, Any]] | Exception) -> None:
        self.resultados = resultados
        self.pedidos: list[tuple[str, dict[str, Any]]] = []

    def images(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        self.pedidos.append((query, kwargs))
        if isinstance(self.resultados, Exception):
            raise self.resultados
        return self.resultados


def _r(img: str, w: Any = 1200, h: Any = 1200) -> dict[str, Any]:
    return {"image": img, "url": f"pagina-de-{img}", "width": w, "height": h, "title": "t"}


def test_busca_descarta_imagem_pequena_e_aceita_tamanho_vazio() -> None:
    ddgs = DdgsFalso([_r("a", 300, 900), _r("b", "", ""), _r("c", 800, 399), _r("d", "1000", "800")])
    assert buscar("tênis Vans", 4, ddgs) == [
        Candidata("b", "pagina-de-b", None, None), Candidata("d", "pagina-de-d", 1000, 800)]
    query, kwargs = ddgs.pedidos[0]
    assert query == "tênis Vans" and kwargs["region"] == "br-pt" and kwargs["safesearch"] == "moderate"


def test_busca_corta_em_n_e_sem_url_repetida() -> None:
    ddgs = DdgsFalso([_r("a"), _r("a"), _r("b"), _r("c"), _r("d")])
    assert [c.url for c in buscar("x", 2, ddgs)] == ["a", "b"]


def test_falha_da_busca_vira_erro_com_a_busca() -> None:
    with pytest.raises(ErroRender, match="camisa do Corinthians.*Ratelimit"):
        buscar("camisa do Corinthians", 4, DdgsFalso(DDGSException("Ratelimit")))


def test_args_baixar_normalizam_com_ffmpeg_e_user_agent() -> None:
    args = args_baixar("https://x/y.webp", Path("d.parcial.jpg"))
    assert args[args.index("-i") + 1] == "https://x/y.webp"
    assert args.index("-user_agent") < args.index("-i")
    assert "Mozilla" in args[args.index("-user_agent") + 1]
    assert args[args.index("-vf") + 1] == "scale=1080:1080:force_original_aspect_ratio=decrease"
    assert args[-1] == "d.parcial.jpg"


def _rodar_que_falha_em(ruim: str):  # type: ignore[no-untyped-def]
    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        if args[args.index("-i") + 1] == ruim:
            return 1, "HTTP error 403 Forbidden"
        Path(args[-1]).write_bytes(b"jpg")
        return 0, ""
    return rodar


def test_baixar_grava_parcial_e_renomeia(tmp_path: Path) -> None:
    destino = tmp_path / "ilus" / "d1-c1.jpg"
    baixar("u", destino, _rodar_que_falha_em("outra"))
    assert destino.read_bytes() == b"jpg" and not destino.with_suffix(".parcial.jpg").exists()


def test_baixar_sem_arquivo_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="não gerou"):
        baixar("u", tmp_path / "x.jpg", lambda a, c: (0, ""))


def test_falha_numa_candidata_nao_para_as_outras(tmp_path: Path) -> None:
    cands = [Candidata(u, "o", None, None) for u in ["u1", "u2", "u3"]]
    baixadas, falhas = baixar_candidatas(cands, tmp_path, "d1", _rodar_que_falha_em("u2"))
    assert [(c.url, p.name) for c, p in baixadas] == [("u1", "d1-c1.jpg"), ("u3", "d1-c3.jpg")]
    assert len(falhas) == 1 and "u2" in falhas[0] and "403" in falhas[0]


def test_folha_uma_linha_por_deixa_com_numero_em_cada_tile() -> None:
    linhas = [LinhaFolha(1, DEIXA, (Path("a1.jpg"), Path("a2.jpg"))),
              LinhaFolha(2, DEIXA, ()),
              LinhaFolha(3, DEIXA, (Path("c1.jpg"),))]
    args = folha_args(linhas, Path("folha.jpg"))
    assert [args[i + 1] for i, a in enumerate(args) if a == "-i"] == ["a1.jpg", "a2.jpg", "c1.jpg"]
    grafo = args[args.index("-filter_complex") + 1]
    assert "text='D1-1'" in grafo and "text='D1-2'" in grafo and "text='D3-1'" in grafo
    assert "D2-" not in grafo   # deixa sem candidata não entra
    assert "scale=320:320" in grafo and "arial.ttf" in grafo
    assert "xstack=inputs=3:layout=0_0|320_0|0_320:fill=white" in grafo
    assert args[-1] == "folha.jpg"


def test_folha_de_uma_imagem_so_nao_usa_xstack() -> None:
    args = folha_args([LinhaFolha(4, DEIXA, (Path("a.jpg"),))], Path("f.jpg"))
    grafo = args[args.index("-filter_complex") + 1]
    assert "xstack" not in grafo and "text='D4-1'" in grafo


def test_folha_sem_imagem_nenhuma_e_erro() -> None:
    with pytest.raises(ErroRender, match="nenhuma imagem"):
        folha_args([LinhaFolha(1, DEIXA, ())], Path("f.jpg"))


def test_gerar_folha_confere_o_arquivo(tmp_path: Path) -> None:
    linhas = [LinhaFolha(1, DEIXA, (Path("a.jpg"),))]
    with pytest.raises(ErroRender, match="não gerou"):
        gerar_folha(linhas, tmp_path / "folha.jpg", lambda a, c: (0, ""))

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        Path(args[-1]).write_bytes(b"jpg")
        return 0, ""

    gerar_folha(linhas, tmp_path / "folha.jpg", rodar)
    assert (tmp_path / "folha.jpg").exists()
