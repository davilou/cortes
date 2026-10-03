"""Vídeo do B-roll (f4): busca e trecho do YouTube, quadros e foto em tela cheia — com falsos, sem rede."""
from pathlib import Path

import pytest

from cortes.render.broll_video import (
    CAMPOS_BUSCA,
    DUR_MAX_VIDEO_S,
    VideoCandidato,
    args_busca,
    args_cheio,
    args_foto_cheia,
    args_trecho,
    baixar_trecho,
    buscar_videos,
    extrair_quadros,
    fonte,
    foto_cheia,
    ler_busca,
    quadros_args,
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


def test_args_da_busca_pedem_8_resultados_sem_baixar() -> None:
    args = args_busca("tênis Vans Old Skool")
    assert args[-1] == "ytsearch8:tênis Vans Old Skool" and "--flat-playlist" in args
    assert args[args.index("--print") + 1] == CAMPOS_BUSCA and "--ignore-config" in args


def test_busca_filtra_20s_a_20min_ignora_aviso_e_sem_duracao() -> None:
    saida = "\n".join(["WARNING: algo", _linha("aaaaaaaaaaa", "19.0"), _linha("bbbbbbbbbbb", "20"),
                       _linha("ccccccccccc", "NA"), _linha("ddddddddddd", str(DUR_MAX_VIDEO_S + 1)),
                       _linha("eeeeeeeeeee", "1200", "título | com barra"), _linha("bbbbbbbbbbb", "20")])
    assert ler_busca(saida, 3) == [VideoCandidato("bbbbbbbbbbb", 20.0, "Canal bbbbbbbbbbb", "t"),
                                   VideoCandidato("eeeeeeeeeee", 1200.0, "Canal eeeeeeeeeee",
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


def test_busca_que_falha_por_rede_ou_prazo_e_errobusca() -> None:
    with pytest.raises(ErroBusca, match="código 1.*Unable to download"):
        buscar_videos("Vans", 3, Rodar((1, "ERROR: Unable to download API page"), cria=False))

    def estoura(args: list[str], cwd: Path | None) -> tuple[int, str]:
        raise ErroRender("python passou de 30 s e foi interrompido")

    with pytest.raises(ErroBusca, match="foi interrompido"):
        buscar_videos("Vans", 3, estoura)


def test_titulo_com_not_a_bot_numa_busca_que_deu_certo_nao_e_bloqueio() -> None:
    rodar = Rodar((0, _linha("ggggggggggg", "90", "I'm not a bot")), cria=False)
    assert len(buscar_videos("x", 3, rodar)) == 1


def test_args_da_secao_de_5s_a_partir_de_25_por_cento_so_video_ate_1080p_sem_recodificar() -> None:
    args = args_trecho(VANS, Path("p/D1-v1.bruto.%(ext)s"))
    assert args[args.index("--download-sections") + 1] == "*25-30"
    assert args[args.index("-f") + 1] == "bv*[height<=1080][ext=mp4]/bv*[height<=1080]"
    assert args[-2:] == ["--", "https://www.youtube.com/watch?v=abcDEF_12-x"]
    assert "--force-keyframes-at-cuts" not in args   # o ffmpeg de args_cheio já corta os 3 s


def test_dois_candidatos_por_deixa_por_padrao() -> None:
    saida = "\n".join(_linha(c * 11, "60") for c in "fghij")
    assert len(buscar_videos("x", rodar=Rodar((0, saida), cria=False))) == 2


@pytest.mark.parametrize("vid", ["curto", "abcDEF_12-x&list=1", "../../etc/pw", "-abcdefghij "])
def test_id_invalido_e_recusado(vid: str) -> None:
    with pytest.raises(ErroRender, match="id de vídeo"):
        args_trecho(VideoCandidato(vid, 100.0, "c", "t"), Path("x.%(ext)s"))


def test_args_tela_cheia_cover_sem_audio() -> None:
    args = args_cheio(Path("b.mp4"), Path("d.mp4"))
    vf = args[args.index("-vf") + 1]
    assert "scale=1080:1920:force_original_aspect_ratio=increase" in vf and "crop=1080:1920" in vf
    assert "-an" in args and args[args.index("-t") + 1] == "3.000"


def test_baixar_trecho_gera_o_mp4_e_apaga_o_bruto(tmp_path: Path) -> None:
    rodar = Rodar()
    destino = tmp_path / "D1-v1.mp4"
    baixar_trecho(VANS, destino, rodar)
    assert destino.exists() and sorted(p.name for p in tmp_path.iterdir()) == ["D1-v1.mp4"]
    assert "yt_dlp" in rodar.chamadas[0] and rodar.chamadas[1][0] == "ffmpeg"


def test_trecho_com_429_e_errobusca_sem_tentar_de_novo(tmp_path: Path) -> None:
    rodar = Rodar((1, "ERROR: [youtube] abc: HTTP Error 429: Too Many Requests"))
    with pytest.raises(ErroBusca, match="limitou ou bloqueou"):
        baixar_trecho(VANS, tmp_path / "D1-v1.mp4", rodar)
    assert len(rodar.chamadas) == 1 and list(tmp_path.iterdir()) == []


def test_trecho_indisponivel_e_errorender_comum(tmp_path: Path) -> None:
    rodar = Rodar((1, "ERROR: Video unavailable"))
    with pytest.raises(ErroRender, match="Video unavailable") as ex:
        baixar_trecho(VANS, tmp_path / "D1-v1.mp4", rodar)
    assert not isinstance(ex.value, ErroBusca)


def test_ffmpeg_que_falha_nao_deixa_mp4_nem_bruto(tmp_path: Path) -> None:
    rodar = Rodar((0, ""), (1, "Invalid data"))
    with pytest.raises(ErroRender, match="tela cheia"):
        baixar_trecho(VANS, tmp_path / "D1-v1.mp4", rodar)
    assert list(tmp_path.iterdir()) == []


def test_quadros_inicio_meio_e_fim_num_ffmpeg_so(tmp_path: Path) -> None:
    ds = (Path("q1.jpg"), Path("q2.jpg"), Path("q3.jpg"))
    args = quadros_args(Path("t.mp4"), ds)
    assert [args[i + 1] for i, a in enumerate(args) if a == "-ss"] == ["0.10", "1.50", "2.80"]
    assert [args[i + 1] for i, a in enumerate(args) if a == "-map"] == ["0:v", "1:v", "2:v"]
    assert args[-1] == "q3.jpg"


def test_extrair_quadros_grava_os_tres(tmp_path: Path) -> None:
    qs = extrair_quadros(tmp_path / "t.mp4", tmp_path / "D1-v1", Rodar())
    assert [q.name for q in qs] == ["D1-v1-q1.jpg", "D1-v1-q2.jpg", "D1-v1-q3.jpg"]


def test_quadro_que_nao_saiu_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="não gerou D1-v1-q1.jpg"):
        extrair_quadros(tmp_path / "t.mp4", tmp_path / "D1-v1", Rodar(cria=False))


def test_foto_cheia_contain_sobre_ela_mesma_desfocada() -> None:
    args = args_foto_cheia(Path("f.jpg"), Path("d.jpg"))
    grafo = args[args.index("-filter_complex") + 1]
    assert "force_original_aspect_ratio=increase,crop=1080:1920,boxblur" in grafo
    assert "force_original_aspect_ratio=decrease[frente]" in grafo and "overlay=(W-w)/2:(H-h)/2" in grafo
    assert args[-1] == "d.jpg" and args.count("f.jpg") == 2


def test_foto_cheia_grava_por_parcial(tmp_path: Path) -> None:
    foto_cheia(tmp_path / "f.jpg", tmp_path / "broll-1.jpg", Rodar())
    assert [p.name for p in tmp_path.iterdir()] == ["broll-1.jpg"]
    with pytest.raises(ErroRender, match="tela cheia"):
        foto_cheia(tmp_path / "f.jpg", tmp_path / "broll-2.jpg", Rodar((1, "erro")))
    assert not (tmp_path / "broll-2.jpg").exists()


def test_fonte_do_clipe_com_licenca_e_risco() -> None:
    assert fonte(VANS) == {"fonte_url": "https://www.youtube.com/watch?v=abcDEF_12-x", "canal": "Canal",
                           "titulo": "Vans Old Skool review", "licenca": "desconhecida (YouTube)",
                           "risco": "alto"}
