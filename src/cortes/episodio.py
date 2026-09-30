"""Identidade e pasta de trabalho de um episódio; gravação atômica de JSON."""
import json
import re
from pathlib import Path
from typing import Any

RAIZ_EPISODIOS = Path("episodios")
_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|live/)([A-Za-z0-9_-]{11})")


def id_do_video(url: str) -> str:
    m = _ID.search(url)
    if not m:
        raise ValueError(f"URL sem id de vídeo do YouTube: {url}")
    return m.group(1)


def pasta(ep_id: str, raiz: Path = RAIZ_EPISODIOS) -> Path:
    p = raiz / ep_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def salvar_json(caminho: Path, dados: Any) -> None:
    """Grava em .tmp e renomeia: um arquivo nunca fica pela metade se o processo cair."""
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(caminho)


def ler_json(caminho: Path) -> Any:
    return json.loads(caminho.read_text(encoding="utf-8"))
