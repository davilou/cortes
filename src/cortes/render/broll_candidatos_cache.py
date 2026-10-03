"""f4 B-roll, os candidatos baixados guardados antes da conferência (`ilustracao/candidatos.json`).

A conferência (`claude -p`) e a folha podem falhar depois dos downloads. Sem este arquivo, a nova
tentativa buscaria e baixaria tudo de novo — minutos de YouTube e mais chance de bloqueio. Ele vale
para a mesma chave do corte e para a mesma deixa; candidato cujo arquivo sumiu invalida a deixa,
que é buscada de novo. Depois que a conferência responde, o arquivo é apagado: as deixas
transitórias que voltarem a ser buscadas não podem reaproveitar a busca que falhou.
"""
from pathlib import Path
from typing import Any

from cortes.episodio import ler_json, salvar_json
from cortes.render.broll_candidatos import Achadas, VideoBaixado
from cortes.render.broll_video import VideoCandidato
from cortes.render.ilustracao import Deixa
from cortes.render.ilustracao_cache import FORMATO, Chave, _arquivo, _chave, _chave_json, _deixa, _deixa_json
from cortes.render.ilustracao_imagens import Candidata
from cortes.render.processo import ErroRender

ARQUIVO = "candidatos.json"


def _video_json(v: VideoBaixado) -> dict[str, Any]:
    c = v.candidato
    return {"id": c.id, "dur": c.dur, "canal": c.canal, "titulo": c.titulo, "trecho": v.trecho.name,
            "quadros": [q.name for q in v.quadros]}


def _foto_json(c: Candidata, p: Path) -> dict[str, Any]:
    return {"url": c.url, "origem": c.origem, "largura": c.largura, "altura": c.altura, "arquivo": p.name}


def _achadas_json(k: int, d: Deixa, a: Achadas) -> dict[str, Any]:
    return {"k": k, **_deixa_json(d), "videos": [_video_json(v) for v in a.videos],
            "fotos": [_foto_json(c, p) for c, p in a.fotos], "falhas": a.falhas, "motivo": a.motivo,
            "transitorio": a.transitorio}


def gravar_achadas(pasta: Path, chave: Chave, numeradas: list[tuple[int, Deixa]],
                   achadas: dict[int, Achadas]) -> None:
    salvar_json(pasta / ARQUIVO, {"formato": FORMATO, "chave": _chave_json(chave),
                                  "achadas": [_achadas_json(k, d, achadas[k]) for k, d in numeradas]})


def _caminho(pasta: Path, nome: Any) -> Path:
    p = _arquivo(pasta, nome)
    if p is None:
        raise ValueError("arquivo do candidato ausente")
    return p


def _texto(v: Any) -> str:
    if not isinstance(v, str):
        raise ValueError(f"texto esperado: {v!r}")
    return v


def _medida(v: Any) -> int | None:
    if v is not None and not isinstance(v, int):
        raise ValueError(f"medida inválida: {v!r}")
    return v


def _video(pasta: Path, b: dict[str, Any]) -> VideoBaixado:
    q1, q2, q3 = (_caminho(pasta, q) for q in b["quadros"])
    c = VideoCandidato(_texto(b["id"]), float(b["dur"]), _texto(b["canal"]), _texto(b["titulo"]))
    return VideoBaixado(c, _caminho(pasta, b["trecho"]), (q1, q2, q3))


def _de_json(pasta: Path, b: dict[str, Any]) -> Achadas:
    videos = [_video(pasta, v) for v in b["videos"]]
    fotos = [(Candidata(_texto(f["url"]), _texto(f["origem"]), _medida(f["largura"]), _medida(f["altura"])),
              _caminho(pasta, f["arquivo"])) for f in b["fotos"]]
    return Achadas(videos, fotos, [_texto(f) for f in b["falhas"]], _texto(b["motivo"]),
                   bool(b["transitorio"]))


def _inteira(a: Achadas) -> bool:
    arquivos = [v.trecho for v in a.videos] + [q for v in a.videos for q in v.quadros] + \
               [p for _, p in a.fotos]
    return all(p.exists() for p in arquivos)


def ler_achadas(pasta: Path, chave: Chave, numeradas: list[tuple[int, Deixa]]) -> dict[int, Achadas]:
    """As achadas guardadas das deixas dadas, quando a chave e a deixa batem e os arquivos ainda
    existem. Arquivo de outra chave ou de formato anterior conta como ausente; malformado é erro."""
    arq = pasta / ARQUIVO
    if not arq.exists():
        return {}
    try:
        bruto = ler_json(arq)
        if not isinstance(bruto, dict) or bruto.get("formato") != FORMATO or _chave(bruto["chave"]) != chave:
            return {}
        guardadas = {int(b["k"]): (_deixa(b), _de_json(pasta, b)) for b in bruto["achadas"]}
    except (KeyError, TypeError, ValueError) as e:
        raise ErroRender(f"{arq}: candidatos do B-roll inválidos ({e!r}); refaça o B-roll") from e
    validas: dict[int, Achadas] = {}
    for k, d in numeradas:
        if k in guardadas and guardadas[k][0] == d and _inteira(guardadas[k][1]):
            validas[k] = guardadas[k][1]
    return validas


def apagar_achadas(pasta: Path) -> None:
    (pasta / ARQUIVO).unlink(missing_ok=True)
