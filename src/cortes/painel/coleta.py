"""Coleta dos números pela skill youtube-analytics (export do Studio via Playwright).

Uma conta por vez; a falha de uma não interrompe as outras e volta com a causa.
O login é manual, na janela do Chrome que a skill abre: o app nunca vê senha.
"""
import re
import subprocess
import tempfile
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cortes.painel.dados import Conta, ErroPainel
from cortes.painel.retratos import Retrato, salvar_retrato
from cortes.painel.studio import ler_tabela, texto_do_zip

Executor = Callable[[list[str], Path], str]
Abridor = Callable[[list[str], Path], object]
TIMEOUT_S = 600
METRICAS = "views,duracao_media,pct_media,inscritos"
_PRONTO = re.compile(r"pronto: (.+\.zip)\s*$", re.MULTILINE)


class ErroColeta(RuntimeError):
    pass


@dataclass(frozen=True)
class Resultado:
    conta: str
    ok: bool
    mensagem: str


def verificar_skill(skill_dir: Path) -> None:
    if not (skill_dir / "src" / "cli.mjs").exists():
        raise ErroPainel(f"skill youtube-analytics não encontrada em {skill_dir} (falta src/cli.mjs); "
                         "passe o caminho certo com --skill")
    if not (skill_dir / "node_modules").is_dir():
        raise ErroPainel(f"{skill_dir}: dependências da skill ausentes; rode 'npm install' nessa pasta")


def comando_numeros(perfil: str, destino: Path) -> list[str]:
    return ["node", "src/cli.mjs", "numeros", "--perfil", perfil, "--dias", "0",
            "--metricas", METRICAS, "--destino", str(destino)]


def comando_login(perfil: str) -> list[str]:
    return ["node", "src/cli.mjs", "login", "--perfil", perfil]


def zip_da_saida(saida: str) -> Path:
    achados = _PRONTO.findall(saida)
    if not achados:
        raise ErroColeta(f"o export não informou o zip gerado: {saida[-300:]}")
    return Path(achados[-1].strip())


def _executar(args: list[str], cwd: Path) -> str:
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired as e:
        raise ErroColeta(f"o export não terminou em {TIMEOUT_S}s") from e
    if r.returncode != 0:
        raise ErroColeta((r.stderr or r.stdout).strip()[-500:] or f"saiu com código {r.returncode}")
    return r.stdout


def _abrir(args: list[str], cwd: Path) -> object:
    return subprocess.Popen(args, cwd=cwd)


def _ler_zip(conta_id: str, caminho: Path) -> str:
    """Isola o zipfile.BadZipFile: um zip corrompido é falha de coleta, não crash."""
    try:
        return texto_do_zip(caminho)
    except zipfile.BadZipFile as e:
        raise ErroColeta(f"conta '{conta_id}': zip corrompido em {caminho}: {e}") from e


def coletar_conta(conta: Conta, skill_dir: Path, pasta_retratos: Path, agora: datetime,
                  executar: Executor = _executar) -> Retrato:
    with tempfile.TemporaryDirectory() as tmp:
        caminho = zip_da_saida(executar(comando_numeros(conta.perfil_studio, Path(tmp)), skill_dir))
        texto = _ler_zip(conta.id, caminho)
    try:
        videos = ler_tabela(texto)
    except ErroPainel as e:
        raise ErroPainel(f"conta '{conta.id}': {e}") from e
    retrato = Retrato(conta.id, agora, tuple(videos))
    salvar_retrato(pasta_retratos, retrato)
    return retrato


def coletar_todas(contas: Iterable[Conta], skill_dir: Path, pasta_retratos: Path,
                  agora: Callable[[], datetime], executar: Executor = _executar,
                  ao_terminar: Callable[[Resultado], None] | None = None) -> list[Resultado]:
    resultados: list[Resultado] = []
    for conta in contas:
        try:
            r = coletar_conta(conta, skill_dir, pasta_retratos, agora(), executar)
            res = Resultado(conta.id, True, f"{len(r.videos)} vídeos")
        except (ErroColeta, ErroPainel, OSError) as e:
            res = Resultado(conta.id, False, str(e))
        if ao_terminar is not None:
            ao_terminar(res)
        resultados.append(res)
    return resultados


def abrir_login(conta: Conta, skill_dir: Path, abrir: Abridor = _abrir) -> None:
    abrir(comando_login(conta.perfil_studio), skill_dir)
