"""Fila única da produção: uma thread, um episódio e uma etapa por vez (spec produção §4.4).

GPU, cota do Claude e CPU do render são recursos únicos — por isso nada roda em paralelo.
Erro numa etapa fica no estado.json do episódio e a fila segue com o próximo; erro do LLM
(ex.: limite de uso da assinatura) PAUSA a fila até Davi retomar — e Davi não perde o
episódio pausado: `retomar` reabre a etapa e devolve o episódio para a frente da fila.
Uma falha que escape de `processar` (ex.: estado.json corrompido) não pode matar a thread:
`_rodar_um` captura, imprime o traceback no terminal e tenta deixar a causa visível.

`antes(pasta)` roda na thread da fila antes de cada episódio e na subida — é o que reabre a
etapa render quando um Renderizar chega depois de ela fechar.
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
Antes = Callable[[Path], None]   # roda na thread da fila antes de processar (e na subida)


def _nada(pasta: Path) -> None:
    return None


class Fila:
    def __init__(self, raiz: Path, rodar: RodarEtapa, agora: Callable[[], datetime] = datetime.now,
                 antes: Antes = _nada) -> None:
        self._raiz = raiz
        self._rodar = rodar
        self._agora = agora
        self._antes = antes
        self._trava = threading.Lock()
        self._tem_trabalho = threading.Condition(self._trava)
        self._ids: list[str] = []
        self._atual: dict[str, str] | None = None
        self._pausada: str | None = None
        self._pausado_id: str | None = None
        self._falhas: dict[str, str] = {}
        self._fio: threading.Thread | None = None

    def _pasta(self, id: str) -> Path:
        return self._raiz / "episodios" / id

    def enfileirar(self, id: str) -> None:
        """Põe no fim da fila quem está esperando. Um episódio que já está rodando (e
        portanto não está mais em `_ids` — `_proximo` o retirou) pode ser enfileirado de
        novo sem perda: o "tentar de novo" clicado durante a execução não desaparece,
        só faz outra passada por `processar` depois (idempotente: pula o que já é "ok").
        Reenfileirar limpa uma falha antiga registrada em `situacao()["falhas"]` — é
        exatamente isso que "tentar de novo" quer dizer.
        """
        with self._tem_trabalho:
            if id not in self._ids:
                self._ids.append(id)
            self._falhas.pop(id, None)
            self._tem_trabalho.notify()

    def retomar(self) -> None:
        """Davi manda a fila seguir. Se a pausa foi por `ErroLLM`, o episódio parado não é
        esquecido: a etapa volta a pendente e ele entra na frente da fila, não no fim — e
        a leitura/gravação do estado roda FORA da trava (I/O não pode bloquear quem só
        quer `situacao()`). Se o episódio não puder ser reaberto, a pausa é restaurada e o
        erro sobe: melhor continuar pausado e visível do que a fila seguir sem ele.
        """
        with self._tem_trabalho:
            id, pausada_anterior = self._pausado_id, self._pausada
            self._pausado_id = None
            self._pausada = None
            if id is None:
                self._tem_trabalho.notify()
                return

        try:
            self._reabrir_e_priorizar(id)
        except Exception:
            with self._tem_trabalho:
                self._pausado_id = id
                self._pausada = pausada_anterior
            raise

        with self._tem_trabalho:
            self._tem_trabalho.notify()

    def _reabrir_e_priorizar(self, id: str) -> None:
        pasta = self._pasta(id)
        gravar(pasta, reabrir(ler(pasta)))   # I/O fora da trava
        with self._trava:
            if id in self._ids:
                self._ids.remove(id)
            self._ids.insert(0, id)

    def situacao(self) -> dict[str, Any]:
        """Cópia do estado interno — nada aqui pode ser mutado pelo chamador."""
        with self._trava:
            atual = dict(self._atual) if self._atual is not None else None
            return {
                "atual": atual,
                "na_fila": list(self._ids),
                "pausada": self._pausada,
                "falhas": dict(self._falhas),
            }

    def recuperar(self) -> None:
        """Na subida: o que ficou 'rodando' volta a pendente e entra na fila. Chamar só
        na inicialização do processo — `iniciar` já faz isso uma vez.
        """
        for arquivo in sorted(self._raiz.glob("episodios/*/estado.json")):
            self._antes(arquivo.parent)
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
        self._antes(pasta)
        try:
            while (etapa := proxima(e := ler(pasta))) is not None:
                with self._trava:
                    self._atual = {"episodio": id, "etapa": etapa}
                gravar(pasta, marcar(e, etapa, "rodando", self._agora()))
                if not self._rodar_etapa(pasta, id, etapa, e):
                    break
        finally:
            with self._trava:
                self._atual = None

    def _rodar_etapa(self, pasta: Path, id: str, etapa: str, e: EstadoEpisodio) -> bool:
        """Roda uma etapa; devolve False se o episódio deve parar (erro ou pausa do LLM)."""
        try:
            self._rodar(etapa, pasta, e)
        except ErroLLM as ex:
            try:
                gravar(pasta, marcar(ler(pasta), etapa, "erro", self._agora(), str(ex)))
            finally:   # a pausa fica registrada mesmo se o gravar falhar
                with self._trava:
                    self._pausada = f"fila pausada: {ex}"
                    self._pausado_id = id
            return False
        except Exception as ex:   # qualquer falha da etapa fica visível no episódio, a fila segue
            traceback.print_exc()
            gravar(pasta, marcar(ler(pasta), etapa, "erro", self._agora(), f"{type(ex).__name__}: {ex}"))
            return False
        gravar(pasta, marcar(ler(pasta), etapa, "ok", self._agora()))
        return True

    def _proximo(self) -> str:
        """Bloqueia até haver um episódio na fila e ela não estar pausada, e o retira —
        enquanto roda, ele não aparece mais em `_ids`/`situacao()["na_fila"]`, mas um
        `enfileirar` para o mesmo id durante a execução não se perde (volta para o fim).
        """
        with self._tem_trabalho:
            while not self._ids or self._pausada:
                self._tem_trabalho.wait()
            return self._ids.pop(0)

    def _rodar_um(self, id: str) -> None:
        """Processa um episódio sem deixar nenhuma falha (nem fora de `processar`) matar a fila."""
        try:
            self.processar(id)
        except Exception as ex:   # ex.: estado.json corrompido — a fila segue para o próximo
            traceback.print_exc()
            self._registrar_falha_inesperada(id, ex)

    def _registrar_falha_inesperada(self, id: str, ex: Exception) -> None:
        """Best-effort: tenta deixar a causa visível na etapa que ficou 'rodando'; se nem
        isso der (ex.: o próprio estado.json é ilegível), guarda em memória — `situacao()`
        não pode esconder que um episódio falhou de um jeito que não é erro de etapa normal.
        """
        msg = f"{type(ex).__name__}: {ex}"
        pasta = self._pasta(id)
        try:
            e = ler(pasta)
            etapa = proxima(e)   # a que ficou "rodando" quando a exceção escapou
            if etapa is not None:
                gravar(pasta, marcar(e, etapa, "erro", self._agora(), msg))
                return
        except Exception:   # sem catch vazio: o traceback vai pro terminal antes do fallback
            traceback.print_exc()
        with self._trava:
            self._falhas[id] = msg

    def _laco(self) -> None:
        while True:
            id = self._proximo()
            self._rodar_um(id)

    def iniciar(self) -> None:
        """Chamar uma única vez, na subida do processo. `recuperar` varre o disco pelo
        que ficou 'rodando' numa queda — rodar de novo depois reabriria episódios que
        já estão em andamento.
        """
        with self._trava:
            if self._fio is not None:
                raise RuntimeError("fila já iniciada")
            self._fio = threading.Thread(target=self._laco, daemon=True, name="fila-producao")
        self.recuperar()
        self._fio.start()
