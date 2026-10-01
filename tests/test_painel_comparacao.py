from datetime import date

import pytest

from cortes.painel.comparacao import Celula, Confusao, confusoes, dimensao, grupos, matriz
from cortes.painel.dados import ErroPainel
from cortes.painel.metodo import Estado, Linha, Medida
from cortes.painel.publicados import Etiquetas


def linha(vid: str, conta: str, formato: str | None, rel: float | None, temas: tuple[str, ...] = (),
          views: int = 1000, inscritos: int = 1, estado: Estado = "medido") -> Linha:
    etq = Etiquetas(formato, temas, "PrimoCast") if formato else None
    return Linha(vid, conta, f"T {vid}", date(2026, 10, 1), etq, "testes/x" if etq else None,
                 Medida(estado, float(views)), rel, views, 80.0, inscritos)


LINHAS = [
    linha("a", "grana", "f7", 3.0, ("humor", "famoso")), linha("b", "grana", "f7", 1.0),
    linha("c", "riso", "f7", 2.0, ("humor",)), linha("d", "grana", "f4", 0.5),
    linha("e", "grana", None, 9.0),          # sem ligação: fora
    linha("f", "riso", "f4", None),          # sem rel: fora
]


def test_grupos_por_formato() -> None:
    f7, f4 = grupos(LINHAS, "formato")
    assert (f7.chave, f7.n, f7.rel_mediana, f7.pista) == ("f7", 3, 2.0, True)
    assert f7.rels == (1.0, 2.0, 3.0) and set(f7.video_ids) == {"a", "b", "c"}
    assert (f4.chave, f4.n) == ("f4", 1)


def test_inscritos_por_mil_views() -> None:
    (g,) = grupos([linha("a", "grana", "f7", 1.0, views=2000, inscritos=3)], "formato")
    assert g.insc_por_mil == pytest.approx(1.5)


def test_tema_multivalor_entra_em_todos_os_grupos() -> None:
    gs = {g.chave: g for g in grupos(LINHAS, "tema")}
    assert gs["humor"].n == 2 and gs["famoso"].n == 1


def test_pista_some_com_n_5() -> None:
    ls = [linha(str(i), "grana", "f7", 1.0) for i in range(5)]
    assert not grupos(ls, "formato")[0].pista


def test_insc_por_mil_none_sem_views() -> None:
    (g,) = grupos([linha("a", "grana", "f7", 1.0, views=0, inscritos=0)], "formato")
    assert g.insc_por_mil is None


def test_grupos_por_podcast_e_conta() -> None:
    assert {g.chave for g in grupos(LINHAS, "podcast")} == {"PrimoCast"}
    gs = {g.chave: g for g in grupos(LINHAS, "conta")}
    assert gs["grana"].n == 3 and gs["riso"].n == 1


def test_grupos_ordem_deterministica_em_mediana_igual() -> None:
    ls = [linha("a", "grana", "fy", 1.0), linha("b", "grana", "fx", 1.0)]
    assert [g.chave for g in grupos(ls, "formato")] == ["fx", "fy"]


def test_matriz() -> None:
    cel = {(c.formato, c.conta): c for c in matriz(LINHAS)}
    assert cel[("f7", "grana")] == Celula("f7", "grana", 2, 2.0)
    assert ("f4", "riso") not in cel


def test_confusoes() -> None:
    # f4 só tem Short medido em grana; riso só tem f7 medido (o 'f' não tem relativo)
    assert confusoes(LINHAS) == [Confusao("formato", "f4", "grana"), Confusao("conta", "riso", "f7")]


def test_dimensao_invalida() -> None:
    assert dimensao("tema") == "tema"
    with pytest.raises(ErroPainel, match="dimensão 'cor'"):
        dimensao("cor")


def test_grupo_marca_estimados_alinhados_aos_rels() -> None:
    ls = [linha("a", "grana", "f7", 3.0, estado="estimado"), linha("b", "grana", "f7", 1.0),
          linha("c", "grana", "f7", 2.0, estado="estimado")]
    (g,) = grupos(ls, "formato")
    assert g.rels == (1.0, 2.0, 3.0) and g.estimados == (False, True, True) and g.n_estimados == 2
