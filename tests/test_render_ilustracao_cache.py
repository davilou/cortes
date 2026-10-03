"""Cache do f4 B-roll: deixas do LLM em `deixas.json`, escolhas em `ilustracao.json`, falha
temporária refeita sem o LLM, "nada a mostrar" guardado e a chave com o texto da fala."""
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from cortes.render.corte import Edicoes
from cortes.render.ilustracao_cache import ARQUIVO_DEIXAS, ler_ilustracoes
from cortes.render.ilustracao_etapa import NENHUMA, TEMPORARIA
from cortes.render.pipeline import montar_projeto
from cortes.render.processo import ErroRender
from tests.test_render_ilustracao_etapa import C4, CAMISA, TEMPO, VANS, Ilustra, _d, _e, _lido, ep4
from tests.test_render_pipeline import Falso

OK = [_e(1, "V1", "é o tênis"), _e(2, "V1", "é a camisa")]
BUSCA_VANS, BUSCA_CAMISA, BUSCA_TEMPO = VANS["busca"], CAMISA["busca"], TEMPO["busca"]


def test_deixas_ficam_num_arquivo_proprio_com_a_chave(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    montar_projeto(pasta, C4, tmp_path, Ilustra([VANS], OK).dep(f))
    bruto = json.loads((_d(pasta) / "ilustracao" / ARQUIVO_DEIXAS).read_text(encoding="utf-8"))
    assert set(bruto["chave"]) == {"inicio", "fim", "texto"} and len(bruto["chave"]["texto"]) == 64
    assert [(d["coisa"], d["tipo"]) for d in bruto["deixas"]] == [("Vans", "literal")]


def test_escolha_guarda_midia_fonte_licenca_e_risco(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    montar_projeto(pasta, C4, tmp_path, Ilustra([VANS, CAMISA], [_e(1, "V1"), _e(2, "F1")]).dep(f))
    bruto = json.loads((_d(pasta) / "ilustracao" / "ilustracao.json").read_text(encoding="utf-8"))
    video, foto = bruto["ilustracoes"]
    assert (video["midia"], video["arquivo"], video["canal"]) == ("video", "D1-v1.mp4", "Canal 1")
    assert (video["licenca"], video["risco"]) == ("desconhecida (YouTube)", "alto")
    assert (foto["midia"], foto["arquivo"], foto["fonte_url"]) == ("foto", "D2-c1-cheia.jpg", "http://loja/1")
    assert foto["licenca"] == "desconhecida"


def test_youtube_que_falhou_e_refeito_sem_llm_e_so_ele_vai_a_conferencia(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS, TEMPO], [_e(1, "F1"), _e(2, "V1")])
    il.falha_yt = {BUSCA_VANS}   # a foto cobre o Vans; o acontecimento nem tenta o YouTube
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    vans, tempo = _lido(pasta).ilustracoes
    assert vans.midia == "foto" and not vans.transitorio and tempo.midia is None and tempo.transitorio
    il.falha_yt = set()
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assert (il.llm, il.conferencias, il.buscas_yt) == (1, 2, [BUSCA_VANS, BUSCA_TEMPO])
    assert "- D2 (" in il.prompts_conferencia[1] and "- D1 (" not in il.prompts_conferencia[1]
    vans2, tempo2 = _lido(pasta).ilustracoes
    assert tempo2.midia == "video" and not tempo2.transitorio and vans2 == vans
    assert (_d(pasta) / "projeto" / "assets" / "broll-2.mp4").exists()


def test_trecho_que_estourou_o_prazo_e_temporario_e_video_indisponivel_nao(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([TEMPO], [])
    il.falha_trecho = {"watch": "python passou de 90 s e foi interrompido"}
    with pytest.raises(ErroRender, match=re.escape(TEMPORARIA)):
        montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assert _lido(pasta).ilustracoes[0].transitorio and len(il.trechos) == 2

    pasta2 = ep4(tmp_path / "b")
    il2 = Ilustra([TEMPO], [])
    il2.falha_trecho = {"watch": "ERROR: Video unavailable"}
    with pytest.raises(ErroRender, match=re.escape(NENHUMA)):
        montar_projeto(pasta2, C4, tmp_path / "b", il2.dep(f))
    assert not _lido(pasta2).ilustracoes[0].transitorio


def test_sem_video_nem_foto_nao_e_temporario_e_nao_e_refeito(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS, CAMISA], OK, sem_resultado=(BUSCA_VANS,))
    il.sem_video = {BUSCA_VANS}
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    vans = _lido(pasta).ilustracoes[0]
    assert vans.midia is None and not vans.transitorio and il.buscas_yt == [BUSCA_VANS, BUSCA_CAMISA]


def test_sem_deixa_nenhuma_fica_em_cache_e_nao_chama_o_llm_de_novo(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([], [])
    for _ in range(2):
        with pytest.raises(ErroRender, match=re.escape(NENHUMA)):
            montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assert il.llm == 1 and _lido(pasta).vazio is not None


def test_conferencia_que_recusa_tudo_fica_em_cache(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS], [_e(1, None, "nenhum é Vans")])
    for _ in range(2):
        with pytest.raises(ErroRender, match=re.escape(NENHUMA) + r".*nenhum é Vans"):
            montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assert (il.llm, il.conferencias, il.buscas_yt) == (1, 1, [BUSCA_VANS])


def test_youtube_e_fotos_fora_do_ar_nao_viram_vazio_em_cache(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS, CAMISA], OK, falha_busca=(BUSCA_VANS, BUSCA_CAMISA))
    il.falha_yt = {BUSCA_VANS}
    with pytest.raises(ErroRender, match=re.escape(TEMPORARIA) + ".*Ratelimit"):
        montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assert _lido(pasta).vazio is None
    il.falha_busca, il.falha_yt = (), set()
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assert il.llm == 1 and all(i.midia == "video" for i in _lido(pasta).ilustracoes)


def test_corrigir_palavra_da_legenda_refaz_as_deixas(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS], OK)
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    montar_projeto(pasta, replace(C4, edicoes=Edicoes(legenda={3: "Vanz"})), tmp_path, il.dep(f))
    assert il.llm == 2 and "[3] Vanz" in il.prompts_llm[1]


def test_mascarar_palavrao_nao_muda_o_prompt_nem_refaz(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS], OK)
    montar_projeto(pasta, replace(C4, edicoes=Edicoes(mascaradas=(2,))), tmp_path, il.dep(f))
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assert il.llm == 1 and "[2] tênis" in il.prompts_llm[0]
    html = (_d(pasta) / "projeto" / "index.html").read_text(encoding="utf-8")
    assert "tênis" in html   # a legenda do segundo render, sem máscara


@pytest.mark.parametrize("apagado", ["D1-v1.mp4", "D1-v1-q2.jpg"])
def test_trecho_ou_miniatura_apagados_refazem_a_escolha_sem_o_llm(tmp_path: Path, apagado: str) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS], OK)
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    (_d(pasta) / "ilustracao" / apagado).unlink()
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assert (il.llm, il.buscas_yt, il.conferencias) == (1, [BUSCA_VANS] * 2, 2)
    assert (_d(pasta) / "ilustracao" / apagado).exists()


def test_clipe_velho_some_dos_assets_mesmo_com_cache(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS], OK)
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assets = _d(pasta) / "projeto" / "assets"
    (assets / "broll-7.jpg").write_bytes(b"velha")
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assert il.llm == 1 and not (assets / "broll-7.jpg").exists() and (assets / "broll-1.mp4").exists()


@pytest.mark.parametrize("nome", ["../../segredo.mp4", "..", "sub/D1-v1.mp4", "C:D1-v1.mp4", ""])
def test_nome_de_arquivo_com_caminho_no_cache_e_erro(tmp_path: Path, nome: str) -> None:
    pasta, f = ep4(tmp_path), Falso()
    montar_projeto(pasta, C4, tmp_path, Ilustra([VANS], OK).dep(f))
    arq = _d(pasta) / "ilustracao" / "ilustracao.json"
    bruto = json.loads(arq.read_text(encoding="utf-8"))
    bruto["ilustracoes"][0]["arquivo"] = nome
    arq.write_text(json.dumps(bruto), encoding="utf-8")
    with pytest.raises(ErroRender, match="cache da ilustração inválido"):
        ler_ilustracoes(_d(pasta))


@pytest.mark.parametrize("campo,valor,causa", [("midia", "gif", "mídia inválida"),
                                                ("midia", None, "não combina"),
                                                ("tipo", "foto", "tipo de deixa inválido")])
def test_midia_ou_tipo_invalidos_no_cache_sao_erro(tmp_path: Path, campo: str, valor: str | None,
                                                   causa: str) -> None:
    pasta, f = ep4(tmp_path), Falso()
    montar_projeto(pasta, C4, tmp_path, Ilustra([VANS], OK).dep(f))
    arq = _d(pasta) / "ilustracao" / "ilustracao.json"
    bruto = json.loads(arq.read_text(encoding="utf-8"))
    bruto["ilustracoes"][0][campo] = valor
    arq.write_text(json.dumps(bruto), encoding="utf-8")
    with pytest.raises(ErroRender, match=f"cache da ilustração inválido.*{causa}"):
        ler_ilustracoes(_d(pasta))


def test_cache_sem_formato_e_refeito(tmp_path: Path) -> None:
    pasta = ep4(tmp_path)
    arq = _d(pasta) / "ilustracao" / "ilustracao.json"
    arq.parent.mkdir(parents=True)
    arq.write_text(json.dumps({"inicio": 10.0, "fim": 16.0, "ilustracoes": []}), encoding="utf-8")
    assert ler_ilustracoes(_d(pasta)) is None


def test_cache_do_f9_formato_3_e_refeito(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS], OK)
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    for nome in ("ilustracao.json", ARQUIVO_DEIXAS):
        arq = _d(pasta) / "ilustracao" / nome
        bruto = json.loads(arq.read_text(encoding="utf-8"))
        arq.write_text(json.dumps({**bruto, "formato": 3}), encoding="utf-8")
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assert il.llm == 2
