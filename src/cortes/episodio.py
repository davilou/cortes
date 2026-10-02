"""Identidade e pasta de trabalho de um episódio; gravação atômica de JSON."""
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

RAIZ_EPISODIOS = Path("episodios")
_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|live/)([A-Za-z0-9_-]{11})")
_TENTATIVAS_REPLACE = 10
_ESPERA_REPLACE_S = 0.05


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
    """Grava em .tmp e renomeia: um arquivo nunca fica pela metade se o processo cair.

    O nome do .tmp é único por processo+thread — duas gravações concorrentes (a fila da
    produção e, no futuro, outro escritor) nunca disputam o mesmo arquivo temporário.
    """
    tmp = caminho.with_suffix(f"{caminho.suffix}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    _substituir_com_retentativa(tmp, caminho)


def _substituir_com_retentativa(tmp: Path, destino: Path) -> None:
    """No Windows, `replace` pode falhar com `PermissionError` se outro processo/thread
    tiver o destino aberto para leitura (o painel lê o estado.json a cada poucos segundos).
    Tenta de novo por um tempo curto antes de desistir e subir o erro.
    """
    for tentativa in range(_TENTATIVAS_REPLACE):
        try:
            tmp.replace(destino)
            return
        except PermissionError:
            if tentativa == _TENTATIVAS_REPLACE - 1:
                raise
            time.sleep(_ESPERA_REPLACE_S)


def ler_json(caminho: Path) -> Any:
    return json.loads(caminho.read_text(encoding="utf-8"))
