import re
from pathlib import Path

import pytest

from cortes.painel.dados import (
    ErroPainel,
    carregar_contas,
    carregar_formatos,
    carregar_temas,
    carregar_vocabulario,
)

PERFIL = """nicho: financas
filtro_tema: "É sobre dinheiro."
rubrica: {gancho_3s: 0.3, autocontido: 0.25, espanto: 0.2, historia_ou_virada: 0.1, fechamento: 0.15}
bonus: {humor: "faz rir", numero_na_primeira_frase: "traz número"}
penalidade: {palestra: "gravado em palco"}
duracao_s: {min: 20, max: 90}
"""
CONTA = '  - {id: grana, nome: Grana, handle: "@grana", nicho: financas, perfil_studio: grana}\n'


def criar_nicho(nichos: Path, nome: str, texto: str = PERFIL) -> None:
    pasta = nichos / nome
    (pasta / "exemplos").mkdir(parents=True)
    (pasta / "perfil.yaml").write_text(texto, encoding="utf-8")
    for arq in ("bons.jsonl", "ruins.jsonl"):
        (pasta / "exemplos" / arq).write_text("", encoding="utf-8")


def escrever(tmp: Path, nome: str, texto: str) -> Path:
    arq = tmp / nome
    arq.write_text(texto, encoding="utf-8")
    return arq


def test_carrega_contas(tmp_path: Path) -> None:
    criar_nicho(tmp_path / "nichos", "financas")
    contas = carregar_contas(escrever(tmp_path, "c.yaml", "contas:\n" + CONTA), tmp_path / "nichos")
    assert contas["grana"].handle == "@grana" and contas["grana"].perfil_studio == "grana"


def test_lista_vazia_e_valida(tmp_path: Path) -> None:
    assert carregar_contas(escrever(tmp_path, "c.yaml", "contas: []\n"), tmp_path) == {}


def test_nicho_inexistente(tmp_path: Path) -> None:
    (tmp_path / "nichos").mkdir()
    with pytest.raises(ErroPainel, match="nicho 'financas'"):
        carregar_contas(escrever(tmp_path, "c.yaml", "contas:\n" + CONTA), tmp_path / "nichos")


def test_campo_faltando(tmp_path: Path) -> None:
    texto = "contas:\n  - {id: grana, nome: G, handle: '@g', nicho: financas}\n"
    with pytest.raises(ErroPainel, match="perfil_studio"):
        carregar_contas(escrever(tmp_path, "c.yaml", texto), tmp_path)


def test_id_repetido(tmp_path: Path) -> None:
    criar_nicho(tmp_path / "nichos", "financas")
    with pytest.raises(ErroPainel, match="repetido"):
        carregar_contas(escrever(tmp_path, "c.yaml", "contas:\n" + CONTA + CONTA), tmp_path / "nichos")


def test_id_fora_do_padrao(tmp_path: Path) -> None:
    criar_nicho(tmp_path / "nichos", "financas")
    texto = "contas:\n" + CONTA.replace("id: grana", "id: Grana!")
    with pytest.raises(ErroPainel, match="padrão"):
        carregar_contas(escrever(tmp_path, "c.yaml", texto), tmp_path / "nichos")


def test_perfil_studio_fora_do_padrao(tmp_path: Path) -> None:
    criar_nicho(tmp_path / "nichos", "financas")
    texto = "contas:\n" + CONTA.replace("perfil_studio: grana", "perfil_studio: ../Grana x")
    with pytest.raises(ErroPainel, match="perfil_studio '../Grana x' fora do padrão"):
        carregar_contas(escrever(tmp_path, "c.yaml", texto), tmp_path / "nichos")


def test_yaml_invalido(tmp_path: Path) -> None:
    arq = escrever(tmp_path, "c.yaml", "contas:\n  - {id: grana, handle: @x}\n")
    with pytest.raises(ErroPainel, match=re.escape(str(arq))):
        carregar_contas(arq, tmp_path)


def test_arquivo_inexistente(tmp_path: Path) -> None:
    arq = tmp_path / "nao_existe.yaml"
    with pytest.raises(ErroPainel, match=re.escape(str(arq))):
        carregar_contas(arq, tmp_path)


def test_formatos(tmp_path: Path) -> None:
    f = carregar_formatos(escrever(tmp_path, "f.yaml", "formatos:\n  f1: {nome: Falante}\n"))
    assert f["f1"].nome == "Falante" and f["f1"].obs == ""


def test_formato_repetido(tmp_path: Path) -> None:
    texto = "formatos:\n  f1: {nome: Falante}\n  f1: {nome: Outro}\n"
    with pytest.raises(ErroPainel, match="repetida"):
        carregar_formatos(escrever(tmp_path, "f.yaml", texto))


def test_formato_sem_nome(tmp_path: Path) -> None:
    with pytest.raises(ErroPainel, match="'f1' sem 'nome'"):
        carregar_formatos(escrever(tmp_path, "f.yaml", "formatos:\n  f1: {obs: x}\n"))


def test_formato_id_nao_texto(tmp_path: Path) -> None:
    with pytest.raises(ErroPainel, match="deve ser texto"):
        carregar_formatos(escrever(tmp_path, "f.yaml", "formatos:\n  1: {nome: X}\n"))


def test_formato_obs_nao_texto(tmp_path: Path) -> None:
    with pytest.raises(ErroPainel, match="'obs' deve ser texto"):
        carregar_formatos(escrever(tmp_path, "f.yaml", "formatos:\n  f1: {nome: X, obs: null}\n"))


def test_temas_unem_bonus_e_penalidade_dos_nichos(tmp_path: Path) -> None:
    criar_nicho(tmp_path, "financas")
    criar_nicho(tmp_path, "humor", PERFIL.replace('humor: "faz rir"', 'trocadilho: "jogo de palavras"'))
    assert carregar_temas(tmp_path) == {"humor", "numero_na_primeira_frase", "palestra", "trocadilho"}


def test_temas_sem_perfis(tmp_path: Path) -> None:
    with pytest.raises(ErroPainel, match="nenhum perfil de nicho encontrado"):
        carregar_temas(tmp_path)


def test_temas_perfil_invalido(tmp_path: Path) -> None:
    pasta = tmp_path / "financas"
    pasta.mkdir()
    (pasta / "perfil.yaml").write_text("nicho: financas\n", encoding="utf-8")
    with pytest.raises(ErroPainel, match=re.escape(str(pasta / "perfil.yaml"))):
        carregar_temas(tmp_path)


def test_vocabulario_da_raiz(tmp_path: Path) -> None:
    criar_nicho(tmp_path / "nichos", "financas")
    (tmp_path / "contas").mkdir()
    escrever(tmp_path / "contas", "contas.yaml", "contas:\n" + CONTA)
    escrever(tmp_path / "contas", "formatos.yaml", "formatos:\n  f7: {nome: Conversa}\n")
    voc = carregar_vocabulario(tmp_path)
    assert set(voc.contas) == {"grana"} and set(voc.formatos) == {"f7"} and "humor" in voc.temas
