"""f9 Ilustrado, a etapa inteira (plano 2026-10-02-ilustrado, Task 3): deixas → busca e download
→ folha → conferência, com cache em `cortes/<n>/ilustracao/`.

O cache (`ilustracao.json`) vale enquanto o início e o fim do corte não mudarem; o pipeline apaga a
pasta quando refaz o trecho, como `miniaturas/`. Falha de busca ou de download numa deixa não
derruba o corte: a deixa fica "sem imagem" com o motivo, visível no editor. Mas um f9 sem imagem
nenhuma é erro — nunca um Ilustrado que não ilustra nada, em silêncio.
"""
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cortes.detector import ChamarLLM
from cortes.episodio import ler_json, salvar_json
from cortes.llm import ErroLLM
from cortes.render.ilustracao import Deixa, deixas_do_corte
from cortes.render.ilustracao_conferencia import ChamarComRead, conferir
from cortes.render.ilustracao_imagens import (
    BuscaImagens,
    Candidata,
    LinhaFolha,
    baixar_candidatas,
    buscar,
    gerar_folha,
)
from cortes.render.processo import ErroRender, Rodar
from cortes.tipos import Palavra

PASTA = "ilustracao"
ARQUIVO = "ilustracao.json"
FOLHA = "folha.jpg"
N_CANDIDATAS = 4
NENHUMA = "nenhuma coisa concreta ilustrável neste corte — use outro formato"
LICENCA = "desconhecida"   # foto de terceiros achada na busca (risco como o do B-roll, spec §10)


@dataclass(frozen=True)
class DepIlustracao:
    chamar_llm: ChamarLLM
    chamar_com_read: ChamarComRead
    ddgs: Callable[[], BuscaImagens]
    rodar: Rodar            # folha de conferência
    rodar_download: Rodar   # download das candidatas, com prazo curto próprio


@dataclass(frozen=True)
class Ilustracao:
    k: int                    # número da deixa no corte (D<k> da folha; assets/ilus-<k>.jpg)
    deixa: Deixa
    imagem: Path | None       # a candidata escolhida, em `ilustracao/`; None = sem imagem
    fonte_url: str | None     # página de origem da imagem (licença desconhecida)
    motivo: str
    falhas: tuple[str, ...]   # downloads de candidatas que falharam (relatório da deixa)


def _para_json(i: Ilustracao) -> dict[str, Any]:
    d = i.deixa
    return {"k": i.k, "inicio": d.inicio, "fim": d.fim, "coisa": d.coisa, "busca": d.busca,
            "imagem": i.imagem.name if i.imagem else None, "fonte_url": i.fonte_url,
            "licenca": LICENCA if i.imagem else None, "motivo": i.motivo, "falhas": list(i.falhas)}


def _de_json(pasta: Path, b: dict[str, Any]) -> Ilustracao:
    deixa = Deixa(float(b["inicio"]), float(b["fim"]), str(b["coisa"]), str(b["busca"]))
    imagem = pasta / str(b["imagem"]) if b["imagem"] else None
    return Ilustracao(int(b["k"]), deixa, imagem, b["fonte_url"], str(b["motivo"]),
                      tuple(str(f) for f in b["falhas"]))


def ler_ilustracoes(d_corte: Path) -> tuple[float, float, list[Ilustracao]] | None:
    """(início, fim, ilustrações) do cache, ou None se ainda não há. Cache malformado é erro claro."""
    arq = d_corte / PASTA / ARQUIVO
    if not arq.exists():
        return None
    try:
        bruto = ler_json(arq)
        return (float(bruto["inicio"]), float(bruto["fim"]),
                [_de_json(arq.parent, b) for b in bruto["ilustracoes"]])
    except (KeyError, TypeError, ValueError) as e:
        raise ErroRender(f"{arq}: cache da ilustração inválido ({e!r}); refaça o trecho") from e


def _cache(d_corte: Path, ini: float, fim: float) -> list[Ilustracao] | None:
    lido = ler_ilustracoes(d_corte)
    if lido is None or (lido[0], lido[1]) != (ini, fim):
        return None
    ilus = lido[2]
    if any(i.imagem is not None and not i.imagem.exists() for i in ilus):
        return None   # imagem apagada à mão: refaz tudo em vez de montar com cartão quebrado
    return ilus


def _candidatas(k: int, deixa: Deixa, pasta: Path,
                dep: DepIlustracao) -> tuple[list[tuple[Candidata, Path]], list[str], str]:
    """(baixadas, falhas, motivo se nenhuma baixou). Busca que falha é motivo, não exceção."""
    try:
        cands = buscar(deixa.busca, N_CANDIDATAS, dep.ddgs())
    except ErroRender as e:
        return [], [], str(e)
    if not cands:
        return [], [], f"a busca '{deixa.busca}' não trouxe imagem do tamanho mínimo"
    baixadas, falhas = baixar_candidatas(cands, pasta, f"D{k}", dep.rodar_download)
    motivo = "" if baixadas else f"nenhuma candidata baixou: {'; '.join(falhas)}"
    return baixadas, falhas, motivo


def _escolher(pasta: Path, deixas: list[Deixa], dep: DepIlustracao) -> list[Ilustracao]:
    linhas: list[LinhaFolha] = []
    baixadas_por_k: dict[int, list[tuple[Candidata, Path]]] = {}
    sem: dict[int, Ilustracao] = {}
    falhas_por_k: dict[int, tuple[str, ...]] = {}
    for k, deixa in enumerate(deixas, start=1):
        baixadas, falhas, motivo = _candidatas(k, deixa, pasta, dep)
        falhas_por_k[k] = tuple(falhas)
        if not baixadas:
            sem[k] = Ilustracao(k, deixa, None, None, motivo, tuple(falhas))
            continue
        baixadas_por_k[k] = baixadas
        linhas.append(LinhaFolha(k, deixa, tuple(p for _, p in baixadas)))
    escolhas = {}
    if linhas:
        gerar_folha(linhas, pasta / FOLHA, dep.rodar)
        escolhas = conferir(pasta / FOLHA, linhas, dep.chamar_com_read)
    res = []
    for k, deixa in enumerate(deixas, start=1):
        if k in sem:
            res.append(sem[k])
            continue
        e = escolhas[k]
        cand, img = baixadas_por_k[k][e.imagem - 1] if e.imagem is not None else (None, None)
        fonte = (cand.origem or cand.url) if cand else None
        res.append(Ilustracao(k, deixa, img, fonte, e.motivo, falhas_por_k[k]))
    return res


def _calcular(pasta: Path, ini: float, fim: float, palavras: list[Palavra],
              dep: DepIlustracao) -> list[Ilustracao]:
    if pasta.exists():
        shutil.rmtree(pasta)   # restos de um cálculo anterior (outro início/fim ou falha no meio)
    pasta.mkdir(parents=True)
    try:
        deixas = deixas_do_corte(palavras, dep.chamar_llm)
        ilus = _escolher(pasta, deixas, dep) if deixas else []
    except ErroLLM as e:
        raise ErroRender(f"ilustração: {e}") from e
    if not any(i.imagem for i in ilus):
        # sem gravar o cache: busca fora do ar não fica guardada como "nada para ilustrar"
        motivos = "; ".join(f"D{i.k} '{i.deixa.coisa}': {i.motivo}" for i in ilus)
        raise ErroRender(NENHUMA + (f" ({motivos})" if motivos else ""))
    salvar_json(pasta / ARQUIVO, {"inicio": ini, "fim": fim, "ilustracoes": [_para_json(i) for i in ilus]})
    return ilus


def nome_asset(k: int) -> str:
    return f"ilus-{k}.jpg"


def ilustrar(d_corte: Path, ini: float, fim: float, palavras: list[Palavra], assets: Path,
             dep: DepIlustracao) -> list[Ilustracao]:
    """Ilustrações do corte (do cache quando início e fim não mudaram), com as imagens escolhidas
    copiadas para `assets/ilus-<k>.jpg`. `palavras` no tempo do trecho sem pausas."""
    pasta = d_corte / PASTA
    ilus = _cache(d_corte, ini, fim)
    if ilus is None:
        ilus = _calcular(pasta, ini, fim, palavras, dep)
    for i in ilus:
        if i.imagem is not None:
            shutil.copyfile(i.imagem, assets / nome_asset(i.k))
    return ilus
