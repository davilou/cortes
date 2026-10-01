import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from cortes.painel.coleta import (
    ErroColeta,
    Resultado,
    _executar,
    abrir_login,
    coletar_todas,
    comando_numeros,
    verificar_skill,
    zip_da_saida,
)
from cortes.painel.dados import Conta, ErroPainel
from cortes.painel.retratos import ler_retratos

CSV = ("Conteúdo,Título do vídeo,Horário de publicação do vídeo,Duração,Visualizações,"
       "Duração média da visualização,Porcentagem visualizada média (%),Inscritos\n"
       'abcdefghijk,Um Short,"Oct 1, 2026",30,500,0:00:20,70.5,2\n')
GRANA = Conta("grana", "Grana", "@grana", "financas", "grana")
RISO = Conta("riso", "Riso", "@riso", "humor", "riso")
AGORA = datetime(2026, 10, 10, 9, 12)


def executor_falso(falha_em: str | None = None):  # type: ignore[no-untyped-def]
    def executar(args: list[str], cwd: Path) -> str:
        perfil = args[args.index("--perfil") + 1]
        if perfil == falha_em:
            raise ErroColeta("login expirado")
        destino = Path(args[args.index("--destino") + 1])
        arq = destino / "Conteúdo.zip"
        with zipfile.ZipFile(arq, "w") as z:
            z.writestr("Dados da tabela.csv", CSV.encode("utf-8-sig"))
        return f"[09:12:00] canal UC123\n[09:12:30] pronto: {arq}\n"
    return executar


def executor_zip_corrompido():  # type: ignore[no-untyped-def]
    def executar(args: list[str], cwd: Path) -> str:
        destino = Path(args[args.index("--destino") + 1])
        arq = destino / "Conteúdo.zip"
        arq.write_text("isto não é um zip", encoding="utf-8")
        return f"[09:12:30] pronto: {arq}\n"
    return executar


def test_comando_pede_desde_sempre_e_metricas() -> None:
    args = comando_numeros("grana", Path("/tmp/x"))
    assert args[:3] == ["node", "src/cli.mjs", "numeros"]
    assert args[args.index("--dias") + 1] == "0"
    assert args[args.index("--metricas") + 1] == "views,duracao_media,pct_media,inscritos"


def test_zip_da_saida() -> None:
    caminho = r"C:\Users\x\AppData\Local\Temp\tmpab c\Conteúdo.zip"
    saida = (
        "[09:12:00] canal UC123\n"
        "[09:12:05] pedindo: VIDEO x views… · desde sempre\n"
        f"[09:12:25] baixado: {caminho} (12.3 kB)\n"
        f"[09:12:30] pronto: {caminho}\n"
    )
    assert zip_da_saida(saida) == Path(caminho)
    with pytest.raises(ErroColeta, match="não informou"):
        zip_da_saida("[1] nada aqui")


def test_falha_numa_conta_nao_para_as_outras(tmp_path: Path) -> None:
    vistos: list[Resultado] = []
    res = coletar_todas([GRANA, RISO], tmp_path, tmp_path / "retratos", lambda: AGORA,
                        executor_falso(falha_em="grana"), vistos.append)
    assert res == vistos
    assert res[0] == Resultado("grana", False, "conta 'grana': login expirado")
    assert res[1] == Resultado("riso", True, "1 vídeos")
    assert set(ler_retratos(tmp_path / "retratos")) == {"riso"}


def test_zip_corrompido_nao_escapa_e_cita_conta_e_caminho(tmp_path: Path) -> None:
    res = coletar_todas([GRANA], tmp_path, tmp_path / "retratos", lambda: AGORA,
                        executor_zip_corrompido())
    assert len(res) == 1
    assert res[0].conta == "grana"
    assert res[0].ok is False
    assert "grana" in res[0].mensagem
    assert "Conteúdo.zip" in res[0].mensagem
    assert ler_retratos(tmp_path / "retratos") == {}


def test_verificar_skill_sem_node_no_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(ErroPainel, match="node não encontrado"):
        verificar_skill(tmp_path)


def test_verificar_skill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "C:/fake/node.exe")
    with pytest.raises(ErroPainel, match="cli.mjs"):
        verificar_skill(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "cli.mjs").write_text("", encoding="utf-8")
    with pytest.raises(ErroPainel, match="npm install"):
        verificar_skill(tmp_path)
    (tmp_path / "node_modules").mkdir()
    verificar_skill(tmp_path)


def test_abrir_login() -> None:
    abertos: list[tuple[list[str], Path]] = []
    abrir_login(GRANA, Path("skill"), lambda args, cwd: abertos.append((args, cwd)))
    assert abertos == [(["node", "src/cli.mjs", "login", "--perfil", "grana"], Path("skill"))]


def test_executar_devolve_stdout_no_sucesso(tmp_path: Path) -> None:
    saida = _executar([sys.executable, "-c", "print('ok')"], tmp_path)
    assert saida.strip() == "ok"


def test_executar_codigo_diferente_de_zero_vira_errocoleta(tmp_path: Path) -> None:
    script = "import sys; sys.stderr.write('deu tilt'); sys.exit(1)"
    with pytest.raises(ErroColeta, match="deu tilt"):
        _executar([sys.executable, "-c", script], tmp_path)


def test_executar_timeout_mata_a_arvore_e_nao_trava(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("cortes.painel.coleta.TIMEOUT_S", 1)
    with pytest.raises(ErroColeta, match="não terminou"):
        _executar([sys.executable, "-c", "import time; time.sleep(5)"], tmp_path)
