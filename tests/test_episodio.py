from pathlib import Path

import pytest

import cortes.episodio as episodio_mod
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
    assert list(tmp_path.glob("*.tmp")) == []


def test_salvar_json_tenta_de_novo_se_replace_falhar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simula o Windows recusando o `replace` por um tempo porque outra thread (ex.: o
    painel lendo o estado.json) tem o destino aberto: a gravação deve esperar e tentar
    de novo em vez de subir o erro na primeira tentativa.
    """
    alvo = tmp_path / "x.json"
    original_replace = Path.replace
    chamadas = {"n": 0}

    def falha_duas_vezes(self: Path, destino: "str | Path") -> Path:
        chamadas["n"] += 1
        if chamadas["n"] <= 2:
            raise PermissionError("em uso por outro processo")
        return original_replace(self, destino)

    monkeypatch.setattr(Path, "replace", falha_duas_vezes)
    monkeypatch.setattr(episodio_mod.time, "sleep", lambda _s: None)

    salvar_json(alvo, {"ok": True})

    assert chamadas["n"] == 3
    assert ler_json(alvo) == {"ok": True}


def test_salvar_json_desiste_apos_tentativas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    alvo = tmp_path / "x.json"

    def sempre_falha(self: Path, destino: "str | Path") -> Path:
        raise PermissionError("em uso por outro processo")

    monkeypatch.setattr(Path, "replace", sempre_falha)
    monkeypatch.setattr(episodio_mod.time, "sleep", lambda _s: None)

    with pytest.raises(PermissionError):
        salvar_json(alvo, {"ok": True})
