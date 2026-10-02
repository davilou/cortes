from datetime import datetime
from pathlib import Path

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


def test_erro_do_llm_pausa_a_fila(tmp_path: Path) -> None:
    episodio(tmp_path)
    f, _ = fila(tmp_path, {"momentos": ErroLLM("CLI reportou erro: limite de uso atingido")})
    f.processar("abcdefghijk")
    assert "limite de uso" in (f.situacao()["pausada"] or "")
    f.retomar()
    assert f.situacao()["pausada"] is None


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


def test_estado_corrompido_nao_trava_a_fila(tmp_path: Path) -> None:
    """Uma falha que escapa de `processar` (estado.json ilegível) não pode matar o laço:
    o episódio corrompido sai da fila e o próximo roda normalmente. Chama `_rodar_um`
    diretamente — é o passo da thread, testável sem thread nenhuma.
    """
    pasta_corrompida = episodio(tmp_path, "corrompid1a")
    (pasta_corrompida / "estado.json").write_text("{isso nao e json", encoding="utf-8")
    episodio(tmp_path, "boaepisodi1a")
    f, feitas = fila(tmp_path)
    f.enfileirar("corrompid1a")
    f.enfileirar("boaepisodi1a")

    f._rodar_um("corrompid1a")  # noqa: SLF001 — testa o passo do laço sem thread

    assert f.situacao()["na_fila"] == ["boaepisodi1a"]

    f._rodar_um("boaepisodi1a")  # noqa: SLF001

    assert feitas == ["video", "legenda", "sinais", "momentos"]
    assert f.situacao()["na_fila"] == []
