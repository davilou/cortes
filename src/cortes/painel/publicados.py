"""publicados.jsonl: liga cada Short no YouTube ao corte que o gerou (spec painel §3.3)."""
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from cortes.painel.dados import ErroPainel, Vocabulario

_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")


@dataclass(frozen=True)
class Etiquetas:
    formato: str
    temas: tuple[str, ...]
    podcast: str


@dataclass(frozen=True)
class Publicado:
    video_id: str
    conta: str
    publicado_em: date
    corte: str
    etiquetas: Etiquetas


def validar(p: Publicado, voc: Vocabulario) -> None:
    """Falha alto para dado fora do vocabulário.

    Temas vazio é permitido (o Short só fica fora dos grupos por tema).
    """
    if not p.video_id or not _VIDEO_ID.fullmatch(p.video_id):
        raise ErroPainel(f"video_id inválido: {p.video_id!r}")
    if p.conta not in voc.contas:
        raise ErroPainel(f"conta '{p.conta}' não existe em contas.yaml")
    if p.etiquetas.formato not in voc.formatos:
        raise ErroPainel(f"formato '{p.etiquetas.formato}' não existe em formatos.yaml")
    if fora := sorted(set(p.etiquetas.temas) - voc.temas):
        raise ErroPainel(f"temas fora do vocabulário dos perfis de nicho: {fora}")
    if dups := sorted({t for t in p.etiquetas.temas if p.etiquetas.temas.count(t) > 1}):
        raise ErroPainel(f"temas repetidos: {dups}")
    if not p.etiquetas.podcast.strip():
        raise ErroPainel("podcast vazio")
    if not p.corte.strip():
        raise ErroPainel("corte vazio")


def _para_dict(p: Publicado) -> dict[str, Any]:
    e = p.etiquetas
    etiquetas = {"formato": e.formato, "temas": list(e.temas), "podcast": e.podcast}
    return {"video_id": p.video_id, "conta": p.conta, "publicado_em": p.publicado_em.isoformat(),
            "corte": p.corte, "etiquetas": etiquetas}


def _texto(d: Any, campo: str) -> str:
    v = d[campo]
    if not isinstance(v, str):
        raise ErroPainel(f"campo '{campo}' não é texto")
    return v


def _lista_textos(d: Any, campo: str) -> tuple[str, ...]:
    v = d[campo]
    if not isinstance(v, list) or not all(isinstance(t, str) for t in v):
        raise ErroPainel(f"campo '{campo}' deve ser lista de textos")
    return tuple(v)


def _de_dict(d: Any) -> Publicado:
    try:
        e = d["etiquetas"]
        return Publicado(_texto(d, "video_id"), _texto(d, "conta"), date.fromisoformat(d["publicado_em"]),
                         _texto(d, "corte"),
                         Etiquetas(_texto(e, "formato"), _lista_textos(e, "temas"), _texto(e, "podcast")))
    except (KeyError, TypeError, ValueError) as ex:
        raise ErroPainel(f"linha inválida ({ex!r})") from ex


def ler_publicados(arquivo: Path, voc: Vocabulario) -> list[Publicado]:
    if not arquivo.exists():
        return []  # nenhum Short ligado ainda: o arquivo nasce na primeira ligação
    lista: list[Publicado] = []
    vistos: set[str] = set()
    for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
        if not linha.strip():
            continue
        try:
            p = _de_dict(json.loads(linha))
            validar(p, voc)
        except (json.JSONDecodeError, ErroPainel) as e:
            raise ErroPainel(f"{arquivo}:{n}: {e}") from e
        if p.video_id in vistos:
            raise ErroPainel(f"{arquivo}:{n}: video_id '{p.video_id}' repetido")
        vistos.add(p.video_id)
        lista.append(p)
    return lista


def ligar(lista: list[Publicado], novo: Publicado, voc: Vocabulario) -> list[Publicado]:
    """Religar o mesmo vídeo substitui a ligação anterior."""
    validar(novo, voc)
    return [p for p in lista if p.video_id != novo.video_id] + [novo]


def gravar_publicados(arquivo: Path, lista: list[Publicado]) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    tmp = arquivo.with_suffix(arquivo.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(_para_dict(p), ensure_ascii=False) + "\n" for p in lista),
                   encoding="utf-8")
    tmp.replace(arquivo)
