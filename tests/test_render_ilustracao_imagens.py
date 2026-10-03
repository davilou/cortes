import re
import threading
from pathlib import Path
from typing import Any

import pytest
from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

from cortes.render.ilustracao import Deixa
from cortes.render.ilustracao_imagens import (
    Candidata,
    ErroBusca,
    LinhaFolha,
    args_baixar,
    baixar,
    baixar_candidatas,
    buscar,
    dividir_folhas,
    falha_temporaria,
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
    """Nome curto vira URL http; URL com esquema fica como está."""
    url = img if ":" in img else f"http://img/{img}"
    return {"image": url, "url": f"pagina-de-{img}", "width": w, "height": h, "title": "t"}


def test_busca_descarta_imagem_pequena_e_aceita_tamanho_vazio() -> None:
    ddgs = DdgsFalso([_r("a", 300, 900), _r("b", "", ""), _r("c", 800, 399), _r("d", "1000", "800")])
    assert buscar("tênis Vans", 4, ddgs) == [
        Candidata("http://img/b", "pagina-de-b", None, None),
        Candidata("http://img/d", "pagina-de-d", 1000, 800)]
    query, kwargs = ddgs.pedidos[0]
    assert query == "tênis Vans" and kwargs["region"] == "br-pt" and kwargs["safesearch"] == "moderate"


def test_busca_corta_em_n_e_sem_url_repetida() -> None:
    ddgs = DdgsFalso([_r("a"), _r("a"), _r("b"), _r("c"), _r("d")])
    assert [c.url for c in buscar("x", 2, ddgs)] == ["http://img/a", "http://img/b"]


def test_busca_so_aceita_http_e_https() -> None:
    urls = ["file:///C:/segredo.jpg", "ftp://x/a.jpg", "data:image/png;base64,AAAA", "c:/a.jpg",
            "concat:http://x/a.jpg", "HTTPS://x/b.jpg", "http://x/c.jpg"]
    assert [c.url for c in buscar("x", 9, DdgsFalso([_r(u) for u in urls]))] == [
        "HTTPS://x/b.jpg", "http://x/c.jpg"]


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/a.jpg", "http://localhost:8790/api", "http://LOCALHOST/a.jpg", "http://x.localhost/a.jpg",
    "http://10.0.0.5/a.jpg", "http://192.168.0.1/a.jpg", "http://172.16.3.4/a.jpg", "http://169.254.169.254/x",
    "http://[::1]/a.jpg", "http://[fe80::1]/a.jpg", "http://[::ffff:127.0.0.1]/a.jpg", "http://0.0.0.0/a.jpg",
    "http://2130706433/a.jpg", "http://0x7f.1/a.jpg", "http://127.1/a.jpg", "http:///a.jpg", "https://:80/a.jpg",
    "http://impressora.local/a.jpg", "http://user@127.0.0.1/a.jpg"])
def test_busca_recusa_host_local_ou_privado(url: str) -> None:
    """A URL vem da web e o ffmpeg a abre daqui: nada de painel local, roteador ou metadados de nuvem."""
    assert buscar("x", 9, DdgsFalso([_r(url), _r("http://8.8.8.8/ok.jpg")])) == [
        Candidata("http://8.8.8.8/ok.jpg", "pagina-de-http://8.8.8.8/ok.jpg", 1200, 1200)]


def test_host_publico_por_nome_passa_sem_resolver_dns() -> None:
    urls = ["https://cdn.loja.com.br/a.jpg", "http://[2606:4700::1111]/b.jpg"]
    assert [c.url for c in buscar("x", 9, DdgsFalso([_r(u) for u in urls]))] == urls


def test_busca_sem_resultado_e_lista_vazia_nao_erro() -> None:
    """O ddgs 9.16 sinaliza "nada achado" com DDGSException("No results found.") (ddgs.py)."""
    assert buscar("x", 4, DdgsFalso(DDGSException("No results found."))) == []
    assert buscar("x", 4, DdgsFalso([])) == []


@pytest.mark.parametrize("erro", [RatelimitException("202 Ratelimit"), TimeoutException("timed out"),
                                  DDGSException("ConnectError('dns')")])
def test_erro_real_da_busca_vira_erro_de_busca_com_a_busca(erro: Exception) -> None:
    with pytest.raises(ErroBusca, match=f"camisa do Corinthians.*{re.escape(str(erro))}"):
        buscar("camisa do Corinthians", 4, DdgsFalso(erro))
    assert issubclass(ErroBusca, ErroRender)


def test_args_baixar_normalizam_com_ffmpeg_e_user_agent() -> None:
    args = args_baixar("https://x/y.webp", Path("d.parcial.jpg"))
    assert args[args.index("-i") + 1] == "https://x/y.webp"
    assert args.index("-user_agent") < args.index("-i")
    assert "Mozilla" in args[args.index("-user_agent") + 1]
    assert args[args.index("-vf") + 1] == "scale=1080:1080:force_original_aspect_ratio=decrease"
    i = args.index("-i")
    assert args.index("-protocol_whitelist") < i
    assert args[args.index("-protocol_whitelist") + 1] == "http,https,tls,tcp"
    assert args.index("-format_whitelist") < i
    demuxers = set(args[args.index("-format_whitelist") + 1].split(","))
    assert {"image2", "jpeg_pipe", "png_pipe", "webp_pipe"} <= demuxers
    assert not {"hls", "concat", "mov"} & demuxers
    assert args.index("-max_pixels") < i
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


def test_baixa_ate_4_candidatas_ao_mesmo_tempo_e_devolve_na_ordem(tmp_path: Path) -> None:
    """A barreira de 4 só abre com 4 downloads simultâneos: em série, estoura o prazo dela."""
    barreira = threading.Barrier(4, timeout=5)
    simultaneos: list[int] = []
    ativos = [0]
    trava = threading.Lock()

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        with trava:
            ativos[0] += 1
            simultaneos.append(ativos[0])
        url = args[args.index("-i") + 1]
        if url != "u5":
            barreira.wait()
        with trava:
            ativos[0] -= 1
        if url == "u3":
            return 1, "HTTP error 404"
        Path(args[-1]).write_bytes(url.encode())
        return 0, ""

    cands = [Candidata(f"u{j}", "o", None, None) for j in range(1, 6)]
    baixadas, falhas = baixar_candidatas(cands, tmp_path, "D1", rodar)
    assert [(c.url, p.name) for c, p in baixadas] == [
        ("u1", "D1-c1.jpg"), ("u2", "D1-c2.jpg"), ("u4", "D1-c4.jpg"), ("u5", "D1-c5.jpg")]
    assert (tmp_path / "D1-c4.jpg").read_bytes() == b"u4"
    assert len(falhas) == 1 and falhas[0].startswith("u3:") and max(simultaneos) == 4


@pytest.mark.parametrize("falha,temporaria", [
    ("u: ffmpeg passou de 30 s e foi interrompido", True),
    ("u: download de u falhou (código 1): Connection timed out", True),
    ("u: download de u falhou (código 1): Failed to resolve hostname x", True),
    ("u: download de u falhou (código 1): Server returned 5XX Server Error reply", True),
    ("u: download de u falhou (código 1): Server returned 404 Not Found", False),
    ("u: download de u falhou (código 1): HTTP error 403 Forbidden", False),
    ("u: download de u: ffmpeg não gerou a imagem", False)])
def test_falha_temporaria_so_para_prazo_rede_e_5xx(falha: str, temporaria: bool) -> None:
    assert falha_temporaria(falha) is temporaria


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
    # rótulo numa faixa branca de 48 px acima da foto, não por cima dela
    assert "pad=320:368:0:48:white" in grafo and "fontcolor=black" in grafo and "boxcolor" not in grafo
    assert "xstack=inputs=3:layout=0_0|320_0|0_368:fill=white" in grafo
    assert args[-1] == "folha.jpg"


def test_dividir_folhas_de_6_em_6_deixas_com_imagem() -> None:
    linhas = [LinhaFolha(k, DEIXA, (Path(f"{k}.jpg"),) if k != 3 else ()) for k in range(1, 15)]
    folhas = dividir_folhas(linhas)
    assert [[ln.k for ln in f] for f in folhas] == [[1, 2, 4, 5, 6, 7], [8, 9, 10, 11, 12, 13], [14]]
    assert dividir_folhas([LinhaFolha(1, DEIXA, ())]) == []


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
