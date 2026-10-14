"""Biblioteca de camas da trilha (spec trilha §3): `biblioteca/trilhas/plano.json` + `final/<id>.m4a`.

Cada fase do plano tem `id`, `mood` (um de MOODS) e `bpm`; todo mood precisa de pelo menos uma
cama. A loudness de cada cama é medida uma vez e guardada em `medidas.json`, chaveada pelo tamanho
e mtime do arquivo e pelo método de medição (arquivo trocado ou método novo → mede de novo).

A medida é a de como a fonte toca no MP4 estéreo (render/trilha.ler_ebur128 soma ~3 dB à fonte
mono): medida em mono, a cama ficaria 3 dB mais alta na mistura do que a conta do ganho prevê
(achado no teste lento: voz estéreo, camas mono).
"""
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cortes.episodio import ler_json, salvar_json
from cortes.render.processo import CAUDA, ErroRender, Rodar, rodar_processo
from cortes.render.trilha import Medida, ler_ebur128

BIBLIOTECA = Path("biblioteca") / "trilhas"
MOODS = ("neutro", "tensao", "leve")
MEDIDAS = "medidas.json"
METODO = "como-toca-estereo"   # entra na chave do cache: medida de antes do método é refeita
MedirLufs = Callable[[Path], Medida]


@dataclass(frozen=True)
class Cama:
    id: str
    mood: str
    bpm: float
    arquivo: Path


def _cama(pasta: Path, f: Any) -> Cama:
    return Cama(str(f["id"]), str(f["mood"]), float(f["bpm"]), pasta / "final" / f"{f['id']}.m4a")


def ler_plano(pasta: Path) -> list[Cama]:
    arq = pasta / "plano.json"
    if not arq.exists():
        raise ErroRender(f"{arq}: plano.json não existe (a biblioteca de trilhas é obrigatória)")
    try:
        camas = [_cama(pasta, f) for f in ler_json(arq)["fases"]]
    except (KeyError, TypeError, ValueError) as ex:
        raise ErroRender(f"{arq}: plano inválido ({ex})") from ex
    _validar(arq, camas)
    return camas


def _validar(arq: Path, camas: list[Cama]) -> None:
    ids = [c.id for c in camas]
    if len(set(ids)) != len(ids):
        raise ErroRender(f"{arq}: id de cama repetido em {ids}")
    for c in camas:
        if c.mood not in MOODS:
            raise ErroRender(f"{arq}: cama {c.id} com mood '{c.mood}'; use um de {MOODS}")
        if not c.arquivo.exists():
            raise ErroRender(f"{arq}: cama {c.id} sem arquivo ({c.arquivo} não existe)")
    if faltam := [m for m in MOODS if m not in {c.mood for c in camas}]:
        raise ErroRender(f"{arq}: nenhuma cama para o mood {', '.join(faltam)}")


def cama_do_mood(camas: list[Cama], mood: str) -> Cama:
    """A primeira cama do mood (ler_plano garante que existe)."""
    return next(c for c in camas if c.mood == mood)


def cama_por_id(camas: list[Cama], id: str) -> Cama:
    for c in camas:
        if c.id == id:
            return c
    raise ErroRender(f"cama '{id}' não existe na biblioteca; use uma de {[c.id for c in camas]}")


def medir_lufs(arq: Path, rodar: Rodar) -> Medida:
    """Só a primeira faixa de áudio (`-vn`): a voz vem do trecho.mp4, e decodificar o vídeo 1080p
    custava ~1,2 s por prévia (revisão final)."""
    args = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(arq), "-map", "0:a:0", "-vn", "-af", "ebur128",
            "-f", "null", "-"]
    codigo, log = rodar(args, None)
    if codigo != 0:
        raise ErroRender(f"ffmpeg falhou ao medir {arq}: {log[-CAUDA:]}")
    return ler_ebur128(log)


def medir_lufs_real(arq: Path) -> Medida:
    return medir_lufs(arq, rodar_processo)


def medida_da_cama(cama: Cama, pasta: Path, medir: MedirLufs) -> Medida:
    arq = pasta / MEDIDAS
    cache: dict[str, Any] = ler_json(arq) if arq.exists() else {}
    st = cama.arquivo.stat()
    chave = {"tamanho": st.st_size, "mtime": st.st_mtime_ns, "metodo": METODO}
    lido = cache.get(cama.id)
    if isinstance(lido, dict) and lido.get("chave") == chave:
        return Medida(float(lido["lufs"]), float(lido["duracao"]))
    m = medir(cama.arquivo)
    salvar_json(arq, {**cache, cama.id: {"chave": chave, **asdict(m)}})
    return m
