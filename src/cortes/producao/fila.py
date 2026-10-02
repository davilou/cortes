"""Fila única da produção: uma thread, um episódio e uma etapa por vez (spec produção §4.4).

GPU, cota do Claude e CPU do render são recursos únicos — por isso nada roda em paralelo.
Erro numa etapa fica no estado.json do episódio e a fila segue com o próximo; erro do LLM
(ex.: limite de uso da assinatura) PAUSA a fila até Davi retomar. Uma falha que escape de
`processar` (ex.: estado.json corrompido) não pode matar a thread: `_rodar_um` captura,
imprime o traceback no terminal e tira o episódio da fila mesmo assim.
"""
import threading
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from cortes.llm import ErroLLM
from cortes.producao.estado import (
    EstadoEpisodio,
    concluido,
    etapa_com_erro,
    gravar,
    ler,
    marcar,
    proxima,
    reabrir,
)

RodarEtapa = Callable[[str, Path, EstadoEpisodio], None]


class Fila:
    def __init__(self, raiz: Path, rodar: RodarEtapa, agora: Callable[[], datetime] = datetime.now) -> None:
        self._raiz = raiz
        self._rodar = rodar
        self._agora = agora
        self._trava = threading.Lock()
        self._tem_trabalho = threading.Condition(self._trava)
        self._ids: list[str] = []
        self._atual: dict[str, str] | None = None
        self._pausada: str | None = None
        self._fio: threading.Thread | None = None

    def _pasta(self, id: str) -> Path:
        return self._raiz / "episodios" / id

    def enfileirar(self, id: str) -> None:
        with self._tem_trabalho:
            if id not in self._ids:
                self._ids.append(id)
            self._tem_trabalho.notify()

    def retomar(self) -> None:
        with self._tem_trabalho:
            self._pausada = None
            self._tem_trabalho.notify()

    def situacao(self) -> dict[str, Any]:
        """Cópia do estado interno — nada aqui pode ser mutado pelo chamador."""
        with self._trava:
            atual = dict(self._atual) if self._atual is not None else None
            return {"atual": atual, "na_fila": list(self._ids), "pausada": self._pausada}

    def recuperar(self) -> None:
        """Na subida: o que ficou 'rodando' volta a pendente e entra na fila."""
        for arquivo in sorted(self._raiz.glob("episodios/*/estado.json")):
            e = ler(arquivo.parent)
            if concluido(e) or etapa_com_erro(e):
                continue
            gravar(arquivo.parent, reabrir(e))
            self.enfileirar(e.id)

    def processar(self, id: str) -> None:
        """Roda as etapas pendentes de um episódio até acabar ou falhar. Síncrono (testável).

        Erro de `ler`/`gravar` (ex.: estado.json corrompido → `ErroProducao`) escapa daqui de
        propósito: quem chama de dentro da thread (`_rodar_um`) é que garante que isso não a mate.
        """
        pasta = self._pasta(id)
        while (etapa := proxima(e := ler(pasta))) is not None:
            with self._trava:
                self._atual = {"episodio": id, "etapa": etapa}
            gravar(pasta, marcar(e, etapa, "rodando", self._agora()))
            if not self._rodar_etapa(pasta, etapa, e):
                break
        with self._trava:
            self._atual = None

    def _rodar_etapa(self, pasta: Path, etapa: str, e: EstadoEpisodio) -> bool:
        """Roda uma etapa; devolve False se o episódio deve parar (erro ou pausa do LLM)."""
        try:
            self._rodar(etapa, pasta, e)
        except ErroLLM as ex:
            gravar(pasta, marcar(ler(pasta), etapa, "erro", self._agora(), str(ex)))
            with self._trava:
                self._pausada = f"fila pausada: {ex}"
            return False
        except Exception as ex:   # qualquer falha da etapa fica visível no episódio, a fila segue
            traceback.print_exc()
            gravar(pasta, marcar(ler(pasta), etapa, "erro", self._agora(), f"{type(ex).__name__}: {ex}"))
            return False
        gravar(pasta, marcar(ler(pasta), etapa, "ok", self._agora()))
        return True

    def _proximo(self) -> str:
        """Bloqueia até haver um episódio na fila e ela não estar pausada."""
        with self._tem_trabalho:
            while not self._ids or self._pausada:
                self._tem_trabalho.wait()
            return self._ids[0]

    def _rodar_um(self, id: str) -> None:
        """Processa um episódio sem deixar nenhuma falha (nem fora de `processar`) matar a fila."""
        try:
            self.processar(id)
        except Exception:   # ex.: estado.json corrompido — a fila segue para o próximo episódio
            traceback.print_exc()
        finally:
            with self._trava:
                if id in self._ids:
                    self._ids.remove(id)

    def _laco(self) -> None:
        while True:
            id = self._proximo()
            self._rodar_um(id)

    def iniciar(self) -> None:
        self.recuperar()
        self._fio = threading.Thread(target=self._laco, daemon=True, name="fila-producao")
        self._fio.start()
