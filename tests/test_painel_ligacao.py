import json
import re
from pathlib import Path

import pytest

from cortes.painel.dados import ErroPainel
from cortes.painel.ligacao import CorteConhecido, listar_cortes, sugerir


def arvore(raiz: Path) -> None:
    for nome in ("comum", "_fontes", "f7-conversa-comediante", "f1-falante-95-carteiras",
                 "f9-sem-formato", "short-400mil"):
        (raiz / "testes" / nome).mkdir(parents=True)
    (raiz / "episodios" / "abc" / "cortes" / "1").mkdir(parents=True)
    meta = raiz / "episodios" / "abc" / "meta.json"
    meta.write_text(json.dumps({"canal": "PrimoCast"}), encoding="utf-8")


def test_lista_cortes_de_testes_e_episodios(tmp_path: Path) -> None:
    arvore(tmp_path)
    cortes = {c.caminho: c for c in listar_cortes(tmp_path, {"f1", "f7"})}
    assert set(cortes) == {"testes/f1-falante-95-carteiras", "testes/f7-conversa-comediante",
                           "testes/f9-sem-formato", "testes/short-400mil", "episodios/abc/cortes/1"}
    assert cortes["testes/f7-conversa-comediante"].formato == "f7"
    assert cortes["testes/f9-sem-formato"].formato is None       # f9 não está nos formatos
    assert cortes["episodios/abc/cortes/1"].podcast == "PrimoCast"


def test_sem_pastas_lista_vazia(tmp_path: Path) -> None:
    assert listar_cortes(tmp_path, {"f7"}) == []


def test_canal_ausente_no_meta_levanta_erro_com_caminho(tmp_path: Path) -> None:
    (tmp_path / "episodios" / "abc" / "cortes" / "1").mkdir(parents=True)
    meta = tmp_path / "episodios" / "abc" / "meta.json"
    meta.write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(ErroPainel, match=re_escapado(meta)):
        listar_cortes(tmp_path, set())


def test_canal_nao_texto_levanta_erro_com_caminho(tmp_path: Path) -> None:
    (tmp_path / "episodios" / "abc" / "cortes" / "1").mkdir(parents=True)
    meta = tmp_path / "episodios" / "abc" / "meta.json"
    meta.write_text(json.dumps({"canal": 123}), encoding="utf-8")
    with pytest.raises(ErroPainel, match=re_escapado(meta)):
        listar_cortes(tmp_path, set())


def re_escapado(caminho: Path) -> str:
    return re.escape(str(caminho))


def test_sugere_pelo_titulo() -> None:
    cortes = [CorteConhecido("testes/f1-falante-95-carteiras", "f1-falante-95-carteiras", "f1", None),
              CorteConhecido("testes/f7-conversa-comediante", "f7-conversa-comediante", "f7", None)]
    assert sugerir("O COMEDIANTE que mais vende #shorts", cortes)[0].formato == "f7"
    assert sugerir("95% das carteiras estão erradas", cortes)[0].formato == "f1"


def test_sugere_desempata_por_caminho_quando_empata(tmp_path: Path) -> None:
    cortes = [CorteConhecido("testes/b-exemplo", "b-exemplo", None, None),
              CorteConhecido("testes/a-exemplo", "a-exemplo", None, None)]
    resultado = sugerir("titulo sem relacao nenhuma", cortes)
    assert [c.caminho for c in resultado] == ["testes/a-exemplo", "testes/b-exemplo"]
