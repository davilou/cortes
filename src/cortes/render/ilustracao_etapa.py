"""f4 B-roll, a etapa inteira (planos 2026-10-02-ilustrado, Task 3, e 2026-10-03-broll-automatico,
Task 3): deixas → vídeos do YouTube e, na deixa literal, fotos (render/broll_candidatos.py) → folha
mista → conferência, com cache em `cortes/<n>/ilustracao/` (render/ilustracao_cache.py).

O pipeline apaga a pasta quando refaz o trecho, como `miniaturas/`. Falha de busca ou de download
numa deixa não derruba o corte: a deixa fica "sem visual" com o motivo, visível no editor, e a
temporária é refeita no próximo render. Mas um f4 sem visual nenhum é erro — nunca um B-roll que
não mostra nada, em silêncio.
"""
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cortes.detector import ChamarLLM
from cortes.llm import ErroLLM
from cortes.render.assets import apagar_clipes
from cortes.render.broll_candidatos import Achadas, DepCandidatos, YouTube, achar
from cortes.render.broll_candidatos_cache import apagar_achadas, gravar_achadas, ler_achadas
from cortes.render.broll_folha import LinhaFolha, dividir_folhas, gerar_folha
from cortes.render.broll_video import foto_cheia
from cortes.render.ilustracao import Deixa, deixas_do_corte
from cortes.render.ilustracao_cache import (
    PASTA,
    Chave,
    Fonte,
    Ilustracao,
    chave_de,
    gravar_deixas,
    gravar_ilustracoes,
    ler_deixas,
    ler_ilustracoes,
    miniatura,
    nome_asset,
)
from cortes.render.ilustracao_conferencia import ChamarComRead, Escolha, conferir
from cortes.render.ilustracao_imagens import BuscaImagens
from cortes.render.processo import ErroRender, Rodar
from cortes.tipos import Palavra

NENHUMA = ("nada a mostrar em B-roll neste corte (nenhuma deixa, ou a conferência recusou todos os "
           "candidatos) — use outro formato")
TEMPORARIA = "nenhum B-roll por falha temporária do YouTube ou da busca de fotos — tente de novo mais tarde"


@dataclass(frozen=True)
class DepIlustracao:
    chamar_llm: ChamarLLM
    chamar_com_read: ChamarComRead
    ddgs: Callable[[], BuscaImagens]
    rodar: Rodar               # folha de conferência
    rodar_download: Rodar      # download das fotos, com prazo curto próprio
    rodar_busca_video: Rodar   # busca no YouTube
    rodar_video: Rodar         # trecho do YouTube, quadros e foto em tela cheia

    def candidatos(self) -> DepCandidatos:
        return DepCandidatos(self.ddgs, self.rodar_download, self.rodar_busca_video, self.rodar_video)


def _foto(k: int, deixa: Deixa, a: Achadas, e: Escolha, j: int, dep: DepIlustracao) -> Ilustracao:
    """A foto escolhida montada em tela cheia; se o ffmpeg falha, a deixa fica sem visual com o
    motivo (refazer não muda a foto nem o ffmpeg: não é transitório)."""
    cand, foto = a.fotos[j - 1]
    cheia = foto.with_name(f"{foto.stem}-cheia.jpg")
    try:
        foto_cheia(foto, cheia, dep.rodar_video)
    except ErroRender as erro:
        return Ilustracao(k, deixa, None, None, None, f"sem visual: a foto {e.candidato} foi escolhida, "
                          f"mas não montou em tela cheia: {erro}", tuple(a.falhas), False)
    return Ilustracao(k, deixa, "foto", cheia, Fonte(cand.origem or cand.url), e.motivo, tuple(a.falhas),
                      False)


def _ilustracao(k: int, deixa: Deixa, a: Achadas, e: Escolha | None, dep: DepIlustracao) -> Ilustracao:
    """A escolha vira o arquivo do clipe: o trecho já baixado, ou a foto montada em tela cheia."""
    falhas = tuple(a.falhas)
    if e is None or e.candidato is None:   # sem candidato (não foi à conferência) ou todos recusados
        motivo = a.motivo if e is None else e.motivo
        return Ilustracao(k, deixa, None, None, None, motivo, falhas, a.transitorio)
    j = int(e.candidato[1:])
    if e.candidato[0] == "F":
        return _foto(k, deixa, a, e, j, dep)
    v = a.videos[j - 1]
    fonte = Fonte(v.candidato.url, v.candidato.canal, v.candidato.titulo)
    return Ilustracao(k, deixa, "video", v.trecho, fonte, e.motivo, falhas, False)


def _achar(pasta: Path, chave: Chave, numeradas: list[tuple[int, Deixa]],
           dep: DepIlustracao) -> dict[int, Achadas]:
    """Os candidatos de cada deixa: os guardados de uma tentativa que falhou depois dos downloads
    ou, sem eles, busca e download — em série, o YouTube nunca recebe dois pedidos ao mesmo tempo.
    Tudo é guardado antes da conferência."""
    guardadas = ler_achadas(pasta, chave, numeradas)
    yt = YouTube()
    achadas = {k: guardadas[k] if k in guardadas else achar(k, deixa, pasta, dep.candidatos(), yt)
               for k, deixa in numeradas}
    gravar_achadas(pasta, chave, numeradas, achadas)
    return achadas


def _escolher(pasta: Path, chave: Chave, numeradas: list[tuple[int, Deixa]],
              dep: DepIlustracao) -> list[Ilustracao]:
    """Busca, baixa e confere as deixas dadas (k, deixa) — numa conferência só."""
    achadas = _achar(pasta, chave, numeradas, dep)
    linhas = [achadas[k].linha(k, deixa) for k, deixa in numeradas]
    escolhas = _conferir(pasta, linhas, dep) if any(ln.rotulos() for ln in linhas) else {}
    ilus = [_ilustracao(k, deixa, achadas[k], escolhas.get(k), dep) for k, deixa in numeradas]
    apagar_achadas(pasta)
    return ilus


def _conferir(pasta: Path, linhas: list[LinhaFolha], dep: DepIlustracao) -> dict[int, Escolha]:
    """Uma folha a cada DEIXAS_POR_FOLHA deixas (`folha-1.jpg`, ...), conferidas numa chamada só."""
    folhas = []
    for i, grupo in enumerate(dividir_folhas(linhas), start=1):
        folhas.append(pasta / f"folha-{i}.jpg")
        gerar_folha(grupo, folhas[-1], dep.rodar)
    return conferir(folhas, linhas, dep.chamar_com_read)


def _deixas(pasta: Path, chave: Chave, palavras: list[Palavra], dur: float,
            dep: DepIlustracao) -> list[Deixa]:
    """De `deixas.json` quando a chave bate; senão a pasta é refeita do zero e o LLM é chamado."""
    deixas = ler_deixas(pasta, chave)
    if deixas is not None:
        return deixas
    if pasta.exists():
        shutil.rmtree(pasta)   # restos de outro início/fim ou de outro texto
    pasta.mkdir(parents=True)
    deixas = deixas_do_corte(palavras, dur, dep.chamar_llm)
    gravar_deixas(pasta, chave, deixas)
    return deixas


def _refazer_temporarias(pasta: Path, chave: Chave, ilus: list[Ilustracao],
                         dep: DepIlustracao) -> list[Ilustracao]:
    novas = {i.k: i for i in _escolher(pasta, chave, [(i.k, i.deixa) for i in ilus if i.transitorio], dep)}
    return [novas.get(i.k, i) for i in ilus]


def _sem_visual(ilus: list[Ilustracao]) -> ErroRender:
    """YouTube limitado ou busca fora do ar não é "nada a mostrar": a mensagem diz o que foi."""
    motivos = "; ".join(f"D{i.k} '{i.deixa.coisa}': {i.motivo}" for i in ilus)
    base = TEMPORARIA if any(i.transitorio for i in ilus) else NENHUMA
    return ErroRender(base + (f" ({motivos})" if motivos else ""))


def _gravar(pasta: Path, chave: Chave, ilus: list[Ilustracao]) -> list[Ilustracao]:
    """Sem visual nenhum é erro; e só fica guardado como `vazio` se nenhuma falha foi temporária."""
    if any(i.arquivo for i in ilus):
        gravar_ilustracoes(pasta, chave, ilus, None)
        return ilus
    erro = _sem_visual(ilus)
    gravar_ilustracoes(pasta, chave, ilus, None if any(i.transitorio for i in ilus) else str(erro))
    raise erro


def _faltando(i: Ilustracao) -> bool:
    mini = miniatura(i)
    return i.arquivo is not None and (not i.arquivo.exists() or mini is None or not mini.exists())


def _cache_vale(pasta: Path, chave: Chave) -> list[Ilustracao] | None:
    """As escolhas do cache desta chave, levantando o "nada a mostrar" guardado; None se o cache
    não vale (outra chave, ou arquivo apagado à mão: refaz a escolha em vez de montar clipe quebrado)."""
    cache = ler_ilustracoes(pasta.parent)
    if cache is None or cache.chave != chave:
        return None
    if any(_faltando(i) for i in cache.ilustracoes):
        return None
    if cache.vazio is not None:
        raise ErroRender(cache.vazio)
    return cache.ilustracoes


def _resolver(pasta: Path, chave: Chave, palavras: list[Palavra], dur: float,
              dep: DepIlustracao) -> list[Ilustracao]:
    ilus = _cache_vale(pasta, chave)
    if ilus is None:
        deixas = _deixas(pasta, chave, palavras, dur, dep)
        return _gravar(pasta, chave, _escolher(pasta, chave, list(enumerate(deixas, start=1)), dep))
    if any(i.transitorio for i in ilus):
        return _gravar(pasta, chave, _refazer_temporarias(pasta, chave, ilus, dep))
    return ilus


def ilustrar(d_corte: Path, ini: float, fim: float, palavras: list[Palavra], dur: float, assets: Path,
             dep: DepIlustracao) -> list[Ilustracao]:
    """B-roll do corte (do cache quando início, fim e texto não mudaram), com os clipes escolhidos
    copiados para `assets/broll-<k>.mp4|jpg` — os de antes são apagados primeiro. `palavras` no
    tempo do trecho sem pausas, com as correções da legenda e sem máscara; `dur` é a duração desse
    trecho."""
    apagar_clipes(assets)
    try:
        ilus = _resolver(d_corte / PASTA, chave_de(ini, fim, palavras), palavras, dur, dep)
    except ErroLLM as e:
        raise ErroRender(f"B-roll: {e}") from e
    for i in ilus:
        if i.arquivo is not None and i.midia is not None:
            shutil.copyfile(i.arquivo, assets / nome_asset(i.k, i.midia))
    return ilus
