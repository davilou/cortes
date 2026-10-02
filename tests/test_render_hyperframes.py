import json
from pathlib import Path

import pytest

from cortes.render.hyperframes import HYPERFRAMES, criar_projeto, renderizar
from cortes.render.processo import ErroRender


def test_criar_projeto(tmp_path: Path) -> None:
    criar_projeto(tmp_path / "projeto", "<html></html>")
    assert (tmp_path / "projeto" / "index.html").read_text(encoding="utf-8") == "<html></html>"
    config = json.loads((tmp_path / "projeto" / "hyperframes.json").read_text(encoding="utf-8"))
    assert config["paths"]["assets"] == "assets"


def test_renderizar_grava_por_parcial_e_guarda_o_log(tmp_path: Path) -> None:
    vistos: list[tuple[list[str], Path | None]] = []

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        vistos.append((args, cwd))
        Path(args[-1]).write_bytes(b"mp4")
        return 0, "Render complete"

    renderizar(tmp_path, tmp_path / "short-v1.mp4", "npx", rodar)
    assert (tmp_path / "short-v1.mp4").read_bytes() == b"mp4"
    assert vistos[0][0][:5] == ["npx", "--yes", HYPERFRAMES, "render", "--output"]
    assert vistos[0][1] == tmp_path
    assert (tmp_path / "render.log").read_text(encoding="utf-8") == "Render complete"


def test_render_que_falha_nao_deixa_mp4(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="render falhou.*timeline"):
        renderizar(tmp_path, tmp_path / "short-v1.mp4", "npx", lambda a, c: (1, "erro na timeline"))
    assert not (tmp_path / "short-v1.mp4").exists()


def test_render_sem_arquivo_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="sem gerar"):
        renderizar(tmp_path, tmp_path / "short-v1.mp4", "npx", lambda a, c: (0, "ok"))


def test_saida_relativa_funciona_com_processo_rodando_em_outro_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    proj = tmp_path / "projeto"
    proj.mkdir()

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        Path(args[-1]).write_bytes(b"mp4")   # o falso escreve relativo ao cwd do PROCESSO de teste
        return 0, ""

    monkeypatch.chdir(tmp_path)
    renderizar(proj, Path("short-v1.mp4"), "npx", rodar)
    assert (tmp_path / "short-v1.mp4").read_bytes() == b"mp4"


def test_render_que_falha_depois_de_escrever_nao_deixa_parcial_no_disco(tmp_path: Path) -> None:
    def falha_depois_de_escrever(args: list[str], cwd: Path | None) -> tuple[int, str]:
        Path(args[-1]).write_bytes(b"lixo")
        return 1, "erro na timeline"

    with pytest.raises(ErroRender, match="render falhou"):
        renderizar(tmp_path, tmp_path / "short-v1.mp4", "npx", falha_depois_de_escrever)
    assert not list(tmp_path.glob("*.parcial.mp4"))
