"""Editor do f3: as cenas (só leitura), o tema e "Refazer motion"."""
import json
from dataclasses import replace

from cortes.painel.servidor import Config
from cortes.render.corte import gravar_corte, ler_corte
from cortes.render.ilustracao_cache import Chave
from cortes.render.motion import Cena, Resultado
from cortes.render.motion_cache import gravar_cenas
from cortes.render.motion_params import Contador, Ilustracao
from cortes.render.motion_ritmo import Descartada
from tests.test_producao_rotas_editor import EP, Ambiente


def ambiente_f3(cfg: Config) -> Ambiente:
    a = Ambiente(cfg)
    gravar_corte(a.d, replace(ler_corte(a.d), formato="f3"))
    cena = Cena(1, "contador", 2.0, 4.5, Contador("GANHEI", 10, "R$", "mil"), ())
    fora = Descartada("valor", 5.0, 7.0, {"rotulo": "x", "valor": 99},
                      "número que a fala não disse: 99")
    gravar_cenas(a.d, Chave(0.7, 7.8, "h"), Resultado([cena], [fora], "dados"))
    return a


def test_editor_lista_as_cenas_e_as_descartadas_do_f3(cfg: Config) -> None:
    d = ambiente_f3(cfg).c.get(f"{EP}/cortes/0/editor").json()
    (cena,) = d["motion"]["cenas"]
    assert (cena["k"], cena["componente"], cena["inicio"], cena["fim"]) == (1, "contador", 2.0, 4.5)
    assert cena["params"] == {"rotulo": "GANHEI", "valor": 10.0, "prefixo": "R$", "sufixo": "mil",
                              "marcos": None}
    assert d["motion"]["descartadas"][0]["motivo"] == "número que a fala não disse: 99"
    assert d["motion_erro"] is None and "f3" in d["formatos"]


def test_editor_sem_motion_fora_do_f3(cfg: Config) -> None:
    d = Ambiente(cfg).c.get(f"{EP}/cortes/0/editor").json()
    assert d["motion"] is None and d["motion_erro"] is None


def test_cache_do_motion_invalido_nao_derruba_o_editor(cfg: Config) -> None:
    a = ambiente_f3(cfg)
    (a.d / "motion" / "cenas.json").write_text('{"formato": 2}', encoding="utf-8")
    d = a.c.get(f"{EP}/cortes/0/editor").json()
    assert d["motion"] is None and "cache do motion inválido" in d["motion_erro"]


def test_refazer_motion_apaga_o_cache_e_pede_a_previa(cfg: Config) -> None:
    a = ambiente_f3(cfg)
    d = a.c.post(f"{EP}/cortes/0/motion/refazer").json()
    assert d["previa"]["situacao"] == "preparando" and d["motion"] is None
    assert not (a.d / "motion").exists()


def test_refazer_motion_recusado_com_a_previa_preparando(cfg: Config) -> None:
    a = ambiente_f3(cfg)
    a.previas.pedir("abcdefghijk", 0)
    r = a.c.post(f"{EP}/cortes/0/motion/refazer")
    assert r.status_code == 422 and "preparada" in r.json()["detail"]
    assert (a.d / "motion" / "cenas.json").exists()


def test_refazer_motion_recusado_fora_do_f3(cfg: Config) -> None:
    r = Ambiente(cfg).c.post(f"{EP}/cortes/0/motion/refazer")
    assert r.status_code == 422 and "f3" in r.json()["detail"]


def test_editor_mostra_o_tema_do_llm_e_a_escolha(cfg: Config) -> None:
    a = ambiente_f3(cfg)
    m = a.c.get(f"{EP}/cortes/0/editor").json()["motion"]
    assert (m["tema"], m["tema_llm"], m["tema_escolha"]) == ("dados", "dados", "auto")
    m = a.c.post(f"{EP}/cortes/0/editar", json={"tema": "noite"}).json()["motion"]
    assert (m["tema"], m["tema_escolha"]) == ("noite", "noite") and ler_corte(a.d).edicoes.tema == "noite"


def test_editor_mostra_a_ilustracao_recusada(cfg: Config) -> None:
    a = ambiente_f3(cfg)
    cena = Cena(1, "ilustracao", 2.0, 4.5, Ilustracao("rosto", "TESTA", "pessoa"), ())
    gravar_cenas(a.d, Chave(0.7, 7.8, "h"), Resultado([cena], [], "clinico"))
    (a.d / "motion" / "svg").mkdir(parents=True)
    (a.d / "motion" / "svg" / "1.json").write_text(
        json.dumps({"chave": {"descricao": "rosto", "tema": "clinico"}, "svg": None,
                    "motivo": "SVG recusado: x"}),
        encoding="utf-8")
    m = a.c.get(f"{EP}/cortes/0/editor").json()["motion"]
    assert m["cenas"][0]["falha_svg"] == "SVG recusado: x"
