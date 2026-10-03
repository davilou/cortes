"""f9 Ilustrado, a etapa inteira (plano 2026-10-02-ilustrado, Task 3): deixas → busca e download
→ folha → conferência, com cache em `cortes/<n>/ilustracao/` (render/ilustracao_cache.py).

O pipeline apaga a pasta quando refaz o trecho, como `miniaturas/`. Falha de busca ou de download
numa deixa não derruba o corte: a deixa fica "sem imagem" com o motivo, visível no editor, e a
temporária é refeita no próximo render. Mas um f9 sem imagem nenhuma é erro — nunca um Ilustrado
que não ilustra nada, em silêncio.
"""
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cortes.detector import ChamarLLM
from cortes.llm import ErroLLM
from cortes.render.ilustracao import Deixa, deixas_do_corte
from cortes.render.ilustracao_cache import (
    PASTA,
    Chave,
    Ilustracao,
    chave_de,
    gravar_deixas,
    gravar_ilustracoes,
    ler_deixas,
    ler_ilustracoes,
    nome_asset,
)
from cortes.render.ilustracao_conferencia import ChamarComRead, Escolha, conferir
from cortes.render.ilustracao_imagens import (
    ERRO_BUSCA,
    BuscaImagens,
    Candidata,
    ErroBusca,
    LinhaFolha,
    baixar_candidatas,
    buscar,
    dividir_folhas,
    falha_temporaria,
    gerar_folha,
)
from cortes.render.processo import ErroRender, Rodar
from cortes.tipos import Palavra

N_CANDIDATAS = 4
NENHUMA = "nenhuma coisa concreta ilustrável neste corte — use outro formato"
BUSCA_FORA = "a busca de imagens falhou em todas as deixas — tente de novo mais tarde"
TEMPORARIA = "nenhuma imagem por falha temporária de busca ou download — tente de novo mais tarde"


@dataclass(frozen=True)
class DepIlustracao:
    chamar_llm: ChamarLLM
    chamar_com_read: ChamarComRead
    ddgs: Callable[[], BuscaImagens]
    rodar: Rodar            # folha de conferência
    rodar_download: Rodar   # download das candidatas, com prazo curto próprio


@dataclass(frozen=True)
class Achadas:
    """O que a busca e o download deram para uma deixa."""
    baixadas: list[tuple[Candidata, Path]]
    falhas: list[str]
    motivo: str          # por que ficou sem candidata ("" se alguma baixou)
    transitorio: bool    # sem candidata por falha que outra tentativa pode resolver


def _candidatas(k: int, deixa: Deixa, pasta: Path, dep: DepIlustracao) -> Achadas:
    """Busca que falha é motivo, não exceção. Busca fora do ar e download que caiu por prazo ou rede
    são temporários; nada achado ou só 404 não."""
    try:
        cands = buscar(deixa.busca, N_CANDIDATAS, dep.ddgs())
    except ErroBusca as e:
        return Achadas([], [], str(e), True)
    if not cands:
        return Achadas([], [], f"sem imagem: a busca '{deixa.busca}' não achou nada do tamanho mínimo", False)
    baixadas, falhas = baixar_candidatas(cands, pasta, f"D{k}", dep.rodar_download)
    if baixadas:
        return Achadas(baixadas, falhas, "", False)
    return Achadas([], falhas, f"nenhuma candidata baixou: {'; '.join(falhas)}",
                   any(falha_temporaria(f) for f in falhas))


def _ilustracao(k: int, deixa: Deixa, a: Achadas, e: Escolha | None) -> Ilustracao:
    if e is None:   # nenhuma candidata baixou: não foi à conferência
        return Ilustracao(k, deixa, None, None, a.motivo, tuple(a.falhas), a.transitorio)
    cand, img = a.baixadas[e.imagem - 1] if e.imagem is not None else (None, None)
    fonte = (cand.origem or cand.url) if cand else None
    return Ilustracao(k, deixa, img, fonte, e.motivo, tuple(a.falhas), False)


def _escolher(pasta: Path, numeradas: list[tuple[int, Deixa]], dep: DepIlustracao) -> list[Ilustracao]:
    """Busca, baixa e confere as deixas dadas (k, deixa) — numa conferência só."""
    achadas = {k: _candidatas(k, deixa, pasta, dep) for k, deixa in numeradas}
    linhas = [LinhaFolha(k, deixa, tuple(p for _, p in achadas[k].baixadas))
              for k, deixa in numeradas if achadas[k].baixadas]
    escolhas = _conferir(pasta, linhas, dep) if linhas else {}
    return [_ilustracao(k, deixa, achadas[k], escolhas.get(k)) for k, deixa in numeradas]


def _conferir(pasta: Path, linhas: list[LinhaFolha], dep: DepIlustracao) -> dict[int, Escolha]:
    """Uma folha a cada DEIXAS_POR_FOLHA deixas (`folha-1.jpg`, ...), conferidas numa chamada só."""
    folhas = []
    for i, grupo in enumerate(dividir_folhas(linhas), start=1):
        folhas.append(pasta / f"folha-{i}.jpg")
        gerar_folha(grupo, folhas[-1], dep.rodar)
    return conferir(folhas, linhas, dep.chamar_com_read)


def _deixas(pasta: Path, chave: Chave, palavras: list[Palavra], dep: DepIlustracao) -> list[Deixa]:
    """De `deixas.json` quando a chave bate; senão a pasta é refeita do zero e o LLM é chamado."""
    deixas = ler_deixas(pasta, chave)
    if deixas is not None:
        return deixas
    if pasta.exists():
        shutil.rmtree(pasta)   # restos de outro início/fim ou de outro texto
    pasta.mkdir(parents=True)
    deixas = deixas_do_corte(palavras, dep.chamar_llm)
    gravar_deixas(pasta, chave, deixas)
    return deixas


def _refazer_temporarias(pasta: Path, ilus: list[Ilustracao], dep: DepIlustracao) -> list[Ilustracao]:
    novas = {i.k: i for i in _escolher(pasta, [(i.k, i.deixa) for i in ilus if i.transitorio], dep)}
    return [novas.get(i.k, i) for i in ilus]


def _sem_imagem(ilus: list[Ilustracao]) -> ErroRender:
    """Busca fora do ar ou download caído não é "nada ilustrável": a mensagem diz o que foi."""
    motivos = "; ".join(f"D{i.k} '{i.deixa.coisa}': {i.motivo}" for i in ilus)
    if ilus and all(i.motivo.startswith(ERRO_BUSCA) for i in ilus):
        base = BUSCA_FORA
    else:
        base = TEMPORARIA if any(i.transitorio for i in ilus) else NENHUMA
    return ErroRender(base + (f" ({motivos})" if motivos else ""))


def _gravar(pasta: Path, chave: Chave, ilus: list[Ilustracao]) -> list[Ilustracao]:
    """Sem imagem nenhuma é erro; e só fica guardado como `vazio` se nenhuma falha foi temporária."""
    if any(i.imagem for i in ilus):
        gravar_ilustracoes(pasta, chave, ilus, None)
        return ilus
    erro = _sem_imagem(ilus)
    gravar_ilustracoes(pasta, chave, ilus, None if any(i.transitorio for i in ilus) else str(erro))
    raise erro


def _cache_vale(pasta: Path, chave: Chave) -> list[Ilustracao] | None:
    """As ilustrações do cache desta chave, levantando o "nada ilustrável" guardado; None se o cache
    não vale (outra chave, ou imagem apagada à mão: refaz a escolha em vez de montar cartão quebrado)."""
    cache = ler_ilustracoes(pasta.parent)
    if cache is None or cache.chave != chave:
        return None
    if any(i.imagem is not None and not i.imagem.exists() for i in cache.ilustracoes):
        return None
    if cache.vazio is not None:
        raise ErroRender(cache.vazio)
    return cache.ilustracoes


def _resolver(pasta: Path, chave: Chave, palavras: list[Palavra], dep: DepIlustracao) -> list[Ilustracao]:
    ilus = _cache_vale(pasta, chave)
    if ilus is None:
        deixas = _deixas(pasta, chave, palavras, dep)
        return _gravar(pasta, chave, _escolher(pasta, list(enumerate(deixas, start=1)), dep))
    if any(i.transitorio for i in ilus):
        return _gravar(pasta, chave, _refazer_temporarias(pasta, ilus, dep))
    return ilus


def ilustrar(d_corte: Path, ini: float, fim: float, palavras: list[Palavra], assets: Path,
             dep: DepIlustracao) -> list[Ilustracao]:
    """Ilustrações do corte (do cache quando início, fim e texto não mudaram), com as imagens
    escolhidas copiadas para `assets/ilus-<k>.jpg` — os cartões de antes são apagados primeiro.
    `palavras` no tempo do trecho sem pausas, com as correções da legenda e sem máscara."""
    for velho in assets.glob("ilus-*.jpg"):
        velho.unlink()
    try:
        ilus = _resolver(d_corte / PASTA, chave_de(ini, fim, palavras), palavras, dep)
    except ErroLLM as e:
        raise ErroRender(f"ilustração: {e}") from e
    for i in ilus:
        if i.imagem is not None:
            shutil.copyfile(i.imagem, assets / nome_asset(i.k))
    return ilus
