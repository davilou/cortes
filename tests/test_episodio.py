from pathlib import Path

import pytest

from cortes.episodio import id_do_video, ler_json, pasta, salvar_json


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=idiB5Far8eA",
    "https://youtu.be/idiB5Far8eA",
    "https://www.youtube.com/shorts/idiB5Far8eA",
    "https://www.youtube.com/live/idiB5Far8eA?si=x",
    "https://www.youtube.com/watch?v=idiB5Far8eA&t=120s",
])
def test_id_do_video_aceita_formatos(url: str) -> None:
    assert id_do_video(url) == "idiB5Far8eA"


def test_id_do_video_rejeita_url_sem_id() -> None:
    with pytest.raises(ValueError, match="sem id"):
        id_do_video("https://www.youtube.com/@canal")


def test_pasta_cria_diretorio(tmp_path: Path) -> None:
    p = pasta("abc", raiz=tmp_path)
    assert p == tmp_path / "abc" and p.is_dir()


def test_salvar_e_ler_json_ida_e_volta(tmp_path: Path) -> None:
    alvo = tmp_path / "x.json"
    salvar_json(alvo, {"á": [1, 2]})
    assert ler_json(alvo) == {"á": [1, 2]}
    assert not (tmp_path / "x.json.tmp").exists()
