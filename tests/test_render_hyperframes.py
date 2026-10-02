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
