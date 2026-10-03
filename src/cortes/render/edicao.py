"""Regras de edição do editor (plano C; spec produção §5): início/fim por palavra, texto da legenda,
mascarar palavrão (só na legenda), título, formato e quem aparece. Puro: recebe o corte e as
palavras do episódio e devolve o corte novo, ou ErroProducao com a causa."""
import re
import unicodedata
from dataclasses import dataclass, field, replace

from cortes.producao.estado import ErroProducao
from cortes.render.corte import Corte, Edicoes
from cortes.render.montagem import validar_formato
from cortes.tipos import Palavra

DURACAO_MIN_S = 3.0
DURACAO_MAX_S = 180.0      # limite do Short no YouTube
TITULO_MAX = 100           # limite do título no YouTube
# Lista fixa (Davi, 2026-10-02): palavrões fortes que o protótipo mascarou e os comuns do português.
PALAVROES = frozenset({
    "porra", "merda", "puta", "puto", "caralho", "foda", "foder", "fodido", "fodeu", "cacete",
    "bosta", "buceta", "cu", "cagado", "cagada", "cagar", "desgraca", "desgracado", "arrombado",
})
AUTOMATICO = -1            # pessoa "automático": apaga a escolha do plano (padrão; no f7, alterna)
_VOGAL = re.compile(r"(?<=\w)[aeiouáéíóúâêôãõà]", re.IGNORECASE)


@dataclass(frozen=True)
class Edicao:
    inicio_palavra: int | None = None
    fim_palavra: int | None = None
    titulo: str | None = None
    formato: str | None = None
    legenda: dict[int, str | None] = field(default_factory=dict)   # None volta ao original
    mascarar: dict[int, bool] = field(default_factory=dict)
    mascarar_palavroes: bool = False
    rosto: tuple[int, int] | None = None                           # (plano, pessoa ou AUTOMATICO)


def mascarar(texto: str) -> str:
    """Primeira vogal depois da primeira letra vira '*' (porra → p*rra), como a legenda dos protótipos."""
    return _VOGAL.sub("*", texto, count=1)


def _normal(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", sem_acento.lower())


def eh_palavrao(texto: str) -> bool:
    return _normal(texto) in PALAVROES


def indices_do_corte(todas: list[Palavra], inicio: float, fim: float) -> tuple[int, int]:
    """Primeira e última palavra que COMEÇAM no corte (mesma tolerância de legenda.palavras_do_corte)."""
    dentro = [i for i, p in enumerate(todas) if inicio - 0.01 <= p.inicio <= fim + 0.01]
    if not dentro:
        raise ErroProducao(f"nenhuma palavra entre {inicio:.2f}s e {fim:.2f}s")
    return dentro[0], dentro[-1]


def palavras_editadas(todas: list[Palavra], ed: Edicoes, *, com_mascara: bool = True) -> list[Palavra]:
    """Texto da legenda com as edições: troca, mascara e tira as apagadas (texto vazio). Sem máscara
    (`com_mascara=False`) é o texto que o LLM lê: "p*rra" não diz nada a ele, e a máscara não tira
    nem põe palavra, então os índices são os mesmos da legenda."""
    res: list[Palavra] = []
    for i, p in enumerate(todas):
        texto = ed.legenda.get(i, p.texto)
        if com_mascara and i in ed.mascaradas:
            texto = mascarar(texto)
        if texto.strip():
            res.append(replace(p, texto=texto))
    return res


def _exigir_indice(i: int, todas: list[Palavra]) -> None:
    if not 0 <= i < len(todas):
        raise ErroProducao(f"palavra {i} não existe (o episódio tem {len(todas)})")


def _janela(c: Corte, ed: Edicao, todas: list[Palavra]) -> Corte:
    if ed.inicio_palavra is None and ed.fim_palavra is None:
        return c
    i0, i1 = indices_do_corte(todas, c.inicio, c.fim)
    i = i0 if ed.inicio_palavra is None else ed.inicio_palavra
    j = i1 if ed.fim_palavra is None else ed.fim_palavra
    _exigir_indice(i, todas)
    _exigir_indice(j, todas)
    if i > j:
        raise ErroProducao("o início tem que vir antes do fim")
    inicio, fim = todas[i].inicio, todas[j].fim
    if not DURACAO_MIN_S <= fim - inicio <= DURACAO_MAX_S:
        raise ErroProducao(f"duração {fim - inicio:.1f}s fora de {DURACAO_MIN_S:.0f}-{DURACAO_MAX_S:.0f}s")
    if (inicio, fim) == (c.inicio, c.fim):
        return c
    return replace(c, inicio=inicio, fim=fim, edicoes=replace(c.edicoes, rostos={}))


def _textos(c: Corte, ed: Edicao, todas: list[Palavra]) -> Corte:
    legenda = dict(c.edicoes.legenda)
    for i, t in ed.legenda.items():
        _exigir_indice(i, todas)
        if t is None or t.strip() == todas[i].texto:
            legenda.pop(i, None)
        else:
            legenda[i] = t.strip()
    masc = set(c.edicoes.mascaradas)
    for i, m in ed.mascarar.items():
        _exigir_indice(i, todas)
        (masc.add if m else masc.discard)(i)
    if ed.mascarar_palavroes:
        i0, i1 = indices_do_corte(todas, c.inicio, c.fim)
        masc |= {i for i in range(i0, i1 + 1) if eh_palavrao(legenda.get(i, todas[i].texto))}
    return replace(c, edicoes=replace(c.edicoes, legenda=legenda, mascaradas=tuple(sorted(masc))))


def _rosto(c: Corte, ed: Edicao, pessoas_por_plano: list[int]) -> Corte:
    if ed.rosto is None:
        return c
    k, j = ed.rosto
    if not 0 <= k < len(pessoas_por_plano):
        raise ErroProducao(f"plano {k} não existe (o trecho tem {len(pessoas_por_plano)})")
    if j == AUTOMATICO:
        rostos = {p: x for p, x in c.edicoes.rostos.items() if p != k}
        return replace(c, edicoes=replace(c.edicoes, rostos=rostos))
    if not 0 <= j < pessoas_por_plano[k]:
        raise ErroProducao(f"pessoa {j} não existe no plano {k}")
    return replace(c, edicoes=replace(c.edicoes, rostos={**c.edicoes.rostos, k: j}))


def _titulo_formato(c: Corte, ed: Edicao) -> Corte:
    if ed.titulo is not None:
        titulo = ed.titulo.strip()
        if not titulo or len(titulo) > TITULO_MAX:
            raise ErroProducao(f"título vazio ou com mais de {TITULO_MAX} caracteres")
        c = replace(c, titulo=titulo)
    if ed.formato is not None:
        validar_formato(ed.formato)
        c = replace(c, formato=ed.formato)
    return c


def aplicar(c: Corte, ed: Edicao, todas: list[Palavra], pessoas_por_plano: list[int]) -> Corte:
    """`pessoas_por_plano[k]` = quantas pessoas o plano k tem (do rosto.json atual)."""
    if ed.rosto is not None and (ed.inicio_palavra is not None or ed.fim_palavra is not None):
        raise ErroProducao(
            "escolha o rosto depois de mudar início/fim: os planos de câmera mudam com o trecho")
    novo = _titulo_formato(_rosto(_textos(_janela(c, ed, todas), ed, todas), ed, pessoas_por_plano), ed)
    return novo if novo == c else replace(novo, alterado=True)
