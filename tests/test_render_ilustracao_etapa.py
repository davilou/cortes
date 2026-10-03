"""Etapa de ilustração do f9 pelo pipeline, com falsos: nada de rede nem de LLM no check."""
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from ddgs.exceptions import DDGSException, RatelimitException

from cortes.llm import ErroLLM
from cortes.render.corte import concluir
from cortes.render.ilustracao_cache import ler_ilustracoes
from cortes.render.ilustracao_etapa import NENHUMA
from cortes.render.pipeline import DepRender, montar_projeto, renderizar_corte
from cortes.render.processo import ErroRender
from tests.test_render_pipeline import C, Falso, episodio

TEXTOS = ["Comprei", "um", "tênis", "Vans", "Old", "Skool", "e", "depois", "de", "um", "tempo", "comprei",
          "também", "a", "camisa", "do", "Timão.", "Foi", "isso", "aí."]
C9 = replace(C, formato="f9", fim=16.0)


class Ilustra:
    """Falsos das três dependências do f9, contando as chamadas."""

    def __init__(self, deixas: list[dict[str, Any]], escolhas: list[dict[str, Any]],
                 falha_busca: tuple[str, ...] = (), sem_resultado: tuple[str, ...] = ()) -> None:
        self.deixas, self.escolhas, self.falha_busca = deixas, escolhas, falha_busca
        self.sem_resultado = sem_resultado
        self.falha_download: dict[str, str] = {}   # trecho da URL → saída do ffmpeg que falhou
        self.llm = self.conferencias = 0
        self.buscas: list[str] = []
        self.pasta_read: Path | None = None
        self.downloads: list[str] = []
        self.prompts_llm: list[str] = []
        self.prompts_conferencia: list[str] = []

    def chamar_llm(self, prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
        self.llm += 1
        self.prompts_llm.append(prompt)
        return {"deixas": self.deixas}

    def chamar_com_read(self, prompt: str, schema: dict[str, Any], sistema: str, modelo: str,
                        pasta: Path) -> dict[str, Any]:
        """Responde só sobre as deixas que a folha mostra, como o modelo de verdade."""
        self.conferencias += 1
        self.pasta_read = pasta
        self.prompts_conferencia.append(prompt)
        return {"escolhas": [e for e in self.escolhas if f"- D{e['deixa']}:" in prompt]}

    def images(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        self.buscas.append(query)
        if query in self.falha_busca:
            raise RatelimitException("Ratelimit")
        if query in self.sem_resultado:
            raise DDGSException("No results found.")
        return [{"image": f"http://img/{query}/{j}.jpg", "url": f"http://loja/{j}", "width": 1000,
                 "height": 1000} for j in (1, 2)]

    def baixar(self, args: list[str], cwd: Path | None) -> tuple[int, str]:
        url = args[args.index("-i") + 1]
        self.downloads.append(url)
        for trecho, saida in self.falha_download.items():
            if trecho in url:
                return 1, saida
        Path(args[-1]).write_bytes(b"jpg")
        return 0, ""

    def dep(self, f: Falso) -> DepRender:
        return replace(f.dep(), chamar_llm=self.chamar_llm, chamar_llm_com_read=self.chamar_com_read,
                       ddgs=lambda: self, rodar_download=self.baixar)


def ep9(tmp: Path) -> Path:
    pasta = episodio(tmp)
    palavras = [{"texto": t, "inicio": round(10.1 + i * 0.3, 2), "fim": round(10.35 + i * 0.3, 2)}
                for i, t in enumerate(TEXTOS)]
    (pasta / "palavras.json").write_text(json.dumps(palavras), encoding="utf-8")
    return pasta


VANS = {"inicio_palavra": 3, "fim_palavra": 5, "coisa": "Vans", "busca": "tênis Vans Old Skool",
        "tipo": "literal"}
CAMISA = {"inicio_palavra": 14, "fim_palavra": 16, "coisa": "camisa", "busca": "camisa do Corinthians",
          "tipo": "literal"}


def test_f9_ilustra_uma_vez_e_reaproveita_o_cache(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS], [{"deixa": 1, "imagem": 2, "motivo": "é o tênis"}])
    renderizar_corte(pasta, C9, tmp_path, il.dep(f))
    renderizar_corte(pasta, concluir(C9), tmp_path, il.dep(f))
    # recorte, rosto, folha, MP4 — e no segundo render só o MP4; os downloads têm prazo próprio
    assert f.chamadas == ["ffmpeg", "py-visao", "ffmpeg", "npx", "npx"]
    assert sorted(il.downloads) == [f"http://img/tênis Vans Old Skool/{j}.jpg" for j in (1, 2)]
    assert (il.llm, il.conferencias, il.buscas) == (1, 1, ["tênis Vans Old Skool"])
    d = pasta / "cortes" / "0"
    assert il.pasta_read == d / "ilustracao" and (d / "ilustracao" / "folha-1.jpg").exists()
    lido = ler_ilustracoes(d)
    assert lido is not None
    [i] = lido.ilustracoes
    assert i.imagem == d / "ilustracao" / "D1-c2.jpg" and i.fonte_url == "http://loja/2"
    assert (d / "projeto" / "assets" / "ilus-1.jpg").exists()
    html = (d / "projeto" / "index.html").read_text(encoding="utf-8")
    assert '<img src="assets/ilus-1.jpg" alt="Vans">' in html and "{{" not in html


def test_f9_trecho_novo_apaga_a_ilustracao_e_refaz(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS], [{"deixa": 1, "imagem": 1, "motivo": "ok"}])
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    assets = pasta / "cortes" / "0" / "projeto" / "assets"
    (assets / "ilus-7.jpg").write_bytes(b"velha")
    montar_projeto(pasta, replace(C9, inicio=10.2), tmp_path, il.dep(f))
    assert il.llm == 2 and not (assets / "ilus-7.jpg").exists()


def test_f9_busca_que_falha_deixa_so_aquela_deixa_sem_imagem(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS, CAMISA], [{"deixa": 2, "imagem": 1, "motivo": "é a camisa"}],
                 falha_busca=("tênis Vans Old Skool",))
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    lido = ler_ilustracoes(pasta / "cortes" / "0")
    assert lido is not None
    vans, camisa = lido.ilustracoes
    assert vans.imagem is None and "Ratelimit" in vans.motivo
    assert camisa.imagem is not None and camisa.motivo == "é a camisa"
    html = (pasta / "cortes" / "0" / "projeto" / "index.html").read_text(encoding="utf-8")
    assert "ilus-2.jpg" in html and "ilus-1.jpg" not in html


def test_f9_busca_sem_resultado_fica_sem_imagem_com_o_motivo(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS, CAMISA], [{"deixa": 2, "imagem": 1, "motivo": "é a camisa"}],
                 sem_resultado=("tênis Vans Old Skool",))
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    lido = ler_ilustracoes(pasta / "cortes" / "0")
    assert lido is not None
    assert "sem imagem: a busca 'tênis Vans Old Skool' não achou nada" in lido.ilustracoes[0].motivo


def test_f9_busca_falhando_em_todas_as_deixas_diz_que_foi_a_busca(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS, CAMISA], [], falha_busca=("tênis Vans Old Skool", "camisa do Corinthians"))
    with pytest.raises(ErroRender, match="busca de imagens falhou em todas as deixas.*Ratelimit") as ex:
        montar_projeto(pasta, C9, tmp_path, il.dep(f))
    assert NENHUMA not in str(ex.value) and il.conferencias == 0


def test_f9_sem_nenhuma_imagem_e_erro(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS], [{"deixa": 1, "imagem": None, "motivo": "nenhuma é Vans"}])
    with pytest.raises(ErroRender, match=NENHUMA + r".*nenhuma é Vans"):
        renderizar_corte(pasta, C9, tmp_path, il.dep(f))
    assert "npx" not in f.chamadas


def test_f9_sem_deixa_nenhuma_e_erro(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([], [])
    with pytest.raises(ErroRender, match=NENHUMA):
        montar_projeto(pasta, C9, tmp_path, il.dep(f))
    assert il.conferencias == 0 and il.buscas == []


def test_f9_erro_do_llm_vira_erro_de_render_com_a_causa(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS], [])

    def quebra(*_: Any) -> dict[str, Any]:
        raise ErroLLM("claude saiu com código 1")

    dep = replace(il.dep(f), chamar_llm=quebra)
    with pytest.raises(ErroRender, match="ilustração: claude saiu com código 1"):
        montar_projeto(pasta, C9, tmp_path, dep)


def test_outro_formato_nao_ilustra(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS], [])
    montar_projeto(pasta, C, tmp_path, il.dep(f))
    assert il.llm == 0 and not (pasta / "cortes" / "0" / "ilustracao").exists()
