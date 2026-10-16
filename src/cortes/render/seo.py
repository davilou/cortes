"""SEO do Short para postar no YouTube: título, descrição, hashtags e tags, gravados em
cortes/<indice>/seo.json junto do MP4.

Gerado no render, antes do MP4 (o passo de minutos), com cache pelo texto do corte: renderizar de
novo sem mudar o texto não chama o LLM outra vez. As regras de SEO não vêm da pesquisa (`pesquisa/`
não cobre metadados); vêm da skill `youtube-descricao-e-tags` e da ajuda do YouTube Studio:
título até 100 caracteres, descrição até 5.000, sem `<` nem `>`, tags até 500 caracteres no total
(tag com espaço conta as aspas), hashtags opcionais e poucas, URL em descrição de Short não é
clicável, e tag só para variação e grafia relevantes.
"""
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cortes.detector import ChamarLLM
from cortes.episodio import ler_json, salvar_json
from cortes.llm import ErroLLM
from cortes.render.corte import Corte, pasta_corte
from cortes.render.edicao import palavras_editadas
from cortes.render.legenda import palavras_do_corte
from cortes.render.motion_prompt import Contexto
from cortes.render.processo import ErroRender
from cortes.tipos import Palavra

ARQUIVO = "seo.json"
MODELO = "sonnet"
MAX_TITULO = 100
MAX_DESCRICAO = 5000
MAX_TAGS = 500
_HASHTAG = re.compile(r"^#\w+$")

SISTEMA = """Você escreve os metadados de YouTube Shorts em português brasileiro: cortes de podcast.
Regras:
- Título: até 100 caracteres, específico, com a ideia mais forte do trecho. Pode ter o nome de quem
  fala se ajudar a busca. Nada de clickbait que o trecho não paga, nada de #shorts no título.
- Descrição: 2 a 4 frases curtas. A primeira diz o assunto e o ganho de assistir; depois o contexto
  (quem fala, em qual podcast). Sem links, sem lista de tags, sem promessa de vídeo futuro.
- Hashtags: de 0 a 3, relevantes ao tema, sem acento, em minúsculas, começando com #.
- Tags: poucas (até 10), termos de busca reais e grafias alternativas de nomes; nada genérico.
- Fidelidade: só o que está no trecho e no contexto. Não invente número, resultado nem fato.
- Sem palavrão, sem os caracteres < e >."""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["titulo", "descricao", "hashtags", "tags"],
    "properties": {
        "titulo": {"type": "string", "minLength": 1, "maxLength": MAX_TITULO},
        "descricao": {"type": "string", "minLength": 1, "maxLength": MAX_DESCRICAO},
        "hashtags": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
        "tags": {"type": "array", "maxItems": 15, "items": {"type": "string", "minLength": 1}},
    },
}


@dataclass(frozen=True)
class Seo:
    titulo: str
    descricao: str
    hashtags: tuple[str, ...]
    tags: tuple[str, ...]


def texto_do_corte(todas: list[Palavra], c: Corte, ini: float, fim: float) -> str:
    """O que se fala no corte, com as edições e sem máscara (o LLM precisa ler a palavra)."""
    ws = palavras_do_corte(palavras_editadas(todas, c.edicoes, com_mascara=False), ini, fim)
    return " ".join(p.texto for p in ws)


def montar_prompt(texto: str, ctx: Contexto, titulo_corte: str) -> str:
    return (f"Podcast: {ctx.canal}\nEpisódio: {ctx.titulo}\nIdeia do corte: {titulo_corte}\n\n"
            f"Fala do corte:\n{texto}")


def tamanho_tags(tags: tuple[str, ...]) -> int:
    """Como a API conta o campo: vírgula entre tags e aspas em volta da tag com espaço."""
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + max(0, len(tags) - 1)


def validar(dados: dict[str, Any]) -> Seo:
    s = Seo(dados["titulo"].strip(), dados["descricao"].strip(),
            tuple(h.strip() for h in dados["hashtags"]), tuple(t.strip() for t in dados["tags"]))
    if not s.titulo or not s.descricao:
        raise ErroRender("SEO veio com título ou descrição vazios")
    for campo, valor in (("título", s.titulo), ("descrição", s.descricao)):
        if "<" in valor or ">" in valor:
            raise ErroRender(f"SEO: {campo} com < ou > (o YouTube recusa): {valor[:120]}")
    if ruins := [h for h in s.hashtags if not _HASHTAG.match(h)]:
        raise ErroRender(f"SEO: hashtag fora do formato #palavra: {ruins}")
    if (n := tamanho_tags(s.tags)) > MAX_TAGS:
        raise ErroRender(f"SEO: tags com {n} caracteres, o YouTube aceita até {MAX_TAGS}")
    return s


def ler_seo(d_corte: Path) -> Seo | None:
    arq = d_corte / ARQUIVO
    if not arq.exists():
        return None
    return validar(ler_json(arq))


def preparar_seo(pasta_ep: Path, c: Corte, texto: str, ctx: Contexto, chamar: ChamarLLM) -> Seo:
    """Do cache quando o texto do corte e a ideia não mudaram; senão chama o LLM e grava."""
    arq = pasta_corte(pasta_ep, c.indice) / ARQUIVO
    chave = {"texto": texto, "titulo_corte": c.titulo}
    if arq.exists():
        lido = ler_json(arq)
        if lido.get("chave") == chave:
            return validar(lido)
    try:
        dados = chamar(montar_prompt(texto, ctx, c.titulo), SCHEMA, SISTEMA, MODELO)
    except ErroLLM as e:
        raise ErroRender(f"SEO: {e}") from e
    s = validar(dados)
    arq.parent.mkdir(parents=True, exist_ok=True)
    salvar_json(arq, {**asdict(s), "chave": chave})
    return s
