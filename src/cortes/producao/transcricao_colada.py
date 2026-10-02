"""Transcrição colada do YouTube ("Mostrar transcrição") → palavras com tempo (spec produção §4.2).

Saída de reserva quando o YouTube bloqueia o download da legenda (HTTP 429). O texto copiado
traz uma linha de tempo (`0:10`, `1:00:03`) seguida do texto do bloco, que pode ocupar várias
linhas. Só o início do bloco tem tempo: as palavras são distribuídas pelo tamanho
(`legenda_yt.distribuir`, a mesma regra da legenda manual) de t_i até
min(t_{i+1}, t_i + nº de palavras × S_POR_PALAVRA × FOLGA_BLOCO) — sem o teto, um bloco
seguido de silêncio ou música espalharia três palavras por minutos. O último bloco não tem
seguinte: dura nº de palavras × S_POR_PALAVRA (fala média ~2,8 palavras/s). O fim de cada
palavra segue `legenda_yt.com_fim`. Precisão por palavra ~±0,3 s.

Leitura do texto:
- linhas antes do primeiro tempo são ignoradas (título do vídeo ou de capítulo copiado junto);
- entre blocos, uma linha sem tempo (ex.: título de capítulo) entra no texto do bloco
  anterior — não há como distingui-la de fala que continua na linha seguinte;
- uma fala que seja exatamente um tempo ("2:30") é lida como tempo (raro; se cair fora de
  ordem, o erro de tempo que não cresce acusa);
- caracteres de largura zero (U+200B/C/D, U+2060, U+FEFF) são removidos antes de tudo.
"""
import re
from dataclasses import dataclass, field

from cortes.producao.legenda_yt import MARCA, ErroLegenda, com_fim, distribuir
from cortes.tipos import Palavra

ARQUIVO = "transcricao.txt"   # em episodios/<id>/, gravado pela API na entrada
S_POR_PALAVRA = 0.35
FOLGA_BLOCO = 1.8   # fala lenta ainda cabe (~1,6 palavra/s); mais que isso é pausa, não fala
MINIMO_PALAVRAS = 50
_TEMPO = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")
_LARGURA_ZERO = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"))


class ErroTranscricao(ErroLegenda):
    """Transcrição colada fora do formato. A mensagem diz a linha."""


@dataclass
class _Bloco:
    inicio: float
    palavras: list[str] = field(default_factory=list)


def _segundos(linha: str, n: int) -> float | None:
    """Segundos de uma linha de tempo; None se a linha não tem forma de tempo."""
    m = _TEMPO.fullmatch(linha)
    if not m:
        return None
    a, b, c = m.groups()
    if c is None:
        h, mi, s = 0, int(a), int(b)
    else:
        h, mi, s = int(a), int(b), int(c)
        if mi >= 60:
            raise ErroTranscricao(f"linha {n}: tempo inválido '{linha}' (minutos ≥ 60)")
    if s >= 60:
        raise ErroTranscricao(f"linha {n}: tempo inválido '{linha}' (segundos ≥ 60)")
    return float(h * 3600 + mi * 60 + s)


def _fmt(t: float) -> str:
    h, resto = divmod(int(t), 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _blocos(texto: str) -> list[_Bloco]:
    blocos: list[_Bloco] = []
    for n, bruta in enumerate(texto.translate(_LARGURA_ZERO).splitlines(), start=1):
        linha = bruta.strip()
        if not linha:
            continue
        t = _segundos(linha, n)
        if t is not None:
            if blocos and t <= blocos[-1].inicio:
                raise ErroTranscricao(f"linha {n}: tempo {linha} não é maior que o anterior "
                                      f"({_fmt(blocos[-1].inicio)})")
            blocos.append(_Bloco(t))
        elif blocos:   # antes do primeiro tempo: título copiado junto, ignorado
            blocos[-1].palavras.extend(MARCA.sub(" ", linha).split())
    return blocos


def _fim_do_bloco(b: _Bloco, seguinte: float | None) -> float:
    fala = len(b.palavras) * S_POR_PALAVRA
    if seguinte is None:
        return b.inicio + fala
    return min(seguinte, b.inicio + fala * FOLGA_BLOCO)


def palavras_da_transcricao(texto: str) -> list[Palavra]:
    blocos = _blocos(texto)
    if not blocos and texto.translate(_LARGURA_ZERO).strip():
        raise ErroTranscricao("transcrição colada sem linhas de tempo (ex.: 0:10) — copie em "
                              "'Mostrar transcrição' com os tempos")
    inicios: list[tuple[str, float]] = []
    for i, b in enumerate(blocos):
        if b.palavras:
            seguinte = blocos[i + 1].inicio if i + 1 < len(blocos) else None
            inicios.extend(distribuir(b.palavras, b.inicio, _fim_do_bloco(b, seguinte)))
    if not inicios:
        raise ErroTranscricao("transcrição colada sem palavras")
    if len(inicios) < MINIMO_PALAVRAS:
        raise ErroTranscricao(f"transcrição curta demais: {len(inicios)} palavras "
                              f"(mínimo {MINIMO_PALAVRAS}); cole a transcrição inteira do episódio")
    return com_fim(inicios)
