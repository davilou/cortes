"""Etapa de ilustração do f9 pelo pipeline, com falsos: nada de rede nem de LLM no check."""
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from ddgs.exceptions import DDGSException

from cortes.llm import ErroLLM
from cortes.render.corte import concluir
from cortes.render.ilustracao_etapa import NENHUMA, ler_ilustracoes
from cortes.render.pipeline import DepRender, montar_projeto, renderizar_corte
from cortes.render.processo import ErroRender
from tests.test_render_pipeline import C, Falso, episodio

TEXTOS = ["Comprei", "um", "tênis", "Vans", "Old", "Skool", "e", "depois", "de", "um", "tempo", "comprei",
          "também", "a", "camisa", "do", "Timão.", "Foi", "isso", "aí."]
C9 = replace(C, formato="f9", fim=16.0)


class Ilustra:
    """Falsos das três dependências do f9, contando as chamadas."""

    def __init__(self, deixas: list[dict[str, Any]], escolhas: list[dict[str, Any]],
                 falha_busca: str | None = None) -> None:
        self.deixas, self.escolhas, self.falha_busca = deixas, escolhas, falha_busca
        self.llm = self.conferencias = 0
        self.buscas: list[str] = []
        self.pasta_read: Path | None = None
        self.downloads: list[str] = []

    def chamar_llm(self, prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
        self.llm += 1
        return {"deixas": self.deixas}

    def chamar_com_read(self, prompt: str, schema: dict[str, Any], sistema: str, modelo: str,
                        pasta: Path) -> dict[str, Any]:
        self.conferencias += 1
        self.pasta_read = pasta
        return {"escolhas": self.escolhas}

    def images(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        self.buscas.append(query)
        if query == self.falha_busca:
            raise DDGSException("Ratelimit")
        return [{"image": f"http://img/{query}/{j}.jpg", "url": f"http://loja/{j}", "width": 1000,
                 "height": 1000} for j in (1, 2)]

    def baixar(self, args: list[str], cwd: Path | None) -> tuple[int, str]:
        self.downloads.append(args[args.index("-i") + 1])
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


VANS = {"inicio_palavra": 3, "fim_palavra": 5, "coisa": "Vans", "busca": "tênis Vans Old Skool"}
CAMISA = {"inicio_palavra": 14, "fim_palavra": 16, "coisa": "camisa", "busca": "camisa do Corinthians"}


def test_f9_ilustra_uma_vez_e_reaproveita_o_cache(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS], [{"deixa": 1, "imagem": 2, "motivo": "é o tênis"}])
    renderizar_corte(pasta, C9, tmp_path, il.dep(f))
    renderizar_corte(pasta, concluir(C9), tmp_path, il.dep(f))
    # recorte, rosto, folha, MP4 — e no segundo render só o MP4; os downloads têm prazo próprio
    assert f.chamadas == ["ffmpeg", "py-visao", "ffmpeg", "npx", "npx"]
    assert il.downloads == ["http://img/tênis Vans Old Skool/1.jpg", "http://img/tênis Vans Old Skool/2.jpg"]
    assert (il.llm, il.conferencias, il.buscas) == (1, 1, ["tênis Vans Old Skool"])
    d = pasta / "cortes" / "0"
    assert il.pasta_read == d / "ilustracao" and (d / "ilustracao" / "folha.jpg").exists()
    lido = ler_ilustracoes(d)
    assert lido is not None
    [i] = lido[2]
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
                 falha_busca="tênis Vans Old Skool")
    montar_projeto(pasta, C9, tmp_path, il.dep(f))
    lido = ler_ilustracoes(pasta / "cortes" / "0")
    assert lido is not None
    vans, camisa = lido[2]
    assert vans.imagem is None and "Ratelimit" in vans.motivo
    assert camisa.imagem is not None and camisa.motivo == "é a camisa"
    html = (pasta / "cortes" / "0" / "projeto" / "index.html").read_text(encoding="utf-8")
    assert "ilus-2.jpg" in html and "ilus-1.jpg" not in html


def test_f9_sem_nenhuma_imagem_e_erro_e_nao_grava_cache(tmp_path: Path) -> None:
    pasta, f = ep9(tmp_path), Falso()
    il = Ilustra([VANS], [{"deixa": 1, "imagem": None, "motivo": "nenhuma é Vans"}])
    with pytest.raises(ErroRender, match=NENHUMA + r".*nenhuma é Vans"):
        renderizar_corte(pasta, C9, tmp_path, il.dep(f))
    assert "npx" not in f.chamadas and ler_ilustracoes(pasta / "cortes" / "0") is None


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
