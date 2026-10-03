import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pytest

from cortes.producao.estado import (
    ETAPAS,
    ErroProducao,
    EstadoEpisodio,
    Etapa,
    concluido,
    etapa_com_erro,
    gravar,
    ler,
    marcar,
    novo,
    proxima,
    reabrir,
)

AGORA = datetime(2026, 10, 2, 9, 12)


def ep() -> EstadoEpisodio:
    return novo("c5xqNNWFT9w", "https://youtu.be/c5xqNNWFT9w", "financas", "f7", AGORA)


def test_novo_comeca_tudo_pendente() -> None:
    e = ep()
    assert list(e.etapas) == list(ETAPAS) and proxima(e) == "video" and not concluido(e)


def test_avanca_pelas_etapas() -> None:
    e = ep()
    for nome in ETAPAS:
        assert proxima(e) == nome
        e = marcar(marcar(e, nome, "rodando", AGORA), nome, "ok", AGORA)
    assert concluido(e) and proxima(e) is None


def test_erro_para_a_fila_do_episodio() -> None:
    e = marcar(ep(), "video", "ok", AGORA)
    e = marcar(e, "legenda", "erro", AGORA, "vídeo sem legenda em português no YouTube")
    assert proxima(e) is None and etapa_com_erro(e) == "legenda"
    assert e.etapas["legenda"].erro == "vídeo sem legenda em português no YouTube"


def test_reabrir_volta_erro_e_rodando_para_pendente() -> None:
    e = marcar(marcar(ep(), "video", "rodando", AGORA), "video", "erro", AGORA, "falhou")
    e = reabrir(e)
    assert e.etapas["video"].situacao == "pendente" and e.etapas["video"].erro is None
    assert proxima(e) == "video"


def test_reabrir_retoma_apos_queda_mantendo_o_que_terminou() -> None:
    # Processo caiu com "video" ok e "legenda" no meio ("rodando"): a retomada
    # devolve "legenda" para pendente e mantém "video" intocado.
    e = marcar(marcar(ep(), "video", "rodando", AGORA), "video", "ok", AGORA)
    e = marcar(e, "legenda", "rodando", AGORA)
    e = reabrir(e)
    assert e.etapas["video"].situacao == "ok"
    assert e.etapas["legenda"].situacao == "pendente" and e.etapas["legenda"].erro is None
    assert proxima(e) == "legenda"


def test_erro_exige_mensagem_e_ok_nao_aceita() -> None:
    with pytest.raises(ErroProducao, match="mensagem"):
        marcar(ep(), "video", "erro", AGORA)
    with pytest.raises(ErroProducao, match="só em erro"):
        marcar(ep(), "video", "ok", AGORA, "x")


def test_etapa_desconhecida() -> None:
    with pytest.raises(ErroProducao, match="etapa 'xyz'"):
        marcar(ep(), "xyz", "ok", AGORA)


def test_ida_e_volta_em_disco(tmp_path: Path) -> None:
    e = marcar(ep(), "video", "ok", AGORA)
    gravar(tmp_path, e)
    assert ler(tmp_path) == e


def test_estado_quebrado_diz_o_arquivo(tmp_path: Path) -> None:
    (tmp_path / "estado.json").write_text('{"id": "x"}', encoding="utf-8")
    with pytest.raises(ErroProducao, match="estado.json"):
        ler(tmp_path)


def test_estado_com_campo_de_tipo_errado_nao_aceita_coercao(tmp_path: Path) -> None:
    e = ep()
    gravar(tmp_path, e)
    dados = (tmp_path / "estado.json").read_text(encoding="utf-8")
    # nicho como número não deve ser aceito silenciosamente.
    quebrado = dados.replace('"nicho": "financas"', '"nicho": 5')
    (tmp_path / "estado.json").write_text(quebrado, encoding="utf-8")
    with pytest.raises(ErroProducao, match="estado.json"):
        ler(tmp_path)


def test_estado_com_situacao_invalida_nao_aceita(tmp_path: Path) -> None:
    e = ep()
    gravar(tmp_path, e)
    dados = (tmp_path / "estado.json").read_text(encoding="utf-8")
    quebrado = dados.replace('"situacao": "pendente"', '"situacao": "travado"')
    (tmp_path / "estado.json").write_text(quebrado, encoding="utf-8")
    with pytest.raises(ErroProducao, match="estado.json"):
        ler(tmp_path)


def test_estado_sem_arquivo_diz_o_caminho(tmp_path: Path) -> None:
    with pytest.raises(ErroProducao, match="estado.json"):
        ler(tmp_path)


def test_estado_do_plano_a_sem_render_migra_para_pendente(tmp_path: Path) -> None:
    e = novo("abcdefghijk", "u", "financas", "f7", datetime(2026, 10, 2))
    d = asdict(e)
    del d["etapas"]["render"]
    (tmp_path / "estado.json").write_text(json.dumps(d), encoding="utf-8")
    assert ler(tmp_path).etapas["render"] == Etapa()


def test_estado_antigo_com_n_shorts_le_sem_o_campo(tmp_path: Path) -> None:
    e = ep()
    (tmp_path / "estado.json").write_text(json.dumps({**asdict(e), "n_shorts": 5}), encoding="utf-8")
    assert ler(tmp_path) == e and not hasattr(ler(tmp_path), "n_shorts")
