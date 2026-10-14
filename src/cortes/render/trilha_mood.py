"""Tom do corte para escolher a cama (spec trilha §4; pesquisa/04-trilha.md R8).

Uma chamada `claude -p` por texto de corte, com cache em `cortes/<n>/trilha.json`: renderizar de
novo sem mudar o texto não chama o LLM. Na dúvida, "neutro": música tensa por baixo de fala neutra
muda o julgamento sobre quem fala (Boltz 2001, R8).
"""
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cortes.detector import ChamarLLM
from cortes.episodio import ler_json, salvar_json
from cortes.llm import ErroLLM
from cortes.render.corte import Corte
from cortes.render.edicao import palavras_editadas
from cortes.render.legenda import palavras_do_corte
from cortes.render.processo import ErroRender
from cortes.render.trilha_biblioteca import MOODS
from cortes.tipos import Palavra

ARQUIVO = "trilha.json"
MODELO = "sonnet"
SISTEMA = """Você classifica o tom de um corte de podcast em português brasileiro para escolher a
música de fundo. Moods:
- "tensao": o trecho causa espanto, medo, raiva ou alerta (perda de dinheiro, crise, golpe, risco).
- "leve": o trecho é engraçado ou descontraído; há piada ou riso.
- "neutro": explicação, opinião ou conversa sem carga forte.
Na dúvida, "neutro": música tensa por baixo de fala neutra faz quem fala parecer suspeito.
O motivo é curto (até 120 caracteres) e cita o que no trecho decidiu."""
SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["mood", "motivo"],
    "properties": {
        "mood": {"type": "string", "enum": list(MOODS)},
        "motivo": {"type": "string", "minLength": 1, "maxLength": 200},
    },
}


def texto_para_mood(todas: list[Palavra], c: Corte, ini: float, fim: float) -> str:
    """O que se fala no corte, com as edições e sem máscara (o LLM precisa ler a palavra)."""
    ws = palavras_do_corte(palavras_editadas(todas, c.edicoes, com_mascara=False), ini, fim)
    return " ".join(p.texto for p in ws)


@dataclass(frozen=True)
class Mood:
    mood: str
    motivo: str


def validar(dados: dict[str, Any]) -> Mood:
    mood, motivo = dados.get("mood"), dados.get("motivo")
    if mood not in MOODS:
        raise ErroRender(f"trilha: mood '{mood}' fora de {MOODS}")
    if not isinstance(motivo, str) or not motivo.strip():
        raise ErroRender(f"trilha: motivo vazio ou ausente ({motivo!r})")
    return Mood(str(mood), motivo.strip())


def ler_mood(d_corte: Path, texto: str) -> Mood | None:
    """O mood guardado, só se foi do mesmo texto: depois de mover início/fim, o do trecho anterior
    não vale (o editor mostraria um motivo que não é do trecho atual)."""
    arq = d_corte / ARQUIVO
    if not arq.exists():
        return None
    lido = ler_json(arq)
    return validar(lido) if lido.get("chave") == {"texto": texto} else None


def preparar_mood(d_corte: Path, texto: str, chamar: ChamarLLM) -> Mood:
    arq = d_corte / ARQUIVO
    chave = {"texto": texto}
    if arq.exists():
        lido = ler_json(arq)
        if lido.get("chave") == chave:
            return validar(lido)
    try:
        dados = chamar(f"Fala do corte:\n{texto}", SCHEMA, SISTEMA, MODELO)
    except ErroLLM as e:
        raise ErroRender(f"trilha: {e}") from e
    m = validar(dados)
    d_corte.mkdir(parents=True, exist_ok=True)
    salvar_json(arq, {**asdict(m), "chave": chave})
    return m
