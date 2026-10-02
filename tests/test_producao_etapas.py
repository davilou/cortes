import json
import wave
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from cortes.producao.estado import ErroProducao, novo
from cortes.producao.etapas import Dependencias, rodar_etapa
from cortes.producao.legenda_yt import ARQUIVO

AGORA = datetime(2026, 10, 2, 9)
PERFIL = """nicho: financas
filtro_tema: "x"
rubrica: {gancho_3s: 0.3, autocontido: 0.25, espanto: 0.2, historia_ou_virada: 0.1, fechamento: 0.15}
bonus: {humor: "faz rir"}
penalidade: {}
duracao_s: {min: 1, max: 90}
"""


def raiz_com_nicho(tmp: Path) -> Path:
    n = tmp / "nichos" / "financas"
    (n / "exemplos").mkdir(parents=True)
    (n / "perfil.yaml").write_text(PERFIL, encoding="utf-8")
    for a in ("bons.jsonl", "ruins.jsonl"):
        (n / "exemplos" / a).write_text("", encoding="utf-8")
    return tmp


def wav_silencio(arq: Path, segundos: int = 4) -> None:
    with wave.open(str(arq), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000 * segundos)


class Falsas:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def dep(self) -> Dependencias:
        def baixar_video(url: str, d: Path) -> None:
            self.chamadas.append("video")
            (d / "video.mp4").write_bytes(b"x")
            (d / "meta.json").write_text('{"titulo": "T"}', encoding="utf-8")

        def extrair_audio(d: Path) -> None:
            self.chamadas.append("audio")
            wav_silencio(d / "audio.wav")

        def baixar_legenda(url: str, d: Path) -> Path:
            self.chamadas.append("legenda")
            evs = [{"tStartMs": 0, "dDurationMs": 3000, "segs": [
                {"utf8": "Eu"}, {"utf8": " ganhei", "tOffsetMs": 300}, {"utf8": " dez", "tOffsetMs": 700},
                {"utf8": " mil.", "tOffsetMs": 1000}]}]
            (d / ARQUIVO).write_text(json.dumps({"events": evs}), encoding="utf-8")
            return d / ARQUIVO

        def chamar_llm(prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
            self.chamadas.append("llm")
            return {"candidatos": []}

        return Dependencias(baixar_video, extrair_audio, baixar_legenda, chamar_llm, "sonnet")


def test_etapas_em_ordem_gravam_seus_arquivos(tmp_path: Path) -> None:
    raiz = raiz_com_nicho(tmp_path)
    pasta = raiz / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    e = novo("abcdefghijk", "https://youtu.be/abcdefghijk", "financas", 5, "f7", AGORA)
    f = Falsas()
    for nome in ("video", "legenda", "sinais", "momentos"):
        rodar_etapa(nome, pasta, e, raiz, f.dep())
    assert f.chamadas == ["video", "audio", "legenda", "llm"]
    palavras = json.loads((pasta / "palavras.json").read_text(encoding="utf-8"))
    assert [p["texto"] for p in palavras] == ["Eu", "ganhei", "dez", "mil."]
    assert "energia" in json.loads((pasta / "sinais.json").read_text(encoding="utf-8"))
    assert json.loads((pasta / "candidatos.json").read_text(encoding="utf-8")) == []
    assert (pasta / "frases.json").exists() and (pasta / "descartados.json").exists()


def test_etapa_pula_o_que_ja_existe(tmp_path: Path) -> None:
    raiz = raiz_com_nicho(tmp_path)
    pasta = raiz / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    (pasta / "video.mp4").write_bytes(b"x")
    wav_silencio(pasta / "audio.wav")
    (pasta / "palavras.json").write_text(json.dumps([asdict_palavra("oi", 0, 1)]), encoding="utf-8")
    e = novo("abcdefghijk", "u", "financas", 5, "f7", AGORA)
    f = Falsas()
    rodar_etapa("video", pasta, e, raiz, f.dep())
    rodar_etapa("legenda", pasta, e, raiz, f.dep())
    assert f.chamadas == []


def asdict_palavra(t: str, i: float, f: float) -> dict[str, Any]:
    return {"texto": t, "inicio": i, "fim": f}


def test_nicho_inexistente_falha_com_caminho(tmp_path: Path) -> None:
    pasta = tmp_path / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    e = novo("abcdefghijk", "u", "humor", 5, "f7", AGORA)
    (pasta / "palavras.json").write_text(json.dumps([asdict_palavra("oi.", 0, 1)]), encoding="utf-8")
    (pasta / "sinais.json").write_text('{"janela_s": 0.5, "energia": [0.1, 0.1]}', encoding="utf-8")
    with pytest.raises(Exception, match="humor"):
        rodar_etapa("momentos", pasta, e, tmp_path, Falsas().dep())


def test_etapa_desconhecida(tmp_path: Path) -> None:
    e = novo("abcdefghijk", "u", "financas", 5, "f7", AGORA)
    with pytest.raises(ErroProducao, match="render"):
        rodar_etapa("render", tmp_path, e, tmp_path, Falsas().dep())


def test_etapas_do_estado_e_do_modulo_nao_divergem() -> None:
    from cortes.producao import etapas
    from cortes.producao.estado import ETAPAS

    assert tuple(etapas._ETAPAS) == ETAPAS
