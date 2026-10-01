from datetime import date
from pathlib import Path

import pytest

from cortes.painel.dados import Conta, ErroPainel, Formato, Vocabulario
from cortes.painel.publicados import Etiquetas, Publicado, gravar_publicados, ler_publicados, ligar

VOC = Vocabulario(
    contas={"grana": Conta("grana", "Grana", "@grana", "financas", "grana")},
    formatos={"f7": Formato("f7", "Conversa", "")},
    temas=frozenset({"humor", "dinheiro_alheio_quanto_ganha"}),
)


def pub(video_id: str = "abcdefghijk", formato: str = "f7", temas: tuple[str, ...] = ("humor",)) -> Publicado:
    return Publicado(video_id, "grana", date(2026, 10, 3), "testes/f7-conversa-comediante",
                     Etiquetas(formato, temas, "PrimoCast"))


def test_ida_e_volta(tmp_path: Path) -> None:
    arq = tmp_path / "publicados.jsonl"
    gravar_publicados(arq, [pub()])
    assert ler_publicados(arq, VOC) == [pub()]


def test_arquivo_ausente_e_lista_vazia(tmp_path: Path) -> None:
    assert ler_publicados(tmp_path / "nao_existe.jsonl", VOC) == []


def test_formato_fora_do_vocabulario() -> None:
    with pytest.raises(ErroPainel, match="formato 'f9'"):
        ligar([], pub(formato="f9"), VOC)


def test_tema_fora_do_vocabulario() -> None:
    with pytest.raises(ErroPainel, match="temas fora"):
        ligar([], pub(temas=("inventado",)), VOC)


def test_ligar_substitui_mesmo_video() -> None:
    novo = pub(temas=("dinheiro_alheio_quanto_ganha",))
    assert ligar([pub(), pub("zzzzzzzzzzz")], novo, VOC) == [pub("zzzzzzzzzzz"), novo]


def test_video_repetido_no_arquivo(tmp_path: Path) -> None:
    arq = tmp_path / "publicados.jsonl"
    gravar_publicados(arq, [pub()])
    arq.write_text(arq.read_text(encoding="utf-8") * 2, encoding="utf-8")
    with pytest.raises(ErroPainel, match="repetido"):
        ler_publicados(arq, VOC)


def test_linha_quebrada_diz_o_numero(tmp_path: Path) -> None:
    arq = tmp_path / "publicados.jsonl"
    arq.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ErroPainel, match=":1:"):
        ler_publicados(arq, VOC)


def test_conta_fora_do_vocabulario() -> None:
    with pytest.raises(ErroPainel, match="conta 'inexistente'"):
        ligar([], Publicado("abcdefghijk", "inexistente", date(2026, 10, 3), "testes/f7",
                             Etiquetas("f7", (), "PrimoCast")), VOC)


def test_podcast_vazio() -> None:
    with pytest.raises(ErroPainel, match="podcast vazio"):
        ligar([], Publicado("abcdefghijk", "grana", date(2026, 10, 3), "testes/f7",
                             Etiquetas("f7", (), "")), VOC)


def test_corte_vazio() -> None:
    with pytest.raises(ErroPainel, match="corte vazio"):
        ligar([], Publicado("abcdefghijk", "grana", date(2026, 10, 3), "",
                             Etiquetas("f7", (), "PrimoCast")), VOC)


def test_video_id_invalido() -> None:
    with pytest.raises(ErroPainel, match="video_id inválido"):
        ligar([], pub(video_id="curto"), VOC)


def test_linha_nao_e_json(tmp_path: Path) -> None:
    arq = tmp_path / "publicados.jsonl"
    arq.write_text("isso não é json\n", encoding="utf-8")
    with pytest.raises(ErroPainel, match=":1:"):
        ler_publicados(arq, VOC)


def test_podcast_tipo_errado(tmp_path: Path) -> None:
    arq = tmp_path / "publicados.jsonl"
    linha = ('{"video_id": "abcdefghijk", "conta": "grana", "publicado_em": "2026-10-03", '
             '"corte": "testes/f7", "etiquetas": {"formato": "f7", "temas": [], "podcast": null}}\n')
    arq.write_text(linha, encoding="utf-8")
    with pytest.raises(ErroPainel, match="podcast"):
        ler_publicados(arq, VOC)


def test_temas_tipo_errado(tmp_path: Path) -> None:
    arq = tmp_path / "publicados.jsonl"
    linha = ('{"video_id": "abcdefghijk", "conta": "grana", "publicado_em": "2026-10-03", '
             '"corte": "testes/f7", "etiquetas": {"formato": "f7", "temas": "humor", '
             '"podcast": "PrimoCast"}}\n')
    arq.write_text(linha, encoding="utf-8")
    with pytest.raises(ErroPainel, match="temas"):
        ler_publicados(arq, VOC)
