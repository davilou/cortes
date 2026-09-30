"""Rejeita candidato que abre com conectivo de continuação (pesquisa R1: erro nº 1 dos fracassos)."""
import re

_CONECTIVO = re.compile(
    r"^(mas|também|e aí|aí|daí|e|só que|porque|até|ou seja|inclusive|pois)\b", re.IGNORECASE)
_LIXO_INICIAL = "-—–…\"'"" "


def comeca_no_meio(texto: str) -> bool:
    return bool(_CONECTIVO.match(texto.lstrip(_LIXO_INICIAL)))
