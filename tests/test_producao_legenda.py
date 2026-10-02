import subprocess
import sys
from pathlib import Path

import pytest

from cortes.producao.legenda_yt import ARQUIVO, FIM_MAX_S, ErroLegenda, baixar, comando, palavras_do_json3
from cortes.tipos import Palavra

AUTO = {"events": [
    {"tStartMs": 0, "dDurationMs": 6000, "segs": [{"utf8": "[música]"}]},
    {"tStartMs": 22000, "dDurationMs": 4000, "wWinId": 1, "segs": [
        {"utf8": "Está", "acAsrConf": 0}, {"utf8": " começando", "tOffsetMs": 199},
        {"utf8": " o", "tOffsetMs": 519}, {"utf8": " Primocast,", "tOffsetMs": 600}]},
    {"tStartMs": 24000, "wWinId": 1, "aAppend": 1, "segs": [{"utf8": "\n"}]},
    {"tStartMs": 24160, "dDurationMs": 3000, "segs": [
        {"utf8": "grupo"}, {"utf8": " Primo.", "tOffsetMs": 320}]},
]}
MANUAL = {"events": [
    {"tStartMs": 1000, "dDurationMs": 2000, "segs": [{"utf8": "Bom dia a todos"}]},
    {"tStartMs": 3500, "dDurationMs": 1000, "segs": [{"utf8": "[aplausos e risos] Obrigado."}]},
]}


def test_legenda_automatica_usa_offset_por_palavra() -> None:
    ps = palavras_do_json3(AUTO)
    assert [p.texto for p in ps] == ["Está", "começando", "o", "Primocast,", "grupo", "Primo."]
    assert ps[0] == Palavra("Está", 22.0, 22.199)
    assert ps[1].fim == pytest.approx(22.519)                  # fim = início da seguinte
    assert ps[3].inicio == 22.6 and ps[3].fim == pytest.approx(22.6 + FIM_MAX_S)  # 24.16 passa do limite
    assert ps[5].inicio == pytest.approx(24.48) and ps[5].fim == pytest.approx(24.48 + FIM_MAX_S)


def test_marcas_entre_colchetes_somem() -> None:
    assert all("[" not in p.texto for p in palavras_do_json3(AUTO) + palavras_do_json3(MANUAL))


def test_legenda_manual_distribui_a_linha_pelo_tamanho_das_palavras() -> None:
    ps = palavras_do_json3(MANUAL)
    assert [p.texto for p in ps] == ["Bom", "dia", "a", "todos", "Obrigado."]
    assert ps[0].inicio == 1.0 and ps[3].inicio > ps[2].inicio > ps[1].inicio > 1.0
    assert ps[3].inicio < 3.0                                   # dentro do evento
    assert ps[4].inicio == 3.5


def test_pausa_longa_nao_estica_a_palavra() -> None:
    dados = {"events": [{"tStartMs": 0, "dDurationMs": 500, "segs": [{"utf8": "a"}]},
                        {"tStartMs": 9000, "dDurationMs": 500, "segs": [{"utf8": "b"}]}]}
    assert palavras_do_json3(dados)[0].fim == FIM_MAX_S


def test_sem_palavras_e_erro() -> None:
    with pytest.raises(ErroLegenda, match="sem palavras"):
        palavras_do_json3({"events": [{"tStartMs": 0, "segs": [{"utf8": "[música]"}]}]})


def test_json_fora_do_formato_e_erro() -> None:
    with pytest.raises(ErroLegenda, match="formato"):
        palavras_do_json3({"eventos": []})


def test_comando_pede_so_pt_em_json3(tmp_path: Path) -> None:
    cmd = comando("https://youtu.be/abcdefghijk", tmp_path)
    assert cmd[:3] == [sys.executable, "-m", "yt_dlp"]
    assert "--skip-download" in cmd and "--write-subs" in cmd and "--write-auto-subs" in cmd
    assert cmd[cmd.index("--sub-langs") + 1] == "pt"
    assert cmd[cmd.index("--sub-format") + 1] == "json3"


def executor(retorno: int, stderr: str = "", criar: bool = True):  # type: ignore[no-untyped-def]
    def rodar(args: list[str]) -> subprocess.CompletedProcess[str]:
        destino = Path(args[args.index("-o") + 1]).parent
        if criar:
            (destino / ARQUIVO).write_text('{"events": []}', encoding="utf-8")
        return subprocess.CompletedProcess(args, retorno, "", stderr)
    return rodar


def test_baixar_devolve_o_arquivo(tmp_path: Path) -> None:
    assert baixar("https://youtu.be/abcdefghijk", tmp_path, executor(0)) == tmp_path / ARQUIVO


def test_sem_legenda_pt_para_com_mensagem(tmp_path: Path) -> None:
    with pytest.raises(ErroLegenda, match="sem legenda em português"):
        baixar("https://youtu.be/abcdefghijk", tmp_path, executor(0, criar=False))


def test_429_para_sem_repetir(tmp_path: Path) -> None:
    with pytest.raises(ErroLegenda, match="limitou as requisições"):
        erro = ("ERROR: Unable to download video subtitles for 'pt': "
                "HTTP Error 429: Too Many Requests")
        baixar("https://youtu.be/abcdefghijk", tmp_path, executor(1, erro, False))


def test_outro_erro_do_ytdlp_mostra_o_fim_do_stderr(tmp_path: Path) -> None:
    with pytest.raises(ErroLegenda, match="Video unavailable"):
        baixar("https://youtu.be/abcdefghijk", tmp_path, executor(1, "ERROR: Video unavailable", False))
