"""Estado de um episódio na produção: etapas, situação e erro (spec produção §4.3–4.4).

Transições são puras e devolvem um estado novo; ler/gravar é o único I/O.
"""
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

from cortes.episodio import ler_json, salvar_json

ETAPAS = ("video", "legenda", "sinais", "momentos")
SITUACOES = ("pendente", "rodando", "ok", "erro")
Situacao = Literal["pendente", "rodando", "ok", "erro"]


class ErroProducao(ValueError):
    """Pedido ou dado inválido na produção. A mensagem diz o arquivo ou o campo."""


@dataclass(frozen=True)
class Etapa:
    situacao: Situacao = "pendente"
    erro: str | None = None
    atualizado_em: str | None = None


@dataclass(frozen=True)
class EstadoEpisodio:
    id: str
    url: str
    nicho: str
    n_shorts: int
    formato: str
    criado_em: str
    etapas: dict[str, Etapa]


def novo(id: str, url: str, nicho: str, n_shorts: int, formato: str, agora: datetime) -> EstadoEpisodio:
    return EstadoEpisodio(id, url, nicho, n_shorts, formato, agora.isoformat(timespec="seconds"),
                          {nome: Etapa() for nome in ETAPAS})


def marcar(e: EstadoEpisodio, etapa: str, situacao: Situacao, agora: datetime,
           erro: str | None = None) -> EstadoEpisodio:
    if etapa not in ETAPAS:
        raise ErroProducao(f"etapa '{etapa}' não existe; use uma de {ETAPAS}")
    if situacao == "erro" and not erro:
        raise ErroProducao("etapa em erro precisa de mensagem")
    if situacao != "erro" and erro is not None:
        raise ErroProducao("mensagem de erro só em erro")
    nova = Etapa(situacao, erro, agora.isoformat(timespec="seconds"))
    return replace(e, etapas={**e.etapas, etapa: nova})


def etapa_com_erro(e: EstadoEpisodio) -> str | None:
    return next((n for n in ETAPAS if e.etapas[n].situacao == "erro"), None)


def proxima(e: EstadoEpisodio) -> str | None:
    """A primeira etapa não concluída; None se acabou ou se uma etapa está em erro."""
    if etapa_com_erro(e):
        return None
    return next((n for n in ETAPAS if e.etapas[n].situacao != "ok"), None)


def concluido(e: EstadoEpisodio) -> bool:
    return all(e.etapas[n].situacao == "ok" for n in ETAPAS)


def reabrir(e: EstadoEpisodio) -> EstadoEpisodio:
    """'Tentar de novo' e retomada após reinício: erro e rodando voltam a pendente."""
    etapas = {n: Etapa() if et.situacao in ("erro", "rodando") else et for n, et in e.etapas.items()}
    return replace(e, etapas=etapas)


def gravar(pasta: Path, e: EstadoEpisodio) -> None:
    salvar_json(pasta / "estado.json", asdict(e))


def _texto(d: dict[str, Any], campo: str) -> str:
    v = d[campo]
    if not isinstance(v, str):
        raise ValueError(f"campo '{campo}' deveria ser texto, veio {v!r}")
    return v


def _texto_ou_nulo(d: dict[str, Any], campo: str) -> str | None:
    v = d[campo]
    if v is not None and not isinstance(v, str):
        raise ValueError(f"campo '{campo}' deveria ser texto ou nulo, veio {v!r}")
    return v


def _n_shorts(d: dict[str, Any]) -> int:
    v = d["n_shorts"]
    if not isinstance(v, int) or isinstance(v, bool):
        raise ValueError(f"campo 'n_shorts' deveria ser inteiro, veio {v!r}")
    return v


def _situacao(d: dict[str, Any]) -> Situacao:
    v = d["situacao"]
    if v not in SITUACOES:
        raise ValueError(f"situação '{v}' inválida; use uma de {SITUACOES}")
    return cast(Situacao, v)


def _etapa(d: Any) -> Etapa:
    return Etapa(_situacao(d), _texto_ou_nulo(d, "erro"), _texto_ou_nulo(d, "atualizado_em"))


def ler(pasta: Path) -> EstadoEpisodio:
    arquivo = pasta / "estado.json"
    try:
        d = ler_json(arquivo)
        etapas = {n: _etapa(d["etapas"][n]) for n in ETAPAS}
        return EstadoEpisodio(_texto(d, "id"), _texto(d, "url"), _texto(d, "nicho"), _n_shorts(d),
                              _texto(d, "formato"), _texto(d, "criado_em"), etapas)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as ex:
        raise ErroProducao(f"{arquivo}: estado inválido ({ex!r})") from ex
