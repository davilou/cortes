"""Configuração do painel: contas, formatos e o vocabulário de temas (spec painel §3)."""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from cortes.perfil import carregar_perfil

_ID_CONTA = re.compile(r"^[a-z0-9-]+$")
CAMPOS_CONTA = ("id", "nome", "handle", "nicho", "perfil_studio")


class ErroPainel(ValueError):
    """Configuração ou dado inválido. A mensagem diz o arquivo e o campo."""


@dataclass(frozen=True)
class Conta:
    id: str
    nome: str
    handle: str
    nicho: str
    perfil_studio: str


@dataclass(frozen=True)
class Formato:
    id: str
    nome: str
    obs: str


@dataclass(frozen=True)
class Vocabulario:
    contas: dict[str, Conta]
    formatos: dict[str, Formato]
    temas: frozenset[str]


class _SemRepetidas(yaml.SafeLoader):
    """O SafeLoader aceita chave repetida e fica com a última, em silêncio. Este recusa."""


def _mapa(loader: yaml.Loader | yaml.SafeLoader, node: yaml.Node, deep: bool = False) -> dict[Any, Any]:
    assert isinstance(node, yaml.MappingNode)
    chaves = [loader.construct_object(k, deep=True) for k, _ in node.value]
    if repetidas := sorted({str(k) for k in chaves if chaves.count(k) > 1}):
        raise ErroPainel(f"chave repetida: {repetidas}")
    return loader.construct_mapping(node, deep=deep)


_SemRepetidas.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapa)


def _ler_yaml(arquivo: Path, chave: str) -> Any:
    try:
        dados = yaml.load(arquivo.read_text(encoding="utf-8"), Loader=_SemRepetidas)
    except ErroPainel as e:
        raise ErroPainel(f"{arquivo}: {e}") from e
    if not isinstance(dados, dict) or chave not in dados:
        raise ErroPainel(f"{arquivo}: falta a chave '{chave}'")
    return dados[chave]


def _conta(arquivo: Path, i: int, c: Any, pasta_nichos: Path) -> Conta:
    if not isinstance(c, dict):
        raise ErroPainel(f"{arquivo}: conta #{i} não é um mapa")
    for campo in CAMPOS_CONTA:
        if not isinstance(c.get(campo), str) or not c[campo].strip():
            raise ErroPainel(f"{arquivo}: conta #{i} sem o campo '{campo}'")
    if not _ID_CONTA.match(c["id"]):
        raise ErroPainel(f"{arquivo}: id '{c['id']}' fora do padrão [a-z0-9-]+")
    if not (pasta_nichos / c["nicho"] / "perfil.yaml").exists():
        raise ErroPainel(f"{arquivo}: conta '{c['id']}' usa o nicho '{c['nicho']}', que não existe "
                         f"em {pasta_nichos}")
    return Conta(*(c[campo] for campo in CAMPOS_CONTA))


def carregar_contas(arquivo: Path, pasta_nichos: Path) -> dict[str, Conta]:
    lista = _ler_yaml(arquivo, "contas")
    if not isinstance(lista, list):
        raise ErroPainel(f"{arquivo}: 'contas' deve ser uma lista")
    contas: dict[str, Conta] = {}
    for i, bruto in enumerate(lista, 1):
        conta = _conta(arquivo, i, bruto, pasta_nichos)
        if conta.id in contas:
            raise ErroPainel(f"{arquivo}: id '{conta.id}' repetido")
        contas[conta.id] = conta
    return contas


def carregar_formatos(arquivo: Path) -> dict[str, Formato]:
    mapa = _ler_yaml(arquivo, "formatos")
    if not isinstance(mapa, dict):
        raise ErroPainel(f"{arquivo}: 'formatos' deve ser um mapa {{id: {{nome, obs}}}}")
    formatos: dict[str, Formato] = {}
    for fid, f in mapa.items():
        if not isinstance(f, dict) or not isinstance(f.get("nome"), str):
            raise ErroPainel(f"{arquivo}: formato '{fid}' sem 'nome'")
        formatos[str(fid)] = Formato(str(fid), f["nome"], str(f.get("obs", "")))
    return formatos


def carregar_temas(pasta_nichos: Path) -> frozenset[str]:
    """Temas = tags de bônus e penalidade de todos os perfis: o mesmo vocabulário do detector."""
    temas: set[str] = set()
    for arq in sorted(pasta_nichos.glob("*/perfil.yaml")):
        perfil = carregar_perfil(arq.parent)
        temas |= set(perfil.bonus) | set(perfil.penalidade)
    return frozenset(temas)


def carregar_vocabulario(raiz: Path) -> Vocabulario:
    return Vocabulario(
        contas=carregar_contas(raiz / "contas" / "contas.yaml", raiz / "nichos"),
        formatos=carregar_formatos(raiz / "contas" / "formatos.yaml"),
        temas=carregar_temas(raiz / "nichos"),
    )
