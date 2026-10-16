"""f3 Motion, os temas (spec 2026-10-15-f3-denso §7; pesquisa/05: um tema por assunto). Puro.

Um tema por Short: o LLM escolhe na chamada das cenas e o editor pode trocar (`Edicoes.tema`). O
tema vira variáveis CSS no motion.tpl — os componentes só usam as variáveis — e a lista de cores
que o SVG livre pode usar (render/motion_svg.py).
"""
from dataclasses import astuple, dataclass

from cortes.render.processo import ErroRender


@dataclass(frozen=True)
class Paleta:
    fundo: str
    cartao: str
    linha: str      # bordas finas e grades
    texto: str
    suave: str      # rótulos pequenos
    acento: str
    perda: str      # carimbo, sinal de "não"
    serifa: bool    # títulos em serifa (o "Residencial Aurora" do reel)


TEMAS: dict[str, Paleta] = {
    "escuro": Paleta("#0d0d0f", "#17171b", "#2a2a31", "#f2f2f2", "#8d8d96", "#ff6a3d", "#ff4d5e", False),
    "noite": Paleta("#0b1424", "#12203a", "#24365a", "#eef2f8", "#8fa0bd", "#d9b46a", "#ff6b6b", True),
    "clinico": Paleta("#f4f6f8", "#ffffff", "#dde3ea", "#16202a", "#6b7886", "#2f7de1", "#e5484d", False),
    "dados": Paleta("#0c1512", "#13211c", "#22362e", "#eaf4ef", "#86a397", "#3ddc84", "#ff5d4f", False),
    # f10 (Motion v2): cartões claros e acento roxo sobre o fundo que alterna entre claro pontilhado e
    # marinho (render/motion2.py); fixo, o LLM não escolhe
    "bolo": Paleta("#f4f2fb", "#ffffff", "#e3def5", "#0d0b1a", "#7a7690", "#7b5cff", "#e5484d", False),
}
TEMA_PADRAO = "escuro"
TEMA_F10 = "bolo"
TEMAS_LLM = tuple(t for t in TEMAS if t != TEMA_F10)   # os que o Claude escolhe para o f3


def paleta(nome: str) -> Paleta:
    if nome not in TEMAS:
        raise ErroRender(f"tema '{nome}' não existe; use um de {tuple(TEMAS)}")
    return TEMAS[nome]


def css_do_tema(nome: str) -> str:
    p = paleta(nome)
    titulo = '"Georgia", "Times New Roman", serif' if p.serifa else '"Montserrat", sans-serif'
    return (f":root {{ --bg: {p.fundo}; --cartao: {p.cartao}; --linha: {p.linha}; --fg: {p.texto}; "
            f"--muted: {p.suave}; --brand: {p.acento}; --perda: {p.perda}; --fonte-titulo: {titulo}; }}")


def cores_do_tema(nome: str) -> frozenset[str]:
    return frozenset(c.lower() for c in astuple(paleta(nome)) if isinstance(c, str))
