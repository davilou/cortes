"""Prévia do editor (plano C): monta o projeto HyperFrames de um corte FORA da fila do render.

Recortar o trecho e medir o rosto leva 10–30 s quando início/fim mudam; esperar atrás de 5 renders
(10–20 min) mataria o editor (Davi, 2026-10-02). Uma thread só para prévias, um corte por vez; o
último pedido de cada corte vale (pedidos repetidos enquanto ele espera não se acumulam).
A situação fica em memória; depois de reiniciar o painel, quem decide é o disco (rotas_editor).
"""
import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cortes.render.corte import Corte, ler_corte, pasta_corte

Montar = Callable[[Path, Corte], None]


@dataclass(frozen=True)
class SituacaoPrevia:
    situacao: Literal["preparando", "pronta", "erro"]
    erro: str | None = None


class Previas:
    def __init__(self, raiz: Path, montar: Montar) -> None:
        self._raiz = raiz
        self._montar = montar
        self._trava = threading.Lock()
        self._tem_pedido = threading.Condition(self._trava)
        self._pedidos: list[tuple[str, int]] = []
        self._situacao: dict[tuple[str, int], SituacaoPrevia] = {}
        self._fio: threading.Thread | None = None

    def pedir(self, id: str, n: int) -> None:
        with self._tem_pedido:
            self._situacao[(id, n)] = SituacaoPrevia("preparando")
            if (id, n) not in self._pedidos:
                self._pedidos.append((id, n))
            self._tem_pedido.notify()

    def situacao(self, id: str, n: int) -> SituacaoPrevia | None:
        with self._trava:
            return self._situacao.get((id, n))

    def preparando(self, id: str, n: int) -> bool:
        s = self.situacao(id, n)
        return s is not None and s.situacao == "preparando"

    def processar(self, id: str, n: int) -> None:
        """Síncrono (testável). Tira este pedido da fila antes de montar — como `_proximo` faria
        na thread real — para que um pedido novo que chegue DURANTE o preparo (via `pedir`)
        apareça de volta na fila e mantenha 'preparando': o resultado deste preparo seria de um
        estado antigo.

        A montagem lê o `corte.json` do disco NO MOMENTO em que roda (via `ler_corte`), não no
        momento do `pedir`. Por isso quem pede uma prévia por causa de uma mudança no corte
        (início/fim, legenda, rosto…) precisa GRAVAR o `corte.json` novo ANTES de chamar `pedir` —
        chamar na ordem inversa faz a prévia montar com o corte antigo."""
        with self._trava:
            if (id, n) in self._pedidos:
                self._pedidos.remove((id, n))
        pasta = self._raiz / "episodios" / id
        try:
            self._montar(pasta, ler_corte(pasta_corte(pasta, n)))
            fim = SituacaoPrevia("pronta")
        except Exception as ex:   # qualquer falha fica visível no editor; a thread segue
            traceback.print_exc()
            fim = SituacaoPrevia("erro", f"{type(ex).__name__}: {ex}")
        with self._trava:
            if (id, n) not in self._pedidos:
                self._situacao[(id, n)] = fim

    def _proximo(self) -> tuple[str, int]:
        with self._tem_pedido:
            while not self._pedidos:
                self._tem_pedido.wait()
            return self._pedidos.pop(0)

    def _laco(self) -> None:
        while True:
            self.processar(*self._proximo())

    def iniciar(self) -> None:
        with self._trava:
            if self._fio is not None:
                raise RuntimeError("prévias já iniciadas")
            self._fio = threading.Thread(target=self._laco, daemon=True, name="previas")
        self._fio.start()
