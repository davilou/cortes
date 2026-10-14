import json
from pathlib import Path

import pytest

from cortes.render.processo import ErroRender
from cortes.render.trilha import Medida
from cortes.render.trilha_biblioteca import (
    cama_do_mood,
    cama_por_id,
    ler_plano,
    medida_da_cama,
    medir_lufs,
)
from tests.test_render_trilha import LOG

FASES = [{"id": "A", "mood": "neutro", "bpm": 76}, {"id": "B", "mood": "tensao", "bpm": 70},
         {"id": "C", "mood": "leve", "bpm": 84}]


def biblioteca(pasta: Path, fases: list[dict[str, object]] = FASES) -> Path:
    (pasta / "final").mkdir(parents=True)
    (pasta / "plano.json").write_text(json.dumps({"fases": fases}), encoding="utf-8")
    for f in fases:
        (pasta / "final" / f"{f['id']}.m4a").write_bytes(b"m4a")
    return pasta


def test_ler_plano(tmp_path: Path) -> None:
    camas = ler_plano(biblioteca(tmp_path))
    assert [(c.id, c.mood, c.bpm) for c in camas] == [("A", "neutro", 76.0), ("B", "tensao", 70.0),
                                                     ("C", "leve", 84.0)]
    assert camas[0].arquivo == tmp_path / "final" / "A.m4a"
    assert cama_do_mood(camas, "tensao").id == "B" and cama_por_id(camas, "C").mood == "leve"


def test_plano_ausente_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="plano.json não existe"):
        ler_plano(tmp_path)


def test_cama_sem_arquivo_e_erro(tmp_path: Path) -> None:
    biblioteca(tmp_path)
    (tmp_path / "final" / "B.m4a").unlink()
    with pytest.raises(ErroRender, match="cama B"):
        ler_plano(tmp_path)


def test_mood_sem_cama_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="leve"):
        ler_plano(biblioteca(tmp_path, FASES[:2]))


def test_mood_desconhecido_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="alegre"):
        ler_plano(biblioteca(tmp_path, [*FASES, {"id": "D", "mood": "alegre", "bpm": 90}]))


def test_id_repetido_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="repetid"):
        ler_plano(biblioteca(tmp_path, [*FASES, {"id": "A", "mood": "neutro", "bpm": 90}]))


def test_cama_por_id_desconhecido_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="Z"):
        cama_por_id(ler_plano(biblioteca(tmp_path)), "Z")


def test_medir_lufs_chama_o_ffmpeg_e_le_o_log(tmp_path: Path) -> None:
    vistos: list[list[str]] = []

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        vistos.append(args)
        return 0, LOG

    assert medir_lufs(tmp_path / "a.m4a", rodar) == Medida(-31.5, 89.9)
    assert vistos[0][0] == "ffmpeg" and "ebur128" in vistos[0]
    assert "-vn" in vistos[0] and "0:a:0" in vistos[0], "a voz vem de um mp4: só o áudio é decodificado"


def test_medir_lufs_falha_alto(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="ffmpeg falhou"):
        medir_lufs(tmp_path / "a.m4a", lambda a, c: (1, "boom"))


def test_medida_da_cama_usa_cache_ate_o_arquivo_mudar(tmp_path: Path) -> None:
    camas = ler_plano(biblioteca(tmp_path))
    medidas: list[Path] = []

    def medir(arq: Path) -> Medida:
        medidas.append(arq)
        return Medida(-30.0, 90.0)

    assert medida_da_cama(camas[0], tmp_path, medir) == Medida(-30.0, 90.0)
    assert medida_da_cama(camas[0], tmp_path, medir) == Medida(-30.0, 90.0)
    assert len(medidas) == 1
    camas[0].arquivo.write_bytes(b"outra cama, maior")
    medida_da_cama(camas[0], tmp_path, medir)
    assert len(medidas) == 2


def test_medida_antiga_sem_o_metodo_estereo_e_refeita(tmp_path: Path) -> None:
    """Cama mono medida em mono soa 3 dB mais alta no MP4 estéreo: medida velha não vale."""
    camas = ler_plano(biblioteca(tmp_path))
    st = camas[0].arquivo.stat()
    velha = {"A": {"chave": {"tamanho": st.st_size, "mtime": st.st_mtime_ns}, "lufs": -25.5, "duracao": 90.0}}
    (tmp_path / "medidas.json").write_text(json.dumps(velha), encoding="utf-8")
    assert medida_da_cama(camas[0], tmp_path, lambda a: Medida(-22.5, 90.0)).lufs == -22.5
