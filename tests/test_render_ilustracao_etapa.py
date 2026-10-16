"""Etapa do B-roll do f4 pelo pipeline, com falsos: nada de rede, YouTube nem LLM no check."""
import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from ddgs.exceptions import DDGSException, RatelimitException

from cortes.llm import ErroLLM
from cortes.render.corte import concluir
from cortes.render.ilustracao_cache import ler_ilustracoes
from cortes.render.ilustracao_etapa import NENHUMA, TEMPORARIA
from cortes.render.montagem import F9_SAIU
from cortes.render.pipeline import DepRender, montar_projeto, renderizar_corte
from cortes.render.processo import ErroRender
from cortes.render.seo import SCHEMA as SCHEMA_SEO
from tests.test_render_pipeline import SEO, C, Falso, episodio

TEXTOS = ["Comprei", "um", "tênis", "Vans", "Old", "Skool", "e", "depois", "de", "um", "tempo", "comprei",
          "também", "a", "camisa", "do", "Timão.", "Foi", "isso", "aí."]
C4 = replace(C, formato="f4", fim=16.0)
BLOQUEIO = "ERROR: [youtube] x: HTTP Error 429: Too Many Requests"


def vid(busca: str, j: int) -> str:
    """Id de 11 caracteres válido e estável para o j-ésimo vídeo de uma busca."""
    return hashlib.md5(busca.encode()).hexdigest()[:10] + str(j)


class Ilustra:
    """Falsos das dependências do f4 (LLM, conferência, ddgs, fotos e YouTube), contando as chamadas."""

    def __init__(self, deixas: list[dict[str, Any]], escolhas: list[dict[str, Any]],
                 falha_busca: tuple[str, ...] = (), sem_resultado: tuple[str, ...] = ()) -> None:
        self.deixas, self.escolhas, self.falha_busca = deixas, escolhas, falha_busca
        self.sem_resultado = sem_resultado
        self.falha_download: dict[str, str] = {}   # trecho da URL → saída do ffmpeg que falhou
        self.falha_yt: set[str] = set()            # buscas cuja busca no YouTube dá 429
        self.sem_video: set[str] = set()           # buscas sem vídeo no YouTube
        self.falha_trecho: dict[str, str] = {}     # id do vídeo → saída do yt-dlp que falhou
        self.llm = self.conferencias = 0
        self.buscas: list[str] = []
        self.buscas_yt: list[str] = []
        self.trechos: list[str] = []
        self.ffmpeg: list[list[str]] = []
        self.pasta_read: Path | None = None
        self.downloads: list[str] = []
        self.prompts_llm: list[str] = []
        self.prompts_conferencia: list[str] = []

    def chamar_llm(self, prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
        if schema is SCHEMA_SEO:   # o SEO do render não conta como chamada do B-roll
            return SEO
        self.llm += 1
        self.prompts_llm.append(prompt)
        return {"deixas": self.deixas}

    def chamar_com_read(self, prompt: str, schema: dict[str, Any], sistema: str, modelo: str,
                        pasta: Path) -> dict[str, Any]:
        """Responde só sobre as deixas que a folha mostra, como o modelo de verdade."""
        self.conferencias += 1
        self.pasta_read = pasta
        self.prompts_conferencia.append(prompt)
        return {"escolhas": [e for e in self.escolhas if f"- D{e['deixa']} (" in prompt]}

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

    def busca_yt(self, args: list[str], cwd: Path | None) -> tuple[int, str]:
        busca = args[-1].split(":", 1)[1]
        self.buscas_yt.append(busca)
        if busca in self.falha_yt:
            return 1, BLOQUEIO
        if busca in self.sem_video:
            return 0, ""
        return 0, "\n".join(f"{vid(busca, j)}|90|Canal {j}|Vídeo {j} de {busca}" for j in (1, 2, 3))

    def video(self, args: list[str], cwd: Path | None) -> tuple[int, str]:
        """yt-dlp do trecho e ffmpeg (tela cheia, quadros, foto cheia): grava as saídas."""
        if "yt_dlp" in args:
            url = args[-1]
            self.trechos.append(url)
            for id_, saida in self.falha_trecho.items():
                if id_ in url:
                    return 1, saida
            Path(args[args.index("-o") + 1].replace("%(ext)s", "mp4")).write_bytes(b"bruto")
            return 0, ""
        self.ffmpeg.append(args)
        for i, a in enumerate(args):
            if a.endswith((".mp4", ".jpg")) and args[i - 1] != "-i":
                Path(a).write_bytes(b"x")
        return 0, ""

    def dep(self, f: Falso) -> DepRender:
        return replace(f.dep(), chamar_llm=self.chamar_llm, chamar_llm_com_read=self.chamar_com_read,
                       ddgs=lambda: self, rodar_download=self.baixar, rodar_busca_video=self.busca_yt,
                       rodar_video=self.video)


def ep4(tmp: Path) -> Path:
    pasta = episodio(tmp)
    palavras = [{"texto": t, "inicio": round(10.1 + i * 0.3, 2), "fim": round(10.35 + i * 0.3, 2)}
                for i, t in enumerate(TEXTOS)]
    (pasta / "palavras.json").write_text(json.dumps(palavras), encoding="utf-8")
    return pasta


VANS = {"inicio_palavra": 3, "fim_palavra": 5, "coisa": "Vans", "busca": "tênis Vans Old Skool",
        "tipo": "literal"}
CAMISA = {"inicio_palavra": 14, "fim_palavra": 16, "coisa": "camisa", "busca": "camisa do Corinthians",
          "tipo": "literal"}
TEMPO = {**CAMISA, "coisa": "o tempo passando", "busca": "time lapse clock", "tipo": "acontecimento"}


def _e(k: int, cand: str | None, motivo: str = "ok") -> dict[str, Any]:
    return {"deixa": k, "candidato": cand, "motivo": motivo}


def _d(pasta: Path) -> Path:
    return pasta / "cortes" / "0"


def _lido(pasta: Path):  # type: ignore[no-untyped-def]
    lido = ler_ilustracoes(_d(pasta))
    assert lido is not None
    return lido


def test_f4_escolhe_o_video_e_reaproveita_o_cache(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS], [_e(1, "V2m3", "é o tênis")])
    renderizar_corte(pasta, C4, tmp_path, il.dep(f))
    renderizar_corte(pasta, concluir(C4), tmp_path, il.dep(f))
    # recorte, rosto, folha, MP4 — e no segundo render só o MP4; YouTube e fotos têm executor próprio
    assert f.chamadas == ["ffmpeg", "py-visao", "ffmpeg", "npx", "npx"]
    busca = VANS["busca"]
    assert il.buscas_yt == [busca] and il.buscas == [busca]   # literal: vídeo e foto
    assert il.trechos == [f"https://www.youtube.com/watch?v={vid(busca, j)}" for j in (1, 2)]   # 2, não 3
    assert (il.llm, il.conferencias) == (1, 1) and il.pasta_read == _d(pasta) / "ilustracao"
    [i] = _lido(pasta).ilustracoes
    assert i.midia == "video" and i.arquivo == _d(pasta) / "ilustracao" / "D1-v2.mp4"
    # o 3º momento do vídeo de 90 s começa a 55%: 49,5 s; a fonte aponta para ele
    assert i.fonte is not None and i.fonte.canal == "Canal 2"
    assert i.fonte.url.endswith(f"{vid(busca, 2)}&t=49s")
    [corte] = [a for a in il.ffmpeg if any(x.endswith("D1-v2.parcial.mp4") for x in a)]
    assert corte[corte.index("-ss") + 1] == "49.500"
    assert corte[corte.index("-i") + 1].endswith("D1-v2.bruto.mp4")
    assert not list((_d(pasta) / "ilustracao").glob("*.bruto.*"))   # os vídeos baixados foram apagados
    assert (_d(pasta) / "ilustracao" / "D1-v2-q2.jpg").exists()      # a miniatura do editor
    assert (_d(pasta) / "projeto" / "assets" / "broll-1.mp4").exists()
    html = (_d(pasta) / "projeto" / "index.html").read_text(encoding="utf-8")
    assert '<video class="clip broll" id="broll-1"' in html and 'src="assets/broll-1.mp4"' in html
    assert "{{" not in html


def test_folha_e_conferencia_marcam_video_e_foto(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS, TEMPO], [_e(1, "V1m1"), _e(2, "V1m1")])
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    [prompt] = il.prompts_conferencia
    assert "- D1 (literal, coisa citada)" in prompt and "vídeo D1-V2, momentos m1 a m4; fotos D1-F1" in prompt
    assert "- D2 (acontecimento, só vídeo)" in prompt and "D2-F" not in prompt
    assert il.buscas == [VANS["busca"]]   # acontecimento não busca foto
    assert (_d(pasta) / "ilustracao" / "D1-v1-q2.jpg").exists()
    assert (_d(pasta) / "ilustracao" / "D1-v2-m4-q3.jpg").exists()   # os quadros dos momentos ficam


def test_foto_escolhida_vira_tela_cheia(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS], [_e(1, "F2", "só a foto mostra o modelo")])
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    [i] = _lido(pasta).ilustracoes
    assert i.midia == "foto" and i.arquivo == _d(pasta) / "ilustracao" / "D1-c2-cheia.jpg"
    assert i.fonte is not None and i.fonte.url == "http://loja/2"
    html = (_d(pasta) / "projeto" / "index.html").read_text(encoding="utf-8")
    assert '<div class="clip broll" id="broll-1"' in html
    assert '<img src="assets/broll-1.jpg" alt="Vans">' in html


def test_429_na_busca_para_o_youtube_na_rodada_e_a_foto_cobre_a_literal(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS, CAMISA], [_e(1, "F1"), _e(2, "F1")])
    il.falha_yt = {VANS["busca"]}
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assert il.buscas_yt == [VANS["busca"]] and il.trechos == []   # a camisa nem tenta o YouTube
    vans, camisa = _lido(pasta).ilustracoes
    assert vans.midia == camisa.midia == "foto" and not vans.transitorio
    assert "limitou ou bloqueou" in vans.falhas[0] and "não buscado" in camisa.falhas[0]


def test_429_no_trecho_nao_tenta_o_proximo_video_e_e_transitorio(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([TEMPO], [_e(1, "V1m1")])
    il.falha_trecho = {vid(TEMPO["busca"], 1): BLOQUEIO}
    with pytest.raises(ErroRender, match=re.escape(TEMPORARIA) + ".*limitou ou bloqueou"):
        montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assert len(il.trechos) == 1 and il.conferencias == 0
    il.falha_trecho = {}
    montar_projeto(pasta, C4, tmp_path, il.dep(f))   # refeito sem o LLM
    assert il.llm == 1 and len(il.trechos) == 3 and _lido(pasta).ilustracoes[0].midia == "video"


def test_acontecimento_sem_video_fica_sem_visual_com_o_motivo(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS, TEMPO], [_e(1, "V1m1")])
    il.sem_video = {TEMPO["busca"]}
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    vans, tempo = _lido(pasta).ilustracoes
    assert vans.midia == "video" and tempo.midia is None and not tempo.transitorio
    assert "sem visual" in tempo.motivo and "acontecimento: sem foto de reserva" in tempo.motivo
    assert not (_d(pasta) / "projeto" / "assets" / "broll-2.mp4").exists()


def test_trecho_novo_apaga_o_broll_e_refaz(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS], [_e(1, "V1m1")])
    montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assets = _d(pasta) / "projeto" / "assets"
    (assets / "broll-7.mp4").write_bytes(b"velho")
    (assets / "ilus-3.jpg").write_bytes(b"cartao do f9")
    montar_projeto(pasta, replace(C4, inicio=10.2), tmp_path, il.dep(f))
    assert il.llm == 2 and not (assets / "broll-7.mp4").exists() and not (assets / "ilus-3.jpg").exists()


def test_f4_sem_visual_nenhum_e_erro(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS], [_e(1, None, "nenhum é Vans")])
    with pytest.raises(ErroRender, match=re.escape(NENHUMA) + r".*nenhum é Vans"):
        renderizar_corte(pasta, C4, tmp_path, il.dep(f))
    assert "npx" not in f.chamadas


def test_f4_sem_deixa_nenhuma_e_erro(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([], [])
    with pytest.raises(ErroRender, match=re.escape(NENHUMA)):
        montar_projeto(pasta, C4, tmp_path, il.dep(f))
    assert il.conferencias == 0 and il.buscas == il.buscas_yt == []


def test_f4_erro_do_llm_vira_erro_de_render_com_a_causa(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS], [])

    def quebra(*_: Any) -> dict[str, Any]:
        raise ErroLLM("claude saiu com código 1")

    dep = replace(il.dep(f), chamar_llm=quebra)
    with pytest.raises(ErroRender, match="B-roll: claude saiu com código 1"):
        montar_projeto(pasta, C4, tmp_path, dep)


def test_outro_formato_nao_faz_broll(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS], [])
    montar_projeto(pasta, C, tmp_path, il.dep(f))
    assert il.llm == 0 and not (_d(pasta) / "ilustracao").exists()


def test_corte_antigo_em_f9_da_erro_claro_sem_converter(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS], [])
    with pytest.raises(ErroRender, match=F9_SAIU):
        renderizar_corte(pasta, replace(C4, formato="f9"), tmp_path, il.dep(f))
    assert il.llm == 0 and f.chamadas == []


def test_ytdlp_quebrado_na_busca_derruba_o_corte_com_a_mensagem(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS], [_e(1, "F1")])

    def quebrado(args: list[str], cwd: Path | None) -> tuple[int, str]:
        return 1, "No module named yt_dlp"

    with pytest.raises(ErroRender, match="No module named yt_dlp") as ex:
        montar_projeto(pasta, C4, tmp_path, replace(il.dep(f), rodar_busca_video=quebrado))
    assert TEMPORARIA not in str(ex.value) and il.conferencias == 0


def test_foto_que_nao_monta_em_tela_cheia_fica_sem_visual_com_o_motivo(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS, TEMPO], [_e(1, "F1"), _e(2, "V1m1")])
    video = il.video

    def cheia_quebra(args: list[str], cwd: Path | None) -> tuple[int, str]:
        if any(a.endswith("-cheia.parcial.jpg") for a in args):
            return 1, "Invalid data found when processing input"
        return video(args, cwd)

    montar_projeto(pasta, C4, tmp_path, replace(il.dep(f), rodar_video=cheia_quebra))
    vans, tempo = _lido(pasta).ilustracoes
    assert vans.midia is None and not vans.transitorio and tempo.midia == "video"
    assert "tela cheia" in vans.motivo and "Invalid data" in vans.motivo


def test_erro_do_llm_na_conferencia_nao_refaz_os_downloads(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS, TEMPO], [_e(1, "F1"), _e(2, "V2m1")])
    conferir = il.chamar_com_read

    def falha_uma_vez(*args: Any) -> dict[str, Any]:
        if il.conferencias == 0:
            il.conferencias += 1
            raise ErroLLM("claude saiu com código 1")
        return conferir(*args)

    dep = replace(il.dep(f), chamar_llm_com_read=falha_uma_vez)
    with pytest.raises(ErroRender, match="B-roll: claude saiu com código 1"):
        montar_projeto(pasta, C4, tmp_path, dep)
    baixados = (list(il.buscas_yt), list(il.trechos), list(il.buscas), list(il.downloads))
    montar_projeto(pasta, C4, tmp_path, dep)
    assert (il.buscas_yt, il.trechos, il.buscas, il.downloads) == baixados and il.llm == 1
    vans, tempo = _lido(pasta).ilustracoes
    assert vans.midia == "foto" and tempo.midia == "video" and tempo.fonte is not None
    assert tempo.fonte.url.endswith(f"{vid(TEMPO['busca'], 2)}&t=13s") and tempo.fonte.canal == "Canal 2"
    assert not list((_d(pasta) / "ilustracao").glob("*.bruto.*"))
    assert not (_d(pasta) / "ilustracao" / "candidatos.json").exists()


def test_trecho_do_momento_que_nao_sai_fica_sem_visual_e_apaga_os_videos(tmp_path: Path) -> None:
    pasta, f = ep4(tmp_path), Falso()
    il = Ilustra([VANS, TEMPO], [_e(1, "F1"), _e(2, "V1m2")])
    video = il.video

    def corte_quebra(args: list[str], cwd: Path | None) -> tuple[int, str]:
        if any(a.endswith("D2-v1.parcial.mp4") for a in args):
            return 1, "Invalid data found when processing input"
        return video(args, cwd)

    montar_projeto(pasta, C4, tmp_path, replace(il.dep(f), rodar_video=corte_quebra))
    vans, tempo = _lido(pasta).ilustracoes
    assert vans.midia == "foto" and tempo.midia is None and not tempo.transitorio
    assert "V1m2" in tempo.motivo and "Invalid data" in tempo.motivo
    assert not list((_d(pasta) / "ilustracao").glob("*.bruto.*"))
