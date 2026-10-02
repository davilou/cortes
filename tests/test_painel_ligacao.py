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


def re_escapado(caminho: Path) -> str:
    return re.escape(str(caminho))


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


def test_meta_ausente_levanta_erro_com_caminho(tmp_path: Path) -> None:
    (tmp_path / "episodios" / "abc" / "cortes" / "1").mkdir(parents=True)
    meta = tmp_path / "episodios" / "abc" / "meta.json"
    with pytest.raises(ErroPainel, match=re_escapado(meta)):
        listar_cortes(tmp_path, set())


def test_meta_json_invalido_levanta_erro_com_caminho(tmp_path: Path) -> None:
    (tmp_path / "episodios" / "abc" / "cortes" / "1").mkdir(parents=True)
    meta = tmp_path / "episodios" / "abc" / "meta.json"
    meta.write_text("{nao é json", encoding="utf-8")
    with pytest.raises(ErroPainel, match=re_escapado(meta)):
        listar_cortes(tmp_path, set())


def test_meta_que_nao_e_mapa_levanta_erro_proprio(tmp_path: Path) -> None:
    (tmp_path / "episodios" / "abc" / "cortes" / "1").mkdir(parents=True)
    meta = tmp_path / "episodios" / "abc" / "meta.json"
    meta.write_text(json.dumps(["PrimoCast"]), encoding="utf-8")
    with pytest.raises(ErroPainel, match="esperava um mapa JSON"):
        listar_cortes(tmp_path, set())


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


def test_sugere_desambigua_pelo_numero_colado_a_letras() -> None:
    cortes = [CorteConhecido("testes/x-95-carteiras", "x-95-carteiras", None, None),
              CorteConhecido("testes/x-20-carteiras", "x-20-carteiras", None, None)]
    assert sugerir("95% das carteiras estão erradas", cortes)[0].caminho == "testes/x-95-carteiras"
    assert sugerir("só 20% das carteiras acertam", cortes)[0].caminho == "testes/x-20-carteiras"


def test_sugere_casa_numero_colado_a_palavra_na_pasta() -> None:
    cortes = [CorteConhecido("testes/short-400mil", "short-400mil", None, None),
              CorteConhecido("testes/f1-falante-95-carteiras", "f1-falante-95-carteiras", "f1", None)]
    assert sugerir("Ele ganhou 400 mil", cortes)[0].caminho == "testes/short-400mil"


def test_sugere_prefixo_de_formato_nao_conta_como_palavra() -> None:
    cortes = [CorteConhecido("testes/f1-politica-internacional", "f1-politica-internacional", "f1", None),
              CorteConhecido("testes/comediante-show", "comediante-show", None, None)]
    # o "1" do título não deve casar com o "1" do prefixo "f1-"
    assert sugerir("Episodio 1 do show de comedia", cortes)[0].caminho == "testes/comediante-show"


def test_sugere_pasta_com_prefixo_de_formato_alcanca_casamento_total() -> None:
    # sem tirar o prefixo "f7-", o "7" entraria nas palavras da pasta e o casamento ficaria
    # em 2/3 (abaixo do concorrente, 3/4); tirando o prefixo, a pasta casa 100% e vence.
    cortes = [CorteConhecido("testes/f7-conversa-comediante", "f7-conversa-comediante", "f7", None),
              CorteConhecido("testes/conversa-com-comediante-extra",
                              "conversa-com-comediante-extra", None, None)]
    assert sugerir("A conversa com o comediante", cortes)[0].caminho == "testes/f7-conversa-comediante"


def test_corte_de_episodio_usa_o_titulo_do_corte_json(tmp_path: Path) -> None:
    from cortes.render.corte import gravar_corte, novo_corte, pasta_corte
    ep = tmp_path / "episodios" / "abcdefghijk"
    ep.mkdir(parents=True)
    (ep / "meta.json").write_text('{"canal": "PrimoCast"}', encoding="utf-8")
    gravar_corte(pasta_corte(ep, 3),
                 novo_corte(3, {"inicio": 1, "fim": 30, "titulo": "O comediante que mais vende"}, "f7"))
    [c] = listar_cortes(tmp_path, {"f7"})
    assert (c.nome, c.formato, c.podcast) == ("O comediante que mais vende", "f7", "PrimoCast")
    assert sugerir("comediante que mais vende #shorts", [c])[0] == c
