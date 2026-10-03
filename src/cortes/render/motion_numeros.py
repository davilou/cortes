"""f3 Motion, a regra dos números (plano 2026-10-03-motion; spec produção §7): na tela, só número
que foi dito na fala. Puro.

O mesmo leitor serve aos dois lados: às palavras da fala e ao texto que o painel mostra. Entende
algarismo ("400", "1.500", "37,5%", "R$7.500"), número por extenso ("mil e duzentos", "trinta e
sete") e os multiplicadores ("mil", "milhões" e a gíria "pau": "3 pau e meio" = 3.500).

Cada número guarda o valor cheio e a `base`, o que vem antes do multiplicador final ("550 mil" →
550). Um número da tela com multiplicador vale também quando a fala disse só a base: "tava valendo
550" sustenta "R$ 550 mil" (os algarismos são os ditos). Zero sempre passa: é o começo de uma
contagem ("ANO 0"), não uma afirmação.
"""
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

_UNIDADES = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
    "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14,
    "quatorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19,
    "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70,
    "oitenta": 80, "noventa": 90, "cem": 100, "cento": 100, "duzentos": 200, "duzentas": 200,
    "trezentos": 300, "trezentas": 300, "quatrocentos": 400, "quatrocentas": 400, "quinhentos": 500,
    "quinhentas": 500, "seiscentos": 600, "seiscentas": 600, "setecentos": 700, "setecentas": 700,
    "oitocentos": 800, "oitocentas": 800, "novecentos": 900, "novecentas": 900,
}
_MULTIPLICADORES = {"mil": 1e3, "milhao": 1e6, "milhoes": 1e6, "bilhao": 1e9, "bilhoes": 1e9}
_GIRIA = {"pau": 1e3, "paus": 1e3}   # só depois de um número: "nem a pau" não é mil
_MEIO = ("meio", "meia")
_ARTIGOS = ("um", "uma")   # "um apê" não é o número 1; "um milhão" é (o texto inteiro não é só "um")
_MILHAR = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?")
_DECIMAL = re.compile(r"\d+(?:,\d+)?")
_PONTO = re.compile(r"\d+\.\d{1,2}")
_BORDA = re.compile(r"^[^\w]+|[^\w%]+$")
_PAUSA = re.compile(r"[.,;:!?…]$")
TOLERANCIA = 1e-6


@dataclass(frozen=True)
class Numero:
    valor: float   # cheio: "400 mil" → 400000
    base: float    # antes do multiplicador final: "400 mil" → 400; sem multiplicador, o próprio valor
    texto: str     # como apareceu, para o motivo da recusa


def _normal(token: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", token).encode("ascii", "ignore").decode()
    return _BORDA.sub("", sem_acento.lower().replace("r$", ""))


def _algarismo(t: str) -> float | None:
    t = t.removesuffix("%")
    if _MILHAR.fullmatch(t):
        return float(t.replace(".", "").replace(",", "."))
    if _DECIMAL.fullmatch(t):
        return float(t.replace(",", "."))
    if _PONTO.fullmatch(t):
        return float(t)
    return None


def _casa(x: float) -> float:
    """A menor casa ocupada de um inteiro: 30 → 10, 300000 → 100000, 7 → 1. Fração → 0 (não junta)."""
    if x != int(x) or x == 0:
        return 0.0
    casa, n = 1.0, int(x)
    while n % 10 == 0:
        casa, n = casa * 10, n // 10
    return casa


@dataclass
class _Frase:
    """Um número sendo lido: total já fechado por multiplicador, parte corrente e as marcas."""
    total: float = 0.0
    atual: float = 0.0
    ultimo: float = 0.0          # a última parte somada (decide se "e X" ainda é deste número)
    mult_final: float = 1.0      # multiplicador que fechou o número, se nada veio depois dele
    algarismo: bool = False      # a última parte foi algarismo: "3 e 4" são dois números
    tokens: int = 0
    texto: str = ""

    def valor(self) -> float:
        return self.total + self.atual

    def numero(self) -> Numero:
        v = self.valor()
        return Numero(v, v / self.mult_final, self.texto.strip())

    def soma(self, v: float, original: str, algarismo: bool) -> None:
        self.atual += v
        self.ultimo, self.mult_final, self.algarismo = v, 1.0, algarismo
        self.tokens, self.texto = self.tokens + 1, f"{self.texto} {original}"

    def multiplica(self, m: float, original: str) -> None:
        parte = (self.atual or 1.0) * m
        self.total, self.atual = self.total + parte, 0.0
        self.ultimo, self.mult_final, self.algarismo = parte, m, False
        self.tokens, self.texto = self.tokens + 1, f"{self.texto} {original}"

    def aceita(self, v: float) -> bool:
        """Uma parte nova (depois de "e" ou de multiplicador) ainda é deste número."""
        return self.tokens > 0 and not self.algarismo and v < _casa(self.ultimo)


def _valor_simples(t: str) -> tuple[float, bool] | None:
    """(valor, é algarismo) de um token que é número sozinho; None se não é."""
    a = _algarismo(t)
    if a is not None:
        return a, True
    if t in _UNIDADES:
        return float(_UNIDADES[t]), False
    return None


def _passo(f: _Frase, tokens: list[tuple[str, str]], i: int) -> tuple[_Frase, int, Numero | None]:
    """Lê o token i dentro da frase `f`: devolve a frase que segue, quantos tokens consumiu e o
    número que fechou (se fechou um)."""
    t, original = tokens[i]
    prox = tokens[i + 1] if i + 1 < len(tokens) else ("", "")
    simples = _valor_simples(t)
    if t in _MULTIPLICADORES or (t in _GIRIA and f.tokens):
        f.multiplica(_MULTIPLICADORES.get(t) or _GIRIA[t], original)
        return f, 1, None
    if t == "e" and f.tokens and prox[0] in _MEIO:
        f.atual += 0.5 * f.mult_final if f.atual == 0 else 0.5
        f.ultimo, f.texto = 0.0, f"{f.texto} e {prox[1]}"
        return f, 2, None
    pv = _valor_simples(prox[0]) if t == "e" else None
    if pv is not None and f.aceita(pv[0]):
        f.soma(pv[0], prox[1], pv[1])
        return f, 2, None
    if simples is not None and f.tokens and f.mult_final > 1 and f.aceita(simples[0]):
        f.soma(simples[0], original, simples[1])   # "mil duzentos", sem o "e"
        return f, 1, None
    fechado = f.numero() if f.tokens else None
    novo = _Frase()
    if simples is not None:
        novo.soma(simples[0], original, simples[1])
    return novo, 1, fechado


def _ler(tokens: list[tuple[str, str]]) -> list[Numero]:
    """Pontuação fecha o número: "mil e duzentos, mil e quinhentos" são dois."""
    res: list[Numero] = []
    f, i = _Frase(), 0
    while i < len(tokens):
        f, usados, fechado = _passo(f, tokens, i)
        if fechado is not None:
            res.append(fechado)
        i += usados
        if f.tokens and _PAUSA.search(tokens[i - 1][1]):
            res.append(f.numero())
            f = _Frase()
    if f.tokens:
        res.append(f.numero())
    return [n for n in res if _normal(n.texto) not in _ARTIGOS]


def numeros(texto: str) -> list[Numero]:
    """Os números de um texto, na ordem."""
    tokens = [(t, o) for o in texto.replace("-", " ").split() if (t := _normal(o))]
    # "por cento" é o %, não o cento de "cento e vinte"
    tokens = [("%", o) if t == "cento" and k and tokens[k - 1][0] == "por" else (t, o)
              for k, (t, o) in enumerate(tokens)]
    return _ler(tokens)


def numeros_da_fala(palavras: Sequence[str]) -> list[Numero]:
    return numeros(" ".join(palavras))


def _igual(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCIA * max(1.0, abs(a), abs(b))


def foi_dito(n: Numero, falados: Sequence[Numero]) -> bool:
    if _igual(n.valor, 0.0):
        return True
    tem_mult = not _igual(n.base, n.valor)
    return any(_igual(n.valor, f.valor) or (tem_mult and _igual(n.base, f.valor)) for f in falados)


def nao_ditos(textos: Sequence[str], falados: Sequence[Numero]) -> list[str]:
    """Os números dos textos da tela que a fala não sustenta (vazio = tudo dito)."""
    return [n.texto for t in textos for n in numeros(t) if not foi_dito(n, falados)]
