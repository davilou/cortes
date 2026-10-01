from pathlib import Path

import pytest

from cortes import cli
from cortes.painel.dados import ErroPainel


def test_painel_com_configuracao_invalida_sai_com_mensagem(monkeypatch: pytest.MonkeyPatch) -> None:
    def quebra(*_: object, **__: object) -> None:
        raise ErroPainel("contas.yaml: falta a chave 'contas'")

    monkeypatch.setattr(cli, "criar_app", quebra)
    with pytest.raises(SystemExit) as saida:
        cli.rodar_painel(8790, Path("skill"), Path("raiz"))
    assert saida.value.code == "erro: contas.yaml: falta a chave 'contas'"
