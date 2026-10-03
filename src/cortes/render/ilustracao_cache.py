"""f9 Ilustrado, o cache em `cortes/<n>/ilustracao/` (plano 2026-10-02-ilustrado, Task 3).

Dois arquivos, com a mesma chave (início, fim e um hash do texto das palavras que vão no prompt):
- `deixas.json`: a resposta do LLM, a parte cara e determinística. Sobrevive a uma falha de busca
  ou de download, para a nova tentativa não chamar o LLM de novo.
- `ilustracao.json`: a escolha de cada deixa. Deixa "sem imagem" por falha temporária (busca fora
  do ar, download que estourou o prazo ou caiu a rede) leva `transitorio`, e só ela é refeita.
  "Nada ilustrável" (sem deixa, ou a conferência recusou tudo) fica guardado em `vazio`, com o
  motivo: o próximo render dá o mesmo erro sem gastar LLM nem busca.

Corrigir uma palavra da legenda muda o hash e invalida tudo. Cache de antes do `formato` 3 (sem a
chave do texto ou sem o `tipo` da deixa) conta como ausente e é refeito.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cortes.episodio import ler_json, salvar_json
from cortes.render.ilustracao import TIPOS, Deixa, TipoDeixa, tipo_valido
from cortes.render.processo import ErroRender
from cortes.tipos import Palavra

PASTA = "ilustracao"
ARQUIVO = "ilustracao.json"
ARQUIVO_DEIXAS = "deixas.json"
FORMATO = 3   # 3: a deixa ganhou `tipo` (B-roll); cache de antes é refeito
LICENCA = "desconhecida"   # foto de terceiros achada na busca (risco como o do B-roll, spec §10)


@dataclass(frozen=True)
class Chave:
    inicio: float
    fim: float
    texto: str   # sha256 dos textos das palavras do prompt das deixas


def chave_de(inicio: float, fim: float, palavras: list[Palavra]) -> Chave:
    textos = json.dumps([p.texto for p in palavras], ensure_ascii=False)
    return Chave(inicio, fim, hashlib.sha256(textos.encode("utf-8")).hexdigest())


@dataclass(frozen=True)
class Ilustracao:
    k: int                    # número da deixa no corte (D<k> da folha; assets/ilus-<k>.jpg)
    deixa: Deixa
    imagem: Path | None       # a candidata escolhida, em `ilustracao/`; None = sem imagem
    fonte_url: str | None     # página de origem da imagem (licença desconhecida)
    motivo: str
    falhas: tuple[str, ...]   # downloads de candidatas que falharam (relatório da deixa)
    transitorio: bool         # sem imagem por falha que outra tentativa pode resolver


@dataclass(frozen=True)
class CacheIlustracao:
    chave: Chave
    ilustracoes: list[Ilustracao]
    vazio: str | None   # motivo do "nada ilustrável" (o erro do render); None = há o que ilustrar


def nome_asset(k: int) -> str:
    return f"ilus-{k}.jpg"


def _chave_json(c: Chave) -> dict[str, Any]:
    return {"inicio": c.inicio, "fim": c.fim, "texto": c.texto}


def _chave(b: dict[str, Any]) -> Chave:
    return Chave(float(b["inicio"]), float(b["fim"]), str(b["texto"]))


def _deixa_json(d: Deixa) -> dict[str, Any]:
    return {"inicio": d.inicio, "fim": d.fim, "coisa": d.coisa, "busca": d.busca, "tipo": d.tipo}


def _tipo(v: Any) -> TipoDeixa:
    t = tipo_valido(v)
    if t is not None:
        return t
    raise ValueError(f"tipo de deixa inválido: {v!r} (esperado um de {', '.join(TIPOS)})")


def _deixa(b: dict[str, Any]) -> Deixa:
    return Deixa(float(b["inicio"]), float(b["fim"]), str(b["coisa"]), str(b["busca"]), _tipo(b["tipo"]))


def _para_json(i: Ilustracao) -> dict[str, Any]:
    return {"k": i.k, **_deixa_json(i.deixa), "imagem": i.imagem.name if i.imagem else None,
            "fonte_url": i.fonte_url, "licenca": LICENCA if i.imagem else None, "motivo": i.motivo,
            "falhas": list(i.falhas), "transitorio": i.transitorio}


def _imagem(pasta: Path, nome: Any) -> Path | None:
    """Só um nome de arquivo dentro de `ilustracao/`: `../`, subpasta ou unidade é cache adulterado."""
    if nome is None:
        return None
    if not isinstance(nome, str) or not nome or nome in (".", "..") or Path(nome).name != nome:
        raise ValueError(f"nome de imagem inválido: {nome!r}")
    return pasta / nome


def _de_json(pasta: Path, b: dict[str, Any]) -> Ilustracao:
    return Ilustracao(int(b["k"]), _deixa(b), _imagem(pasta, b["imagem"]), b["fonte_url"],
                      str(b["motivo"]), tuple(str(f) for f in b["falhas"]), bool(b["transitorio"]))


def _ler(arq: Path) -> dict[str, Any] | None:
    """O JSON do cache, ou None se não existe ou é de formato anterior."""
    if not arq.exists():
        return None
    bruto = ler_json(arq)
    if not isinstance(bruto, dict) or bruto.get("formato") != FORMATO:
        return None
    return bruto


def ler_ilustracoes(d_corte: Path) -> CacheIlustracao | None:
    """O cache das escolhas, ou None se ainda não há. Cache malformado é erro claro."""
    arq = d_corte / PASTA / ARQUIVO
    try:
        bruto = _ler(arq)
        if bruto is None:
            return None
        vazio = bruto["vazio"]
        ilus = [_de_json(arq.parent, b) for b in bruto["ilustracoes"]]
        return CacheIlustracao(_chave(bruto["chave"]), ilus, None if vazio is None else str(vazio))
    except (KeyError, TypeError, ValueError) as e:
        raise ErroRender(f"{arq}: cache da ilustração inválido ({e!r}); refaça a ilustração") from e


def gravar_ilustracoes(pasta: Path, chave: Chave, ilus: list[Ilustracao], vazio: str | None) -> None:
    salvar_json(pasta / ARQUIVO, {"formato": FORMATO, "chave": _chave_json(chave), "vazio": vazio,
                                  "ilustracoes": [_para_json(i) for i in ilus]})


def ler_deixas(pasta: Path, chave: Chave) -> list[Deixa] | None:
    """As deixas guardadas para esta chave, ou None (sem arquivo, outra chave ou formato anterior)."""
    arq = pasta / ARQUIVO_DEIXAS
    try:
        bruto = _ler(arq)
        if bruto is None or _chave(bruto["chave"]) != chave:
            return None
        return [_deixa(b) for b in bruto["deixas"]]
    except (KeyError, TypeError, ValueError) as e:
        raise ErroRender(f"{arq}: cache das deixas inválido ({e!r}); refaça a ilustração") from e


def gravar_deixas(pasta: Path, chave: Chave, deixas: list[Deixa]) -> None:
    salvar_json(pasta / ARQUIVO_DEIXAS, {"formato": FORMATO, "chave": _chave_json(chave),
                                         "deixas": [_deixa_json(d) for d in deixas]})
