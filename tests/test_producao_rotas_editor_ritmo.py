"""Editor do f7: ritmo de trocas e planos que alternam (render/conversa.py, plano melhora-f7)."""
import json
from dataclasses import replace

from cortes.painel.servidor import Config
from cortes.render.corte import gravar_corte, ler_corte
from tests.test_producao_rotas_editor import EP, Ambiente

PALAVRAS = [{"texto": "fala", "inicio": float(i), "fim": i + 0.8} for i in range(40)]
FACES = [{"x": 500, "y": 540, "r": 80, "conf": 0.9}, {"x": 500, "y": 540, "r": 80, "conf": 0.9},
         {"x": 1500, "y": 540, "r": 80, "conf": 0.9}]
ROSTO = {"formato": 2, "largura": 1920, "altura": 1080, "cortes": [],
         "amostras": [{"t": i * 0.25, "rostos": FACES} for i in range(125)]}


def _ambiente(cfg: Config, formato: str = "f7") -> Ambiente:
    """Um plano aberto de 31 s com duas pessoas; o recorte vale para o início/fim do corte."""
    a = Ambiente(cfg)
    (a.pasta / "palavras.json").write_text(json.dumps(PALAVRAS), encoding="utf-8")
    (a.d / "rosto.json").write_text(json.dumps(ROSTO), encoding="utf-8")
    gravar_corte(a.d, replace(ler_corte(a.d), inicio=1.0, fim=31.8, formato=formato))
    recorte = {"inicio": 0.7, "fim": 31.8, "segmentos": [[0.0, 31.1]]}
    (a.d / "recorte.json").write_text(json.dumps(recorte), encoding="utf-8")
    return a


def test_ritmo_do_f7_no_estado_do_editor(cfg: Config) -> None:
    d = _ambiente(cfg).c.get(f"{EP}/cortes/0/editor").json()
    assert d["ritmo"] == {"trocas_10s": 0.64, "alvo": [0.6, 0.8], "reais": 0, "alternancias": 2}
    assert [(p["alterna"], p["manual"]) for p in d["planos"]] == [(True, False)]


def test_escolha_manual_fixa_o_plano_e_automatico_volta_a_alternar(cfg: Config) -> None:
    a = _ambiente(cfg)
    d = a.c.post(f"{EP}/cortes/0/editar", json={"rosto": [0, 1]}).json()
    assert d["ritmo"]["alternancias"] == 0 and d["ritmo"]["trocas_10s"] == 0.0
    assert [(p["alterna"], p["manual"], p["escolha"]) for p in d["planos"]] == [(False, True, 1)]
    a.previas.processar("abcdefghijk", 0)
    d = a.c.post(f"{EP}/cortes/0/editar", json={"rosto": [0, -1]}).json()
    assert d["ritmo"]["alternancias"] == 2 and d["planos"][0]["manual"] is False


def test_sem_ritmo_fora_do_f7(cfg: Config) -> None:
    assert _ambiente(cfg, "f1").c.get(f"{EP}/cortes/0/editor").json()["ritmo"] is None


def test_sem_ritmo_sem_recorte_do_trecho_atual(cfg: Config) -> None:
    a = _ambiente(cfg)
    gravar_corte(a.d, replace(ler_corte(a.d), inicio=2.0))   # trecho mudou, a prévia ainda não recortou
    assert a.c.get(f"{EP}/cortes/0/editor").json()["ritmo"] is None
