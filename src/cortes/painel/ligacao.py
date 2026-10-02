"""Cortes conhecidos no disco e sugestão do corte pelo título do Short (spec painel §4.2).

Cortes em `episodios/*/cortes/<n>` usam o título do `corte.json` como nome, para casar com o
título do Short. A tela sempre pede confirmação antes de ligar.
"""
import json
import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from cortes.episodio import ler_json
from cortes.painel.dados import ErroPainel
from cortes.producao.estado import ErroProducao
from cortes.render.corte import ARQUIVO, ler_corte

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


def _podcast_do_episodio(meta: Path) -> str:
    if not meta.exists():
        raise ErroPainel(f"{meta}: arquivo não existe")
    try:
        dados = ler_json(meta)
    except json.JSONDecodeError as e:
        raise ErroPainel(f"{meta}: JSON inválido: {e}") from e
    if not isinstance(dados, dict):
        raise ErroPainel(f"{meta}: esperava um mapa JSON, veio {type(dados).__name__}")
    if "canal" not in dados:
        raise ErroPainel(f"{meta}: falta a chave 'canal'")
    canal = dados["canal"]
    if not isinstance(canal, str):
        raise ErroPainel(f"{meta}: campo 'canal' deve ser texto, veio {type(canal).__name__}")
    return canal


def _corte_de_episodio(raiz: Path, pasta: Path, formatos: Collection[str], podcast: str) -> CorteConhecido:
    if not (pasta / ARQUIVO).exists():
        return _corte(raiz, pasta, formatos, podcast)
    try:
        c = ler_corte(pasta)
    except ErroProducao as ex:
        raise ErroPainel(str(ex)) from ex
    return CorteConhecido(pasta.relative_to(raiz).as_posix(), c.titulo,
                          c.formato if c.formato in formatos else None, podcast)


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
            cortes.append(_corte_de_episodio(raiz, p, formatos, podcast))
    return cortes


def _palavras(texto: str) -> set[str]:
    texto = re.sub(r"#\w+", " ", texto.lower())
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z]+|\d+", texto) if w.isdigit() or len(w) >= 3}


def sugerir(titulo: str, cortes: list[CorteConhecido], n: int = 5) -> list[CorteConhecido]:
    """Ordena pela fração das palavras do nome da pasta que aparecem no título; desempata por
    semelhança de texto e, por fim, pelo caminho (ordem determinística). É só sugestão: a tela
    sempre pede confirmação."""
    alvo = _palavras(titulo)

    def nota(c: CorteConhecido) -> tuple[float, float, str]:
        ps = _palavras(_FORMATO.sub("", c.nome))
        comum = len(alvo & ps) / len(ps) if ps else 0.0
        semelhanca = SequenceMatcher(None, " ".join(sorted(alvo)), " ".join(sorted(ps))).ratio()
        return -comum, -semelhanca, c.caminho

    return sorted(cortes, key=nota)[:n]
