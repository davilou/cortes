from datetime import date, datetime
from pathlib import Path

import pytest

from cortes.painel.dados import ErroPainel
from cortes.painel.retratos import Retrato, VideoRetrato, ler_retratos, salvar_retrato


def video(views: int) -> VideoRetrato:
    return VideoRetrato("abcdefghijk", "Título", date(2026, 10, 3), 26.0, views, 87.4, 22.7, 3)


def test_ida_e_volta(tmp_path: Path) -> None:
    r = Retrato("grana", datetime(2026, 10, 10, 9, 12), (video(1830),))
    destino = salvar_retrato(tmp_path, r)
    assert destino == tmp_path / "grana" / "2026-10-10.json"
    assert ler_retratos(tmp_path) == {"grana": [r]}


def test_ordena_por_data_e_mesmo_dia_sobrescreve(tmp_path: Path) -> None:
    salvar_retrato(tmp_path, Retrato("grana", datetime(2026, 10, 12, 8), (video(300),)))
    salvar_retrato(tmp_path, Retrato("grana", datetime(2026, 10, 10, 8), (video(100),)))
    salvar_retrato(tmp_path, Retrato("grana", datetime(2026, 10, 10, 20), (video(150),)))
    rs = ler_retratos(tmp_path)["grana"]
    assert [r.videos[0].views for r in rs] == [150, 300]


def test_pasta_ausente_e_vazio(tmp_path: Path) -> None:
    assert ler_retratos(tmp_path / "nada") == {}


def test_retrato_quebrado(tmp_path: Path) -> None:
    (tmp_path / "grana").mkdir()
    (tmp_path / "grana" / "2026-10-10.json").write_text('{"conta": "grana"}', encoding="utf-8")
    with pytest.raises(ErroPainel, match="retrato inválido"):
        ler_retratos(tmp_path)


def test_json_truncado(tmp_path: Path) -> None:
    (tmp_path / "grana").mkdir()
    (tmp_path / "grana" / "2026-10-10.json").write_text('{"conta": "gra', encoding="utf-8")
    with pytest.raises(ErroPainel, match="retrato inválido"):
        ler_retratos(tmp_path)


def test_conta_nao_casa_com_a_pasta(tmp_path: Path) -> None:
    (tmp_path / "grana").mkdir()
    r = Retrato("outraconta", datetime(2026, 10, 10, 9, 12), (video(1830),))
    salvar_retrato(tmp_path, Retrato("outraconta", r.coletado_em, r.videos))
    (tmp_path / "grana" / "2026-10-10.json").write_bytes(
        (tmp_path / "outraconta" / "2026-10-10.json").read_bytes()
    )
    with pytest.raises(ErroPainel, match="retrato inválido"):
        ler_retratos(tmp_path)


def test_dia_nao_casa_com_o_nome_do_arquivo(tmp_path: Path) -> None:
    (tmp_path / "grana").mkdir()
    r = Retrato("grana", datetime(2026, 10, 10, 9, 12), (video(1830),))
    salvar_retrato(tmp_path, r)
    (tmp_path / "grana" / "2026-10-11.json").write_bytes(
        (tmp_path / "grana" / "2026-10-10.json").read_bytes()
    )
    (tmp_path / "grana" / "2026-10-10.json").unlink()
    with pytest.raises(ErroPainel, match="retrato inválido"):
        ler_retratos(tmp_path)


def test_video_com_campo_de_tipo_errado(tmp_path: Path) -> None:
    (tmp_path / "grana").mkdir()
    arquivo = tmp_path / "grana" / "2026-10-10.json"
    arquivo.write_text(
        '{"conta": "grana", "coletado_em": "2026-10-10T09:12:00", "videos": '
        '[{"video_id": "abcdefghijk", "titulo": "Título", "publicado_em": "2026-10-03", '
        '"duracao_s": 26.0, "views": true, "pct_media": 87.4, "duracao_media_s": 22.7, '
        '"inscritos": 3}]}',
        encoding="utf-8",
    )
    with pytest.raises(ErroPainel, match="retrato inválido"):
        ler_retratos(tmp_path)
