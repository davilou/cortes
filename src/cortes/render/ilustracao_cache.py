"""f4 B-roll, o cache em `cortes/<n>/ilustracao/` (planos 2026-10-02-ilustrado e
2026-10-03-broll-automatico). Os nomes internos `ilustracao*` vêm do f9, que o f4 substituiu.

Dois arquivos, com a mesma chave (início, fim e um hash do texto das palavras que vão no prompt):
- `deixas.json`: a resposta do LLM, a parte cara e determinística. Sobrevive a uma falha de busca
  ou de download, para a nova tentativa não chamar o LLM de novo.
- `ilustracao.json`: a escolha de cada deixa — vídeo do YouTube, foto em tela cheia ou "sem
  visual". Deixa sem visual por falha temporária (YouTube limitado, busca fora do ar, download que
  estourou o prazo ou caiu a rede) leva `transitorio`, e só ela é refeita.
  "Nada a mostrar" (sem deixa, ou a conferência recusou tudo) fica guardado em `vazio`, com o
  motivo: o próximo render dá o mesmo erro sem gastar LLM nem busca.

Corrigir uma palavra da legenda muda o hash e invalida tudo. Cache de antes do `formato` 4 (o
cartão de foto do f9) conta como ausente e é refeito.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from cortes.episodio import ler_json, salvar_json
from cortes.render import broll_video
from cortes.render.ilustracao import TIPOS, Deixa, TipoDeixa, tipo_valido
from cortes.render.processo import ErroRender
from cortes.tipos import Palavra

PASTA = "ilustracao"
ARQUIVO = "ilustracao.json"
ARQUIVO_DEIXAS = "deixas.json"
FORMATO = 4   # 4: vídeo ou foto em tela cheia (f4); o cartão de foto do f9 é refeito
Midia = Literal["video", "foto"]
LICENCA_FOTO = "desconhecida"   # foto de terceiros achada na busca (spec §10)


@dataclass(frozen=True)
class Chave:
    inicio: float
    fim: float
    texto: str   # sha256 dos textos das palavras do prompt das deixas


def chave_de(inicio: float, fim: float, palavras: list[Palavra]) -> Chave:
    textos = json.dumps([p.texto for p in palavras], ensure_ascii=False)
    return Chave(inicio, fim, hashlib.sha256(textos.encode("utf-8")).hexdigest())


@dataclass(frozen=True)
class Fonte:
    url: str                  # vídeo do YouTube, ou página de origem da foto
    canal: str | None = None  # só vídeo
    titulo: str | None = None


@dataclass(frozen=True)
class Ilustracao:
    k: int                    # número da deixa no corte (D<k> da folha; assets/broll-<k>.mp4|jpg)
    deixa: Deixa
    midia: Midia | None       # None = sem visual
    arquivo: Path | None      # o trecho (.mp4) ou a foto em tela cheia (.jpg), em `ilustracao/`
    fonte: Fonte | None
    motivo: str
    falhas: tuple[str, ...]   # buscas e downloads que falharam (relatório da deixa)
    transitorio: bool         # sem visual por falha que outra tentativa pode resolver


@dataclass(frozen=True)
class CacheIlustracao:
    chave: Chave
    ilustracoes: list[Ilustracao]
    vazio: str | None   # motivo do "nada ilustrável" (o erro do render); None = há o que ilustrar


def nome_asset(k: int, midia: Midia) -> str:
    return f"broll-{k}.{'mp4' if midia == 'video' else 'jpg'}"


def miniatura(i: Ilustracao) -> Path | None:
    """O que o editor mostra: o quadro do meio do trecho (`<trecho>-q2.jpg`) ou a própria foto."""
    if i.arquivo is None:
        return None
    return i.arquivo.with_name(f"{i.arquivo.stem}-q2.jpg") if i.midia == "video" else i.arquivo


def _midia(v: Any) -> Midia | None:
    if v is None:
        return None
    if v == "video":
        return "video"
    if v == "foto":
        return "foto"
    raise ValueError(f"mídia inválida: {v!r} (esperado video, foto ou null)")


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


def _licenca(midia: Midia | None) -> dict[str, str | None]:
    """Política de fontes A da spec: o registro vai junto, mesmo sem uso comercial ainda."""
    if midia == "video":
        return {"licenca": broll_video.LICENCA, "risco": broll_video.RISCO}
    return {"licenca": LICENCA_FOTO if midia == "foto" else None, "risco": None}


def _para_json(i: Ilustracao) -> dict[str, Any]:
    f = i.fonte
    return {"k": i.k, **_deixa_json(i.deixa), "midia": i.midia,
            "arquivo": i.arquivo.name if i.arquivo else None, "fonte_url": f.url if f else None,
            "canal": f.canal if f else None, "titulo": f.titulo if f else None, **_licenca(i.midia),
            "motivo": i.motivo, "falhas": list(i.falhas), "transitorio": i.transitorio}


def _arquivo(pasta: Path, nome: Any) -> Path | None:
    """Só um nome de arquivo dentro de `ilustracao/`: `../`, subpasta ou unidade é cache adulterado."""
    if nome is None:
        return None
    if not isinstance(nome, str) or not nome or nome in (".", "..") or Path(nome).name != nome:
        raise ValueError(f"nome de arquivo inválido: {nome!r}")
    return pasta / nome


def _texto(b: dict[str, Any], campo: str, opcional: bool) -> str | None:
    v = b[campo]
    if isinstance(v, str) or (opcional and v is None):
        return v
    raise ValueError(f"{campo} inválido: {v!r} (esperado texto{' ou null' if opcional else ''})")


def _fonte(b: dict[str, Any]) -> Fonte | None:
    if b["fonte_url"] is None:
        return None
    return Fonte(str(_texto(b, "fonte_url", False)), _texto(b, "canal", True), _texto(b, "titulo", True))


def _de_json(pasta: Path, b: dict[str, Any]) -> Ilustracao:
    midia, arquivo = _midia(b["midia"]), _arquivo(pasta, b["arquivo"])
    if (midia is None) != (arquivo is None):
        raise ValueError(f"mídia {midia!r} não combina com o arquivo {b['arquivo']!r}")
    return Ilustracao(int(b["k"]), _deixa(b), midia, arquivo, _fonte(b), str(b["motivo"]),
                      tuple(str(f) for f in b["falhas"]), bool(b["transitorio"]))


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
