"""Vídeo do B-roll (f4): busca e download do YouTube — com falsos, sem rede."""
from pathlib import Path

import pytest

from cortes.render.broll_video import (
    CAMPOS_BUSCA,
    DUR_MAX_VIDEO_S,
    DUR_MIN_VIDEO_S,
    VideoCandidato,
    apagar_bruto,
    args_busca,
    args_video,
    baixar_bruto,
    buscar_videos,
    fonte,
    ler_busca,
)
from cortes.render.ilustracao_imagens import ErroBusca
from cortes.render.processo import ErroRender

VANS = VideoCandidato("abcDEF_12-x", 100.0, "Canal", "Vans Old Skool review")


class Rodar:
    """Executor falso: responde por ordem e, se pedido, cria o arquivo que o comando gravaria."""

    def __init__(self, *respostas: tuple[int, str], cria: bool = True) -> None:
        self.respostas = list(respostas)
        self.cria = cria
        self.chamadas: list[list[str]] = []

    def __call__(self, args: list[str], cwd: Path | None) -> tuple[int, str]:
        self.chamadas.append(args)
        codigo, saida = self.respostas.pop(0) if self.respostas else (0, "")
        if codigo == 0 and self.cria:
            self._criar(args)
        return codigo, saida

    @staticmethod
    def _criar(args: list[str]) -> None:
        if "yt_dlp" in args:
            molde = args[args.index("-o") + 1]
            Path(molde.replace("%(ext)s", "mp4")).write_bytes(b"bruto")
        else:   # ffmpeg: os arquivos de saída são os argumentos que terminam em .mp4/.jpg sem -i antes
            for i, a in enumerate(args):
                if a.endswith((".mp4", ".jpg")) and args[i - 1] != "-i":
                    Path(a).write_bytes(b"x")


def _linha(vid: str, dur: str, titulo: str = "t") -> str:
    return f"{vid}|{dur}|Canal {vid}|{titulo}"


def test_args_da_busca_pedem_15_resultados_sem_baixar() -> None:
    args = args_busca("tênis Vans Old Skool")
    assert args[-1] == "ytsearch15:tênis Vans Old Skool" and "--flat-playlist" in args
    assert args[args.index("--print") + 1] == CAMPOS_BUSCA and "--ignore-config" in args


def test_busca_filtra_15s_a_3min_ignora_aviso_e_sem_duracao() -> None:
    assert (DUR_MIN_VIDEO_S, DUR_MAX_VIDEO_S) == (15.0, 180.0)
    saida = "\n".join(["WARNING: algo", _linha("aaaaaaaaaaa", "14.0"), _linha("bbbbbbbbbbb", "15"),
                       _linha("ccccccccccc", "NA"), _linha("ddddddddddd", "181"),
                       _linha("eeeeeeeeeee", "180", "título | com barra"), _linha("bbbbbbbbbbb", "15")])
    assert ler_busca(saida, 3) == [VideoCandidato("bbbbbbbbbbb", 15.0, "Canal bbbbbbbbbbb", "t"),
                                   VideoCandidato("eeeeeeeeeee", 180.0, "Canal eeeeeeeeeee",
                                                  "título | com barra")]


def test_busca_corta_em_n_e_id_invalido_nao_vira_candidato() -> None:
    saida = "\n".join([_linha("curto", "60"), _linha("a;rm -rf /x", "60"),
                       *(_linha(f"{c * 11}", "60") for c in "fgh")])
    assert [c.id for c in ler_busca(saida, 2)] == ["f" * 11, "g" * 11]


def test_buscar_videos_roda_a_busca_e_le_a_saida() -> None:
    rodar = Rodar((0, _linha("ggggggggggg", "90")), cria=False)
    assert [c.id for c in buscar_videos("Vans", 3, rodar)] == ["ggggggggggg"]
    assert rodar.chamadas == [args_busca("Vans")]


@pytest.mark.parametrize("saida", ["ERROR: HTTP Error 429: Too Many Requests",
                                   "ERROR: Sign in to confirm you're not a bot"])
def test_busca_bloqueada_e_errobusca(saida: str) -> None:
    with pytest.raises(ErroBusca, match="limitou ou bloqueou"):
        buscar_videos("Vans", 3, Rodar((1, saida), cria=False))


@pytest.mark.parametrize("saida", ["ERROR: Unable to download API page: <urlopen error [Errno 11001] "
                                   "getaddrinfo failed>", "ERROR: Unable to download webpage: The read "
                                   "operation timed out"])
def test_busca_que_falha_por_rede_ou_prazo_e_errobusca(saida: str) -> None:
    with pytest.raises(ErroBusca, match="código 1.*Unable to download"):
        buscar_videos("Vans", 3, Rodar((1, saida), cria=False))

    def estoura(args: list[str], cwd: Path | None) -> tuple[int, str]:
        raise ErroRender("python passou de 30 s e foi interrompido")

    with pytest.raises(ErroBusca, match="foi interrompido"):
        buscar_videos("Vans", 3, estoura)


@pytest.mark.parametrize("saida", ["No module named yt_dlp",
                                   "ERROR: [youtube:search] x: KeyError('contents') ... report this issue"])
def test_ytdlp_quebrado_na_busca_e_errorender_nao_temporario(saida: str) -> None:
    with pytest.raises(ErroRender, match="código 1") as ex:
        buscar_videos("Vans", 3, Rodar((1, saida), cria=False))
    assert not isinstance(ex.value, ErroBusca) and saida[:20] in str(ex.value)


def test_titulo_com_not_a_bot_numa_busca_que_deu_certo_nao_e_bloqueio() -> None:
    rodar = Rodar((0, _linha("ggggggggggg", "90", "I'm not a bot")), cria=False)
    assert len(buscar_videos("x", 3, rodar)) == 1


def test_args_baixam_o_video_inteiro_so_video_ate_1080p_com_teto_de_tamanho() -> None:
    args = args_video(VANS, Path("p/D1-v1.bruto.%(ext)s"))
    assert "--download-sections" not in args and "--downloader" not in args
    assert args[args.index("-f") + 1] == "bv*[height<=1080][ext=mp4]/bv*[height<=1080]"
    assert args[args.index("--max-filesize") + 1] == "120M"
    assert args[args.index("-o") + 1] == str(Path("p/D1-v1.bruto.%(ext)s"))
    assert args[-2:] == ["--", "https://www.youtube.com/watch?v=abcDEF_12-x"]


def test_dois_candidatos_por_deixa_por_padrao() -> None:
    saida = "\n".join(_linha(c * 11, "60") for c in "fghij")
    assert len(buscar_videos("x", rodar=Rodar((0, saida), cria=False))) == 2


@pytest.mark.parametrize("vid", ["curto", "abcDEF_12-x&list=1", "../../etc/pw", "-abcdefghij "])
def test_id_invalido_e_recusado(vid: str) -> None:
    with pytest.raises(ErroRender, match="id de vídeo"):
        args_video(VideoCandidato(vid, 100.0, "c", "t"), Path("x.%(ext)s"))


def test_baixar_bruto_deixa_o_video_inteiro_para_a_conferencia(tmp_path: Path) -> None:
    rodar = Rodar()
    bruto = baixar_bruto(VANS, tmp_path, "D1-v1.bruto", rodar)
    assert bruto == tmp_path / "D1-v1.bruto.mp4" and bruto.exists()
    assert len(rodar.chamadas) == 1 and "yt_dlp" in rodar.chamadas[0]
    apagar_bruto(tmp_path, "D1-v1.bruto")
    assert list(tmp_path.iterdir()) == []


# a mensagem do downloader nativo (YoutubeDL.process_info: "unable to download video data: <HTTPError>")
@pytest.mark.parametrize("saida", ["ERROR: [youtube] abc: HTTP Error 429: Too Many Requests",
                                   "ERROR: unable to download video data: HTTP Error 429: Too Many Requests",
                                   "ERROR: unable to download video data: HTTP Error 403: Forbidden"])
def test_video_com_429_ou_403_e_errobusca_sem_tentar_de_novo(tmp_path: Path, saida: str) -> None:
    rodar = Rodar((1, saida))
    with pytest.raises(ErroBusca, match="limitou ou bloqueou"):
        baixar_bruto(VANS, tmp_path, "D1-v1.bruto", rodar)
    assert len(rodar.chamadas) == 1 and list(tmp_path.iterdir()) == []


def test_video_maior_que_o_teto_e_erro_claro(tmp_path: Path) -> None:
    saida = "[download] File is larger than max-filesize (200000000 bytes > 125829120 bytes). Aborting."
    with pytest.raises(ErroRender, match="passa de 120M") as ex:
        baixar_bruto(VANS, tmp_path, "D1-v1.bruto", Rodar((0, saida), cria=False))
    assert not isinstance(ex.value, ErroBusca)


def test_video_indisponivel_e_errorender_comum(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="Video unavailable") as ex:
        baixar_bruto(VANS, tmp_path, "D1-v1.bruto", Rodar((1, "ERROR: Video unavailable")))
    assert not isinstance(ex.value, ErroBusca)


def _trava_unlink(monkeypatch: pytest.MonkeyPatch) -> None:
    """O Windows não deixa apagar o bruto (antivírus ou indexador com o arquivo aberto)."""
    original = Path.unlink

    def unlink(self: Path, missing_ok: bool = False) -> None:
        if ".bruto." in self.name:
            raise PermissionError(13, "acesso negado", str(self))
        original(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)


def test_bruto_preso_nao_mascara_o_erro_original(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def deixa_part(args: list[str], cwd: Path | None) -> tuple[int, str]:
        (tmp_path / "D1-v1.bruto.mp4.part").write_bytes(b"meio")
        return 1, "ERROR: Video unavailable"

    _trava_unlink(monkeypatch)
    with pytest.raises(ErroRender, match="Video unavailable") as ex:
        baixar_bruto(VANS, tmp_path, "D1-v1.bruto", deixa_part)
    assert any("D1-v1.bruto.mp4.part" in n for n in getattr(ex.value, "__notes__", []))


def test_bruto_preso_e_errorender_com_o_caminho(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "D1-v1.bruto.mp4").write_bytes(b"bruto")
    _trava_unlink(monkeypatch)
    with pytest.raises(ErroRender, match=r"não consegui apagar .*D1-v1\.bruto\.mp4"):
        apagar_bruto(tmp_path, "D1-v1.bruto")


def test_fonte_do_clipe_com_licenca_e_risco() -> None:
    assert fonte(VANS) == {"fonte_url": "https://www.youtube.com/watch?v=abcDEF_12-x", "canal": "Canal",
                           "titulo": "Vans Old Skool review", "licenca": "desconhecida (YouTube)",
                           "risco": "alto"}
