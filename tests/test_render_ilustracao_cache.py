"""Cache do f9 Ilustrado: deixas do LLM em `deixas.json`, escolhas em `ilustracao.json`, falha
temporária refeita sem o LLM, "nada ilustrável" guardado e a chave com o texto da fala."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from cortes.render.corte import Edicoes
from cortes.render.ilustracao_cache import ARQUIVO_DEIXAS, ler_ilustracoes
from cortes.render.ilustracao_etapa import BUSCA_FORA, NENHUMA
from cortes.render.pipeline import montar_projeto
from cortes.render.processo import ErroRender
from tests.test_render_ilustracao_etapa import C9, CAMISA, VANS, Ilustra, ep9
from tests.test_render_pipeline import Falso

OK = [{"deixa": 1, "imagem": 1, "motivo": "é o tênis"}, {"deixa": 2, "imagem": 1, "motivo": "é a camisa"}]
BUSCA_VANS, BUSCA_CAMISA = VANS["busca"], CAMISA["busca"]


def _d(pasta: Path) -> Path:
    return pasta / "cortes" / "0"


def _lido(pasta: Path):  # type: ignore[no-untyped-def]
    lido = ler_ilustracoes(_d(pasta))
    assert lido is not None
    return lido


def test_deixas_ficam_num_arquivo_proprio_com_a_chave(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    montar_projeto(pasta, C9, tmp_path, Ilustra([VANS], OK).dep(f))
    bruto = json.loads((_d(pasta) / "ilustracao" / ARQUIVO_DEIXAS).read_text(encoding="utf-8"))
    assert set(bruto["chave"]) == {"inicio", "fim", "texto"} and len(bruto["chave"]["texto"]) == 64
    assert [d["coisa"] for d in bruto["deixas"]] == ["Vans"]


def test_busca_que_falhou_e_refeita_sem_llm_e_so_ela_vai_a_conferencia(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS, CAMISA], OK, falha_busca=(BUSCA_VANS,))
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    vans, camisa = _lido(pasta).ilustracoes
    assert vans.transitorio and vans.imagem is None and not camisa.transitorio
    il.falha_busca = ()
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    assert (il.llm, il.conferencias, il.buscas) == (1, 2, [BUSCA_VANS, BUSCA_CAMISA, BUSCA_VANS])
    assert "- D1:" in il.prompts_conferencia[1] and "- D2:" not in il.prompts_conferencia[1]
    vans2, camisa2 = _lido(pasta).ilustracoes
    assert vans2.imagem is not None and not vans2.transitorio and camisa2 == camisa
    assert (_d(pasta) / "projeto" / "assets" / "ilus-1.jpg").exists()


def test_download_que_estourou_o_prazo_e_temporario_e_404_nao(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS, CAMISA], OK)
    il.falha_download = {"Vans": "ffmpeg passou de 30 s e foi interrompido",
                         "Corinthians/1": "HTTP error 404", "Corinthians/2": "Server returned 404 Not Found"}
    with pytest.raises(ErroRender):
        montar_projeto(pasta, C9, tmp_path, il.dep(f))
    vans, camisa = _lido(pasta).ilustracoes
    assert vans.transitorio and "nenhuma candidata baixou" in vans.motivo
    assert not camisa.transitorio and camisa.imagem is None


def test_sem_resultado_nao_e_temporario_e_nao_e_refeito(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS, CAMISA], OK, sem_resultado=(BUSCA_VANS,))
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    assert not _lido(pasta).ilustracoes[0].transitorio and il.buscas == [BUSCA_VANS, BUSCA_CAMISA]


def test_sem_deixa_nenhuma_fica_em_cache_e_nao_chama_o_llm_de_novo(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([], [])
    for _ in range(2):
        with pytest.raises(ErroRender, match=NENHUMA):
            montar_projeto(pasta, C9, tmp_path, il.dep(f))
    assert il.llm == 1 and _lido(pasta).vazio is not None


def test_conferencia_que_recusa_tudo_fica_em_cache(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS], [{"deixa": 1, "imagem": None, "motivo": "nenhuma é Vans"}])
    for _ in range(2):
        with pytest.raises(ErroRender, match=NENHUMA + r".*nenhuma é Vans"):
            montar_projeto(pasta, C9, tmp_path, il.dep(f))
    assert (il.llm, il.conferencias, il.buscas) == (1, 1, [BUSCA_VANS])


def test_busca_fora_do_ar_nao_vira_vazio_em_cache(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS, CAMISA], OK, falha_busca=(BUSCA_VANS, BUSCA_CAMISA))
    with pytest.raises(ErroRender, match=BUSCA_FORA):
        montar_projeto(pasta, C9, tmp_path, il.dep(f))
    assert _lido(pasta).vazio is None
    il.falha_busca = ()
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    assert il.llm == 1 and all(i.imagem for i in _lido(pasta).ilustracoes)


def test_corrigir_palavra_da_legenda_refaz_as_deixas(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS], OK)
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    montar_projeto(pasta, replace(C9, edicoes=Edicoes(legenda={3: "Vanz"})), tmp_path, il.dep(f))
    assert il.llm == 2 and "[3] Vanz" in il.prompts_llm[1]


def test_mascarar_palavrao_nao_muda_o_prompt_nem_refaz(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS], OK)
    montar_projeto(pasta, replace(C9, edicoes=Edicoes(mascaradas=(2,))), tmp_path, il.dep(f))
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    assert il.llm == 1 and "[2] tênis" in il.prompts_llm[0]
    html = (_d(pasta) / "projeto" / "index.html").read_text(encoding="utf-8")
    assert "tênis" in html   # a legenda do segundo render, sem máscara


def test_imagem_apagada_refaz_a_escolha_sem_o_llm(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS], OK)
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    img = _lido(pasta).ilustracoes[0].imagem
    assert img is not None
    img.unlink()
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    assert (il.llm, il.buscas, il.conferencias) == (1, [BUSCA_VANS] * 2, 2) and img.exists()


def test_cartao_velho_some_dos_assets_mesmo_com_cache(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS], OK)
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    assets = _d(pasta) / "projeto" / "assets"
    (assets / "ilus-7.jpg").write_bytes(b"velha")
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    assert il.llm == 1 and not (assets / "ilus-7.jpg").exists() and (assets / "ilus-1.jpg").exists()


@pytest.mark.parametrize("nome", ["../../segredo.jpg", "..", "sub/D1-c1.jpg", "C:D1-c1.jpg", ""])
def test_nome_de_imagem_com_caminho_no_cache_e_erro(tmp_path: Path, nome: str) -> None:
    pasta, f = ep9(tmp_path), Falso()
    montar_projeto(pasta, C9, tmp_path, Ilustra([VANS], OK).dep(f))
    arq = _d(pasta) / "ilustracao" / "ilustracao.json"
    bruto = json.loads(arq.read_text(encoding="utf-8"))
    bruto["ilustracoes"][0]["imagem"] = nome
    arq.write_text(json.dumps(bruto), encoding="utf-8")
    with pytest.raises(ErroRender, match="cache da ilustração inválido"):
        ler_ilustracoes(_d(pasta))


def test_cache_de_formato_anterior_e_refeito(tmp_path: Path) -> None:
    pasta = ep9(tmp_path)
    arq = _d(pasta) / "ilustracao" / "ilustracao.json"
    arq.parent.mkdir(parents=True)
    arq.write_text(json.dumps({"inicio": 10.0, "fim": 16.0, "ilustracoes": []}), encoding="utf-8")
    assert ler_ilustracoes(_d(pasta)) is None
