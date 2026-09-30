from pathlib import Path

import pytest

from cortes.perfil import carregar_perfil

YAML_OK = """
nicho: teste
filtro_tema: "É sobre dinheiro."
rubrica: {gancho_3s: 0.3, autocontido: 0.25, espanto: 0.2, historia_ou_virada: 0.1, fechamento: 0.15}
bonus:
  numero_na_primeira_frase: "a primeira frase traz um número"
penalidade:
  palestra_ou_palco: "gravado em palco"
duracao_s: {min: 20, max: 90}
"""
PENALIDADE_OK = 'penalidade:' + chr(10) + '  palestra_ou_palco: "gravado em palco"'


def criar(tmp: Path, yaml: str, bons: str = "", ruins: str = "") -> Path:
    (tmp / "exemplos").mkdir()
    (tmp / "perfil.yaml").write_text(yaml, encoding="utf-8")
    (tmp / "exemplos" / "bons.jsonl").write_text(bons, encoding="utf-8")
    (tmp / "exemplos" / "ruins.jsonl").write_text(ruins, encoding="utf-8")
    return tmp


def test_carrega_perfil_valido(tmp_path: Path) -> None:
    p = carregar_perfil(criar(tmp_path, YAML_OK, bons='{"texto": "a", "motivo": "b"}\n'))
    assert p.nicho == "teste" and p.duracao_min == 20 and p.duracao_max == 90
    assert p.rubrica["gancho_3s"] == 0.3
    assert p.exemplos_bons == [{"texto": "a", "motivo": "b"}] and p.exemplos_ruins == []
    assert p.bonus == {"numero_na_primeira_frase": "a primeira frase traz um número"}
    assert p.penalidade == {"palestra_ou_palco": "gravado em palco"}


def test_penalidade_vazia_e_aceita(tmp_path: Path) -> None:
    yaml = YAML_OK.replace(PENALIDADE_OK, "penalidade: {}")
    assert carregar_perfil(criar(tmp_path, yaml)).penalidade == {}


def test_tags_em_lista_levantam(tmp_path: Path) -> None:
    yaml = YAML_OK.replace(PENALIDADE_OK, "penalidade: [x]")
    with pytest.raises(ValueError, match="penalidade"):
        carregar_perfil(criar(tmp_path, yaml))


def test_tag_em_bonus_e_penalidade_levanta(tmp_path: Path) -> None:
    yaml = YAML_OK.replace("palestra_ou_palco:", "numero_na_primeira_frase:")
    with pytest.raises(ValueError, match="numero_na_primeira_frase"):
        carregar_perfil(criar(tmp_path, yaml))


def test_campo_ausente_levanta_com_nome(tmp_path: Path) -> None:
    yaml = YAML_OK.replace('filtro_tema: "É sobre dinheiro."' + chr(10), "")
    with pytest.raises(ValueError, match="perfil.yaml sem o campo 'filtro_tema'"):
        carregar_perfil(criar(tmp_path, yaml))


def test_pesos_que_nao_somam_1_levantam(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="somam"):
        carregar_perfil(criar(tmp_path, YAML_OK.replace("0.15}", "0.5}")))


def test_criterio_desconhecido_levanta(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="critérios"):
        carregar_perfil(criar(tmp_path, YAML_OK.replace("fechamento", "outro")))


def test_sem_arquivo_de_exemplos_levanta(tmp_path: Path) -> None:
    (tmp_path / "perfil.yaml").write_text(YAML_OK, encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        carregar_perfil(tmp_path)


def test_perfil_financas_do_repo_e_valido() -> None:
    p = carregar_perfil(Path(__file__).resolve().parents[1] / "nichos" / "financas")
    assert p.nicho == "financas"
    assert "numero_na_primeira_frase" in p.bonus and p.penalidade == {}
