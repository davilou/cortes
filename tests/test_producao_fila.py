import threading
from datetime import datetime
from pathlib import Path

import pytest

from cortes.llm import ErroLLM
from cortes.producao.estado import EstadoEpisodio, gravar, ler, marcar, novo
from cortes.producao.fila import Fila

AGORA = datetime(2026, 10, 2, 9)


def episodio(raiz: Path, id: str = "abcdefghijk") -> Path:
    pasta = raiz / "episodios" / id
    pasta.mkdir(parents=True)
    gravar(pasta, novo(id, f"https://youtu.be/{id}", "financas", 5, "f7", AGORA))
    return pasta


def fila(raiz: Path, falha: dict[str, Exception] | None = None) -> tuple[Fila, list[str]]:
    feitas: list[str] = []

    def rodar(nome: str, pasta: Path, e: EstadoEpisodio) -> None:
        if falha and nome in falha:
            raise falha[nome]
        feitas.append(nome)

    return Fila(raiz, rodar, lambda: AGORA), feitas


def test_processa_todas_as_etapas(tmp_path: Path) -> None:
    pasta = episodio(tmp_path)
    f, feitas = fila(tmp_path)
    f.processar("abcdefghijk")
    assert feitas == ["video", "legenda", "sinais", "momentos"]
    assert all(et.situacao == "ok" for et in ler(pasta).etapas.values())


def test_erro_grava_causa_e_para_o_episodio(tmp_path: Path) -> None:
    pasta = episodio(tmp_path)
    f, feitas = fila(tmp_path, {"legenda": RuntimeError("vídeo sem legenda em português no YouTube")})
    f.processar("abcdefghijk")
    e = ler(pasta)
    assert feitas == ["video"] and e.etapas["legenda"].situacao == "erro"
    assert "sem legenda" in (e.etapas["legenda"].erro or "") and f.situacao()["pausada"] is None


def test_erro_do_llm_pausa_a_fila_e_grava_a_causa_na_etapa(tmp_path: Path) -> None:
    pasta = episodio(tmp_path)
    f, _ = fila(tmp_path, {"momentos": ErroLLM("CLI reportou erro: limite de uso atingido")})
    f.processar("abcdefghijk")

    e = ler(pasta)
    assert e.etapas["momentos"].situacao == "erro"
    assert "limite de uso" in (e.etapas["momentos"].erro or "")
    assert "limite de uso" in (f.situacao()["pausada"] or "")

    f.retomar()
    assert f.situacao()["pausada"] is None


def test_retomar_reabre_e_reprocessa_so_a_etapa_que_falhou(tmp_path: Path) -> None:
    """'Tentar de novo' depois de uma pausa do LLM: a etapa que falhou volta a rodar,
    as que já estavam 'ok' não rodam de novo.
    """
    pasta = episodio(tmp_path)
    chamadas: list[Exception | None] = [ErroLLM("CLI reportou erro: limite de uso atingido"), None]

    def rodar(nome: str, p: Path, e: EstadoEpisodio) -> None:
        if nome == "momentos" and chamadas:
            erro = chamadas.pop(0)
            if erro is not None:
                raise erro

    f = Fila(tmp_path, rodar, lambda: AGORA)
    f.processar("abcdefghijk")
    assert f.situacao()["pausada"] is not None

    f.retomar()
    assert f.situacao()["na_fila"] == ["abcdefghijk"]

    f.processar("abcdefghijk")
    e = ler(pasta)
    assert all(et.situacao == "ok" for et in e.etapas.values())
    assert chamadas == []  # "momentos" rodou de novo; video/legenda/sinais não rodam (já "ok")


def test_recupera_o_que_estava_rodando(tmp_path: Path) -> None:
    pasta = episodio(tmp_path)
    gravar(pasta, marcar(ler(pasta), "video", "rodando", AGORA))
    concluido = episodio(tmp_path, "zzzzzzzzzzz")
    e = ler(concluido)
    for n in e.etapas:
        e = marcar(e, n, "ok", AGORA)
    gravar(concluido, e)
    f, _ = fila(tmp_path)
    f.recuperar()
    assert f.situacao()["na_fila"] == ["abcdefghijk"]
    assert ler(pasta).etapas["video"].situacao == "pendente"


def test_enfileirar_nao_duplica(tmp_path: Path) -> None:
    episodio(tmp_path)
    f, _ = fila(tmp_path)
    f.enfileirar("abcdefghijk")
    f.enfileirar("abcdefghijk")
    assert f.situacao()["na_fila"] == ["abcdefghijk"]


def test_proximo_retira_da_fila_enquanto_roda(tmp_path: Path) -> None:
    episodio(tmp_path)
    f, _ = fila(tmp_path)
    f.enfileirar("abcdefghijk")
    id = f._proximo()  # noqa: SLF001 — testa o passo do laço sem thread
    assert id == "abcdefghijk"
    assert f.situacao()["na_fila"] == []


def test_reenfileirar_durante_a_execucao_nao_se_perde(tmp_path: Path) -> None:
    """Regressão: `_proximo` só espiava `_ids[0]`, então o id ficava listado enquanto
    rodava e um `enfileirar` de "tentar de novo" feito durante essa janela era deduplicado
    e perdido. Agora `_proximo` retira o id, e o `rodar` abaixo se reenfileira a si mesmo
    para simular esse clique durante a execução.
    """
    episodio(tmp_path)
    f_ref: list[Fila] = []

    def rodar(nome: str, p: Path, e: EstadoEpisodio) -> None:
        if nome == "video":
            f_ref[0].enfileirar("abcdefghijk")

    f = Fila(tmp_path, rodar, lambda: AGORA)
    f_ref.append(f)
    f.enfileirar("abcdefghijk")

    id = f._proximo()  # noqa: SLF001
    f._rodar_um(id)  # noqa: SLF001

    assert f.situacao()["na_fila"] == ["abcdefghijk"]


def test_estado_corrompido_nao_trava_a_fila_e_fica_visivel(tmp_path: Path) -> None:
    """Uma falha que escapa de `processar` (estado.json ilegível) não pode matar o laço:
    o episódio corrompido sai da fila, fica registrado em `situacao()["falhas"]`, e o
    próximo roda normalmente. Chama `_rodar_um` direto — é o passo da thread, testável
    sem thread nenhuma.
    """
    pasta_corrompida = episodio(tmp_path, "corrompid1a")
    (pasta_corrompida / "estado.json").write_text("{isso nao e json", encoding="utf-8")
    episodio(tmp_path, "boaepisodi1a")
    f, feitas = fila(tmp_path)
    f.enfileirar("corrompid1a")
    f.enfileirar("boaepisodi1a")

    f._rodar_um(f._proximo())  # noqa: SLF001 — testa o passo do laço sem thread

    assert f.situacao()["na_fila"] == ["boaepisodi1a"]
    assert "corrompid1a" in f.situacao()["falhas"]

    f._rodar_um(f._proximo())  # noqa: SLF001

    assert feitas == ["video", "legenda", "sinais", "momentos"]
    assert f.situacao()["na_fila"] == []


def test_iniciar_duas_vezes_falha(tmp_path: Path) -> None:
    episodio(tmp_path)
    f, _ = fila(tmp_path)
    f.iniciar()
    with pytest.raises(RuntimeError, match="já iniciada"):
        f.iniciar()


def test_thread_real_pausa_no_erro_llm_e_nao_roda_o_proximo_ate_retomar(tmp_path: Path) -> None:
    episodio(tmp_path, "primeiroep1")
    episodio(tmp_path, "segundoepi1")
    pausou = threading.Event()
    terminou_segundo = threading.Event()
    trava = threading.Lock()
    rodadas: list[str] = []

    def rodar(nome: str, p: Path, e: EstadoEpisodio) -> None:
        with trava:
            rodadas.append(f"{e.id}:{nome}")
            vezes = rodadas.count(f"{e.id}:{nome}")
        if e.id == "primeiroep1" and nome == "momentos" and vezes == 1:
            pausou.set()
            raise ErroLLM("CLI reportou erro: limite de uso atingido")
        if e.id == "segundoepi1" and nome == "momentos":
            terminou_segundo.set()

    f = Fila(tmp_path, rodar, lambda: AGORA)
    f.enfileirar("primeiroep1")
    f.enfileirar("segundoepi1")
    f.iniciar()

    assert pausou.wait(timeout=5)
    assert not terminou_segundo.wait(timeout=0.3)
    assert f.situacao()["pausada"] is not None

    f.retomar()

    assert terminou_segundo.wait(timeout=5)
    with trava:
        assert rodadas.count("primeiroep1:momentos") == 2
        assert "segundoepi1:video" in rodadas
