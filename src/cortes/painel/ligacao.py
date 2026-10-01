"""Cortes conhecidos no disco e sugestão do corte pelo título do Short (spec painel §4.2)."""
import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from cortes.episodio import ler_json
from cortes.painel.dados import ErroPainel

_FORMATO = re.compile(r"^(f\d+)-")
_FORA_DE_TESTES = {"comum"}   # código compartilhado, não é corte


@dataclass(frozen=True)
class CorteConhecido:
    caminho: str           # relativo à raiz, com "/"
    nome: str
    formato: str | None    # pelo prefixo da pasta (f7-…), se existir em formatos.yaml
    podcast: str | None    # 'canal' do meta.json do episódio, quando o corte está em episodios/


def _corte(raiz: Path, pasta: Path, formatos: Collection[str], podcast: str | None) -> CorteConhecido:
    m = _FORMATO.match(pasta.name)
    formato = m.group(1) if m and m.group(1) in formatos else None
    return CorteConhecido(pasta.relative_to(raiz).as_posix(), pasta.name, formato, podcast)


def _podcast_do_episodio(meta: Path) -> str | None:
    if not meta.exists():
        return None
    dados = ler_json(meta)
    if not isinstance(dados, dict) or "canal" not in dados:
        raise ErroPainel(f"{meta}: falta a chave 'canal'")
    canal = dados["canal"]
    if not isinstance(canal, str):
        raise ErroPainel(f"{meta}: campo 'canal' deve ser texto, veio {type(canal).__name__}")
    return canal


def listar_cortes(raiz: Path, formatos: Collection[str]) -> list[CorteConhecido]:
    cortes: list[CorteConhecido] = []
    testes = raiz / "testes"
    if testes.is_dir():
        for p in sorted(testes.iterdir()):
            if p.is_dir() and not p.name.startswith(("_", ".")) and p.name not in _FORA_DE_TESTES:
                cortes.append(_corte(raiz, p, formatos, None))
    for p in sorted((raiz / "episodios").glob("*/cortes/*")):
        if p.is_dir():
            meta = p.parent.parent / "meta.json"
            podcast = _podcast_do_episodio(meta)
            cortes.append(_corte(raiz, p, formatos, podcast))
    return cortes


def _palavras(texto: str) -> set[str]:
    texto = re.sub(r"#\w+", " ", texto.lower())
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return {w for w in re.split(r"[^a-z0-9]+", texto) if len(w) >= 3}


def sugerir(titulo: str, cortes: list[CorteConhecido], n: int = 5) -> list[CorteConhecido]:
    """Ordena pela fração das palavras do nome da pasta que aparecem no título; desempata por
    semelhança de texto e, por fim, pelo caminho (ordem determinística). É só sugestão: a tela
    sempre pede confirmação."""
    alvo = _palavras(titulo)

    def nota(c: CorteConhecido) -> tuple[float, float, str]:
        ps = _palavras(c.nome)
        comum = len(alvo & ps) / len(ps) if ps else 0.0
        semelhanca = SequenceMatcher(None, " ".join(sorted(alvo)), " ".join(sorted(ps))).ratio()
        return -comum, -semelhanca, c.caminho

    return sorted(cortes, key=nota)[:n]
