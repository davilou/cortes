# Produção A — Do link aos candidatos, no painel

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Na aba Produção do painel, Davi cola o link de um episódio do YouTube; o app baixa vídeo e legenda do YouTube (sem Whisper), mede a energia, roda o detector numa fila em segundo plano com progresso por etapa, e mostra os candidatos com nota, rubrica, justificativa e o trecho tocando — com aprovar/rejeitar que alimenta os exemplos do detector.

**Architecture:** Pacote novo `src/cortes/producao/` (legenda do YouTube → palavras, estado do episódio, etapas, fila de uma thread, curadoria, rotas) montado no servidor do painel (`src/cortes/painel/servidor.py`). Decisões são funções puras testadas; I/O (yt-dlp, ffmpeg, `claude -p`) entra por dependências injetáveis. Front em JS puro: `web/static/js/episodios.js` (entrada + lista + fila) e `web/static/js/episodio.js` (candidatos + painel do trecho).

**Tech Stack:** Python 3.13 · FastAPI (lifespan) · yt-dlp · ffmpeg · `claude -p` (assinatura) · pytest · ruff · mypy --strict · HTML/CSS/JS puro

**Spec:** `docs/superpowers/specs/2026-10-02-producao-design.md` (plano A: §3, §4.1–4.5, §5 Episódios, §8, §9). Mockup: `docs/superpowers/specs/2026-10-02-producao-mockup.html`.

## Fatos verificados que este plano usa

- `yt-dlp --skip-download --write-auto-subs --write-subs --sub-langs pt --sub-format json3`
  baixou a legenda do PrimoCast 536 (`c5xqNNWFT9w`) em < 1 s: arquivo `<id>.pt.json3`, 2,1 MB.
  Pedir `pt.*` trouxe também `pt-PT` (tradução) e levou **HTTP 429** — pedir só `pt`.
- Estrutura do json3 (real): `{"events": [{"tStartMs": int, "dDurationMs": int, "wWinId": 1,
  "segs": [{"utf8": " começando", "tOffsetMs": 199, "acAsrConf": 0}, ...]}, ...]}`. Eventos com
  `"aAppend": 1` trazem só `{"utf8": "\n"}`. Marcas vêm como palavra `[música]`. Legenda
  automática tem um segmento por palavra com `tOffsetMs`; legenda manual traz a linha inteira
  num segmento sem `tOffsetMs`. Há pontuação (`"Primocast,"`, `"Primo."`).
- Contagem no PrimoCast 536: 20.234 palavras (Whisper 19.752), 1.425 fins de frase.
- `cortes.ingestao.baixar(url, destino)` grava `video.mp4`, `video.info.json`, `meta.json`
  (`titulo, canal, duracao_s, data, id`); `extrair_audio(destino)` grava `audio.wav` 16 kHz mono.
  Ambos levantam `ErroIngestao`. Invocação do yt-dlp: `[sys.executable, "-m", "yt_dlp", ...]`.
- `cortes.sinais.ler_wav_mono(audio)` + `energia_por_janela(amostras)` → `list[float]`;
  `sinais.JANELA_S`. `cortes.segmentacao.frases(palavras)` → `list[Frase]`.
- `cortes.detector.detectar(frases, energia, perfil, modelo, chamar_llm)` →
  `(list[Candidato], descartes)`; `Candidato` tem `inicio, fim, notas (dict 1–5 por critério da
  rubrica), bonus, penalidades, justificativa, titulo, nota_final (0–100)`. `cortes.llm.ErroLLM`
  é levantado em erro do CLI (inclusive limite de uso).
- `cortes.perfil.carregar_perfil(nichos/<nicho>)` lê `exemplos/bons.jsonl` e `ruins.jsonl`
  (objetos JSON livres, injetados no prompt como estão).
- `cortes.episodio.salvar_json` grava atômico; `ler_json` lê.
- `cortes.painel.dados.VIDEO_ID` = `re.compile(r"[A-Za-z0-9_-]{11}")`.
- Servidor: `criar_app(cfg, executar, abrir, agora)` em `src/cortes/painel/servidor.py`
  (238 linhas); `ErroPainel` → 422 por exception handler; `TrustedHostMiddleware` só
  127.0.0.1/localhost; StaticFiles montado por último. Testes usam
  `TestClient(app, base_url="http://127.0.0.1")` (helper `local(app)` em `tests/test_painel_servidor.py`).
- Starlette 1.7.0 / FastAPI 0.142.2: `FileResponse` atende `Range` (206) — necessário para o
  `<video>` pular para o trecho. `FastAPI(lifespan=...)` só roda o lifespan sob `uvicorn` ou
  `with TestClient(...)`.
- Front: telas registram `TELAS.<nome> = fn(meu)`; `desenhar()` passa o token `meu` e a tela
  confere `if (meu !== desenhar.n) return;` depois de cada `await`; `esc()` em todo texto da API;
  `api()`, `post()`, `avisar()`, `vazio()` em `base.js`; `index.html` tem `nav` + `.barra-mobile`.

## Estrutura de arquivos

```
src/cortes/producao/
  __init__.py
  legenda_yt.py   # json3 → list[Palavra] (puro) + baixar (executor injetável)
  estado.py       # ErroProducao, Etapa, EstadoEpisodio, transições (puro) + ler/gravar
  etapas.py       # Dependencias + rodar_etapa(video|legenda|sinais|momentos)
  fila.py         # Fila: uma thread, pausa em ErroLLM, recuperação na subida
  curadoria.py    # aprovar/rejeitar candidato → exemplos do nicho + curadoria.json
  rotas.py        # API da Produção, montada pelo servidor do painel
src/cortes/painel/servidor.py   # monta as rotas da Produção e o lifespan da fila
web/static/
  index.html  painel.css  js/base.js  js/inicio.js       # navegação em grupos + fila no trilho
  js/episodios.js  js/episodio.js                         # telas novas
tests/
  test_producao_legenda.py  test_producao_estado.py  test_producao_etapas.py
  test_producao_fila.py     test_producao_curadoria.py  test_producao_rotas.py
```

Comando de check (do `CLAUDE.md` do repo), rodar ao fim de cada tarefa:

```
.venv/Scripts/python -m ruff check src tests
.venv/Scripts/python -m mypy src
.venv/Scripts/python -m pytest -q
```

Commits: stage só os arquivos da tarefa, por caminho (há pastas não rastreadas no repo:
`pesquisa/`, `testes/`, `biblioteca/`). Mensagem termina com
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

---

### Task 1: Legenda do YouTube → palavras (puro)

**Files:**
- Create: `src/cortes/producao/__init__.py`, `src/cortes/producao/legenda_yt.py`
- Test: `tests/test_producao_legenda.py`

- [ ] **Step 1: `src/cortes/producao/__init__.py`**

```python
"""Produção no painel: do link do episódio aos candidatos e Shorts (spec produção)."""
```

- [ ] **Step 2: Escrever os testes**

```python
import pytest

from cortes.producao.legenda_yt import FIM_MAX_S, ErroLegenda, palavras_do_json3
from cortes.tipos import Palavra

AUTO = {"events": [
    {"tStartMs": 0, "dDurationMs": 6000, "segs": [{"utf8": "[música]"}]},
    {"tStartMs": 22000, "dDurationMs": 4000, "wWinId": 1, "segs": [
        {"utf8": "Está", "acAsrConf": 0}, {"utf8": " começando", "tOffsetMs": 199},
        {"utf8": " o", "tOffsetMs": 519}, {"utf8": " Primocast,", "tOffsetMs": 600}]},
    {"tStartMs": 24000, "wWinId": 1, "aAppend": 1, "segs": [{"utf8": "\n"}]},
    {"tStartMs": 24160, "dDurationMs": 3000, "segs": [
        {"utf8": "grupo"}, {"utf8": " Primo.", "tOffsetMs": 320}]},
]}
MANUAL = {"events": [
    {"tStartMs": 1000, "dDurationMs": 2000, "segs": [{"utf8": "Bom dia a todos"}]},
    {"tStartMs": 3500, "dDurationMs": 1000, "segs": [{"utf8": "[aplausos e risos] Obrigado."}]},
]}


def test_legenda_automatica_usa_offset_por_palavra() -> None:
    ps = palavras_do_json3(AUTO)
    assert [p.texto for p in ps] == ["Está", "começando", "o", "Primocast,", "grupo", "Primo."]
    assert ps[0] == Palavra("Está", 22.0, 22.199)
    assert ps[1].fim == pytest.approx(22.519)                  # fim = início da seguinte
    assert ps[3].inicio == 22.6 and ps[3].fim == pytest.approx(22.6 + FIM_MAX_S)  # 24.16 passa do limite
    assert ps[5].inicio == pytest.approx(24.48) and ps[5].fim == pytest.approx(24.48 + FIM_MAX_S)


def test_marcas_entre_colchetes_somem() -> None:
    assert all("[" not in p.texto for p in palavras_do_json3(AUTO) + palavras_do_json3(MANUAL))


def test_legenda_manual_distribui_a_linha_pelo_tamanho_das_palavras() -> None:
    ps = palavras_do_json3(MANUAL)
    assert [p.texto for p in ps] == ["Bom", "dia", "a", "todos", "Obrigado."]
    assert ps[0].inicio == 1.0 and ps[3].inicio > ps[2].inicio > ps[1].inicio > 1.0
    assert ps[3].inicio < 3.0                                   # dentro do evento
    assert ps[4].inicio == 3.5


def test_pausa_longa_nao_estica_a_palavra() -> None:
    dados = {"events": [{"tStartMs": 0, "dDurationMs": 500, "segs": [{"utf8": "a"}]},
                        {"tStartMs": 9000, "dDurationMs": 500, "segs": [{"utf8": "b"}]}]}
    assert palavras_do_json3(dados)[0].fim == FIM_MAX_S


def test_sem_palavras_e_erro() -> None:
    with pytest.raises(ErroLegenda, match="sem palavras"):
        palavras_do_json3({"events": [{"tStartMs": 0, "segs": [{"utf8": "[música]"}]}]})


def test_json_fora_do_formato_e_erro() -> None:
    with pytest.raises(ErroLegenda, match="formato"):
        palavras_do_json3({"eventos": []})
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_producao_legenda.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cortes.producao.legenda_yt'`

- [ ] **Step 4: Implementar `src/cortes/producao/legenda_yt.py`** (só a parte pura nesta tarefa)

```python
"""Legenda do YouTube (json3) → palavras com tempo, sem Whisper (spec produção §4.2).

Automática: um segmento por palavra, com tOffsetMs. Manual: a linha inteira num segmento só —
o tempo é distribuído pelas palavras na proporção do tamanho. O json3 não traz o fim de cada
palavra: fim = início da seguinte, limitado a FIM_MAX_S (uma pausa longa não estica a palavra).
"""
import re
from typing import Any

from cortes.tipos import Palavra

FIM_MAX_S = 1.5
_MARCA = re.compile(r"\[[^\]]*\]")


class ErroLegenda(RuntimeError):
    pass


def _inicios_do_evento(ev: dict[str, Any]) -> list[tuple[str, float]]:
    t0 = ev["tStartMs"] / 1000
    fim_ev = t0 + ev.get("dDurationMs", 0) / 1000
    segs = [s for s in ev["segs"] if _MARCA.sub(" ", s.get("utf8", "")).strip()]
    saida: list[tuple[str, float]] = []
    for k, seg in enumerate(segs):
        ini = t0 + seg.get("tOffsetMs", 0) / 1000
        fim = t0 + segs[k + 1].get("tOffsetMs", 0) / 1000 if k + 1 < len(segs) else max(fim_ev, ini)
        palavras = _MARCA.sub(" ", seg["utf8"]).split()
        total = sum(len(w) for w in palavras)
        acumulado = 0
        for w in palavras:
            saida.append((w, ini + (fim - ini) * acumulado / total))
            acumulado += len(w)
    return saida


def palavras_do_json3(dados: dict[str, Any]) -> list[Palavra]:
    eventos = dados.get("events")
    if not isinstance(eventos, list):
        raise ErroLegenda("legenda do YouTube fora do formato json3 (sem 'events')")
    inicios = [par for ev in eventos if "segs" in ev for par in _inicios_do_evento(ev)]
    if not inicios:
        raise ErroLegenda("legenda do YouTube sem palavras")
    inicios.sort(key=lambda par: par[1])
    palavras: list[Palavra] = []
    for i, (texto, ini) in enumerate(inicios):
        seguinte = inicios[i + 1][1] if i + 1 < len(inicios) else ini + FIM_MAX_S
        palavras.append(Palavra(texto, round(ini, 3), round(min(seguinte, ini + FIM_MAX_S), 3)))
    return palavras
```

- [ ] **Step 5: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_producao_legenda.py -q`
Expected: `6 passed`. Se um valor de float divergir por arredondamento (ex.: `22.199`), ajuste o
teste para `pytest.approx` — nunca o código para "bater" com o teste.

- [ ] **Step 6: Check e commit**

```bash
git add src/cortes/producao/__init__.py src/cortes/producao/legenda_yt.py tests/test_producao_legenda.py
git commit -m "feat: legenda do YouTube vira palavras com tempo, sem Whisper"
```

---

### Task 2: Baixar a legenda (fino, executor injetável)

**Files:**
- Modify: `src/cortes/producao/legenda_yt.py`
- Test: `tests/test_producao_legenda.py` (acrescentar)

- [ ] **Step 1: Acrescentar os testes**

```python
import subprocess  # noqa: E402  (mover para o topo do arquivo junto dos outros imports)
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

from cortes.producao.legenda_yt import ARQUIVO, baixar, comando  # noqa: E402


def test_comando_pede_so_pt_em_json3(tmp_path: Path) -> None:
    cmd = comando("https://youtu.be/abcdefghijk", tmp_path)
    assert cmd[:3] == [sys.executable, "-m", "yt_dlp"]
    assert "--skip-download" in cmd and "--write-subs" in cmd and "--write-auto-subs" in cmd
    assert cmd[cmd.index("--sub-langs") + 1] == "pt"
    assert cmd[cmd.index("--sub-format") + 1] == "json3"


def executor(retorno: int, stderr: str = "", criar: bool = True):  # type: ignore[no-untyped-def]
    def rodar(args: list[str]) -> subprocess.CompletedProcess[str]:
        destino = Path(args[args.index("-o") + 1]).parent
        if criar:
            (destino / ARQUIVO).write_text('{"events": []}', encoding="utf-8")
        return subprocess.CompletedProcess(args, retorno, "", stderr)
    return rodar


def test_baixar_devolve_o_arquivo(tmp_path: Path) -> None:
    assert baixar("https://youtu.be/abcdefghijk", tmp_path, executor(0)) == tmp_path / ARQUIVO


def test_sem_legenda_pt_para_com_mensagem(tmp_path: Path) -> None:
    with pytest.raises(ErroLegenda, match="sem legenda em português"):
        baixar("https://youtu.be/abcdefghijk", tmp_path, executor(0, criar=False))


def test_429_para_sem_repetir(tmp_path: Path) -> None:
    with pytest.raises(ErroLegenda, match="limitou as requisições"):
        baixar("https://youtu.be/abcdefghijk", tmp_path,
               executor(1, "ERROR: Unable to download video subtitles for 'pt': HTTP Error 429: Too Many Requests", False))


def test_outro_erro_do_ytdlp_mostra_o_fim_do_stderr(tmp_path: Path) -> None:
    with pytest.raises(ErroLegenda, match="Video unavailable"):
        baixar("https://youtu.be/abcdefghijk", tmp_path, executor(1, "ERROR: Video unavailable", False))
```

(Mova esses imports para o topo do arquivo de teste; os `noqa` acima são só para leitura do plano.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_producao_legenda.py -q`
Expected: FAIL — `ImportError: cannot import name 'ARQUIVO'`

- [ ] **Step 3: Acrescentar a `src/cortes/producao/legenda_yt.py`**

Imports do topo passam a ser:

```python
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cortes.tipos import Palavra
```

E, depois de `class ErroLegenda`:

```python
Executor = Callable[[list[str]], subprocess.CompletedProcess[str]]
ARQUIVO = "legenda.pt.json3"


def comando(url: str, destino: Path) -> list[str]:
    """Só a faixa 'pt' original: pedir 'pt.*' traz a tradução 'pt-PT' e levou HTTP 429
    (conferido em 2026-10-02). Com --write-subs e --write-auto-subs, a manual tem preferência."""
    return [sys.executable, "-m", "yt_dlp", "--skip-download", "--write-subs", "--write-auto-subs",
            "--sub-langs", "pt", "--sub-format", "json3", "--no-progress",
            "-o", str(destino / "legenda.%(ext)s"), url]


def _rodar(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")


def baixar(url: str, destino: Path, executar: Executor = _rodar) -> Path:
    r = executar(comando(url, destino))
    if "HTTP Error 429" in r.stderr:
        raise ErroLegenda("YouTube limitou as requisições; tente em alguns minutos")
    if r.returncode != 0:
        raise ErroLegenda(f"yt-dlp falhou ao baixar a legenda: {r.stderr.strip()[-400:]}")
    arquivo = destino / ARQUIVO
    if not arquivo.exists():
        raise ErroLegenda("vídeo sem legenda em português no YouTube")
    return arquivo
```

Nota: o yt-dlp grava `legenda.pt.json3` a partir do template `legenda.%(ext)s` (a língua entra
antes da extensão). Confirme uma vez no Step 5 com um vídeo real; se o nome divergir, ajuste
`ARQUIVO` e registre aqui.

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_producao_legenda.py -q`
Expected: `11 passed`

- [ ] **Step 5: Conferir o nome do arquivo com o yt-dlp real (uma requisição)**

```bash
.venv/Scripts/python -c "from pathlib import Path; import tempfile; from cortes.producao.legenda_yt import baixar; d=Path(tempfile.mkdtemp()); print(baixar('https://www.youtube.com/watch?v=c5xqNNWFT9w', d)); print(sorted(p.name for p in d.iterdir()))"
```

Expected: imprime o caminho de `legenda.pt.json3` e a lista com esse arquivo. Se der 429, espere
alguns minutos e tente uma vez — não repita em loop.

- [ ] **Step 6: Check e commit**

```bash
git add src/cortes/producao/legenda_yt.py tests/test_producao_legenda.py
git commit -m "feat: baixa só a legenda pt do YouTube e para com mensagem clara em 429"
```

---

### Task 3: Estado do episódio

**Files:**
- Create: `src/cortes/producao/estado.py`
- Test: `tests/test_producao_estado.py`

- [ ] **Step 1: Escrever os testes**

```python
from datetime import datetime
from pathlib import Path

import pytest

from cortes.producao.estado import (
    ETAPAS,
    ErroProducao,
    concluido,
    etapa_com_erro,
    gravar,
    ler,
    marcar,
    novo,
    proxima,
    reabrir,
)

AGORA = datetime(2026, 10, 2, 9, 12)


def ep() -> object:
    return novo("c5xqNNWFT9w", "https://youtu.be/c5xqNNWFT9w", "financas", 5, "f7", AGORA)


def test_novo_comeca_tudo_pendente() -> None:
    e = ep()
    assert list(e.etapas) == list(ETAPAS) and proxima(e) == "video" and not concluido(e)


def test_avanca_pelas_etapas() -> None:
    e = ep()
    for nome in ETAPAS:
        assert proxima(e) == nome
        e = marcar(marcar(e, nome, "rodando", AGORA), nome, "ok", AGORA)
    assert concluido(e) and proxima(e) is None


def test_erro_para_a_fila_do_episodio() -> None:
    e = marcar(ep(), "video", "ok", AGORA)
    e = marcar(e, "legenda", "erro", AGORA, "vídeo sem legenda em português no YouTube")
    assert proxima(e) is None and etapa_com_erro(e) == "legenda"
    assert e.etapas["legenda"].erro == "vídeo sem legenda em português no YouTube"


def test_reabrir_volta_erro_e_rodando_para_pendente() -> None:
    e = marcar(marcar(ep(), "video", "rodando", AGORA), "video", "erro", AGORA, "falhou")
    e = reabrir(e)
    assert e.etapas["video"].situacao == "pendente" and e.etapas["video"].erro is None
    assert proxima(e) == "video"


def test_erro_exige_mensagem_e_ok_nao_aceita() -> None:
    with pytest.raises(ErroProducao, match="mensagem"):
        marcar(ep(), "video", "erro", AGORA)
    with pytest.raises(ErroProducao, match="só em erro"):
        marcar(ep(), "video", "ok", AGORA, "x")


def test_etapa_desconhecida() -> None:
    with pytest.raises(ErroProducao, match="etapa 'render'"):
        marcar(ep(), "render", "ok", AGORA)


def test_ida_e_volta_em_disco(tmp_path: Path) -> None:
    e = marcar(ep(), "video", "ok", AGORA)
    gravar(tmp_path, e)
    assert ler(tmp_path) == e


def test_estado_quebrado_diz_o_arquivo(tmp_path: Path) -> None:
    (tmp_path / "estado.json").write_text('{"id": "x"}', encoding="utf-8")
    with pytest.raises(ErroProducao, match="estado.json"):
        ler(tmp_path)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_producao_estado.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implementar `src/cortes/producao/estado.py`**

```python
"""Estado de um episódio na produção: etapas, situação e erro (spec produção §4.3–4.4).

Transições são puras e devolvem um estado novo; ler/gravar é o único I/O.
"""
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

from cortes.episodio import ler_json, salvar_json

ETAPAS = ("video", "legenda", "sinais", "momentos")
SITUACOES = ("pendente", "rodando", "ok", "erro")
Situacao = Literal["pendente", "rodando", "ok", "erro"]


class ErroProducao(ValueError):
    """Pedido ou dado inválido na produção. A mensagem diz o arquivo ou o campo."""


@dataclass(frozen=True)
class Etapa:
    situacao: Situacao = "pendente"
    erro: str | None = None
    atualizado_em: str | None = None


@dataclass(frozen=True)
class EstadoEpisodio:
    id: str
    url: str
    nicho: str
    n_shorts: int
    formato: str
    criado_em: str
    etapas: dict[str, Etapa]


def novo(id: str, url: str, nicho: str, n_shorts: int, formato: str, agora: datetime) -> EstadoEpisodio:
    return EstadoEpisodio(id, url, nicho, n_shorts, formato, agora.isoformat(timespec="seconds"),
                          {nome: Etapa() for nome in ETAPAS})


def marcar(e: EstadoEpisodio, etapa: str, situacao: Situacao, agora: datetime,
           erro: str | None = None) -> EstadoEpisodio:
    if etapa not in ETAPAS:
        raise ErroProducao(f"etapa '{etapa}' não existe; use uma de {ETAPAS}")
    if situacao == "erro" and not erro:
        raise ErroProducao("etapa em erro precisa de mensagem")
    if situacao != "erro" and erro is not None:
        raise ErroProducao("mensagem de erro só em erro")
    nova = Etapa(situacao, erro, agora.isoformat(timespec="seconds"))
    return replace(e, etapas={**e.etapas, etapa: nova})


def etapa_com_erro(e: EstadoEpisodio) -> str | None:
    return next((n for n in ETAPAS if e.etapas[n].situacao == "erro"), None)


def proxima(e: EstadoEpisodio) -> str | None:
    """A primeira etapa não concluída; None se acabou ou se uma etapa está em erro."""
    if etapa_com_erro(e):
        return None
    return next((n for n in ETAPAS if e.etapas[n].situacao != "ok"), None)


def concluido(e: EstadoEpisodio) -> bool:
    return all(e.etapas[n].situacao == "ok" for n in ETAPAS)


def reabrir(e: EstadoEpisodio) -> EstadoEpisodio:
    """'Tentar de novo' e retomada após reinício: erro e rodando voltam a pendente."""
    etapas = {n: Etapa() if et.situacao in ("erro", "rodando") else et for n, et in e.etapas.items()}
    return replace(e, etapas=etapas)


def gravar(pasta: Path, e: EstadoEpisodio) -> None:
    salvar_json(pasta / "estado.json", asdict(e))


def _etapa(d: Any) -> Etapa:
    if d["situacao"] not in SITUACOES:
        raise ValueError(f"situação '{d['situacao']}'")
    return Etapa(cast(Situacao, d["situacao"]), d["erro"], d["atualizado_em"])


def ler(pasta: Path) -> EstadoEpisodio:
    arquivo = pasta / "estado.json"
    try:
        d = ler_json(arquivo)
        etapas = {n: _etapa(d["etapas"][n]) for n in ETAPAS}
        return EstadoEpisodio(str(d["id"]), str(d["url"]), str(d["nicho"]), int(d["n_shorts"]),
                              str(d["formato"]), str(d["criado_em"]), etapas)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as ex:
        raise ErroProducao(f"{arquivo}: estado inválido ({ex!r})") from ex
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_producao_estado.py -q`
Expected: `8 passed`

- [ ] **Step 5: Check e commit**

```bash
git add src/cortes/producao/estado.py tests/test_producao_estado.py
git commit -m "feat: estado do episódio na produção com etapas e erro"
```

---

### Task 4: Etapas do episódio

**Files:**
- Create: `src/cortes/producao/etapas.py`
- Test: `tests/test_producao_etapas.py`

- [ ] **Step 1: Escrever os testes** (dependências falsas; nada de rede, GPU ou `claude`)

```python
import json
import wave
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from cortes.producao.estado import novo
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
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
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
    from cortes.producao.estado import ErroProducao
    e = novo("abcdefghijk", "u", "financas", 5, "f7", AGORA)
    with pytest.raises(ErroProducao, match="render"):
        rodar_etapa("render", tmp_path, e, tmp_path, Falsas().dep())
```

(Remova o `asdict` não usado do import se o ruff acusar; o helper `asdict_palavra` cobre o caso.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_producao_etapas.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implementar `src/cortes/producao/etapas.py`**

```python
"""As 4 etapas do episódio no painel: vídeo, legenda do YouTube, sinais, momentos.

Cada etapa grava seu arquivo e pula se ele já existe (mesmo padrão do `cortes detectar`).
O `cortes detectar` do terminal segue com Whisper; aqui a transcrição é a legenda do YouTube.
"""
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from cortes import ingestao, sinais
from cortes.detector import ChamarLLM, detectar
from cortes.detector import _chamar_real as _llm_real
from cortes.episodio import ler_json, salvar_json
from cortes.perfil import carregar_perfil
from cortes.producao import legenda_yt
from cortes.producao.estado import ETAPAS, ErroProducao, EstadoEpisodio
from cortes.segmentacao import frases
from cortes.tipos import Palavra


@dataclass(frozen=True)
class Dependencias:
    baixar_video: Callable[[str, Path], None] = ingestao.baixar
    extrair_audio: Callable[[Path], None] = ingestao.extrair_audio
    baixar_legenda: Callable[[str, Path], Path] = legenda_yt.baixar
    chamar_llm: ChamarLLM = _llm_real
    modelo: str = "sonnet"


def _video(pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    if not (pasta / "video.mp4").exists():
        dep.baixar_video(e.url, pasta)
    if not (pasta / "audio.wav").exists():
        dep.extrair_audio(pasta)


def _legenda(pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    if (pasta / "palavras.json").exists():
        return
    arquivo = dep.baixar_legenda(e.url, pasta)
    palavras = legenda_yt.palavras_do_json3(ler_json(arquivo))
    salvar_json(pasta / "palavras.json", [asdict(p) for p in palavras])


def _sinais(pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    if (pasta / "sinais.json").exists():
        return
    energia = sinais.energia_por_janela(sinais.ler_wav_mono(pasta / "audio.wav"))
    salvar_json(pasta / "sinais.json", {"janela_s": sinais.JANELA_S, "energia": energia})


def _momentos(pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    if (pasta / "candidatos.json").exists():
        return
    nicho = raiz / "nichos" / e.nicho
    if not (nicho / "perfil.yaml").exists():
        raise ErroProducao(f"nicho '{e.nicho}' não existe: falta {nicho / 'perfil.yaml'}")
    fs = frases([Palavra(**p) for p in ler_json(pasta / "palavras.json")])
    salvar_json(pasta / "frases.json", [asdict(f) for f in fs])
    aceitos, descartes = detectar(fs, ler_json(pasta / "sinais.json")["energia"], carregar_perfil(nicho),
                                  dep.modelo, dep.chamar_llm)
    salvar_json(pasta / "descartados.json", descartes)
    salvar_json(pasta / "candidatos.json", [asdict(c) for c in aceitos])


_ETAPAS = {"video": _video, "legenda": _legenda, "sinais": _sinais, "momentos": _momentos}
assert tuple(_ETAPAS) == ETAPAS


def rodar_etapa(nome: str, pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    if nome not in _ETAPAS:
        raise ErroProducao(f"etapa '{nome}' não existe; use uma de {ETAPAS}")
    _ETAPAS[nome](pasta, e, raiz, dep)
```

Notas:
- `candidatos.json` é gravado por último: ele é o marcador de "etapa feita" (se o processo cair
  entre os dois `salvar_json`, a etapa roda de novo inteira).
- Importar `_chamar_real` (privado) do detector: em vez disso, se preferir, torne-o público em
  `cortes/detector/__init__.py` como `chamar_llm_real` e atualize o default de `detectar` —
  registre a escolha no commit. Não duplique a função.
- O `assert` de módulo garante que as etapas do estado e das funções não divergem; se o ruff ou
  o mypy reclamarem, troque por um teste equivalente.

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_producao_etapas.py -q`
Expected: `4 passed`. Se `energia_por_janela` exigir áudio mais longo que 4 s, aumente
`wav_silencio(..., segundos=10)`.

- [ ] **Step 5: Check e commit**

```bash
git add src/cortes/producao/etapas.py tests/test_producao_etapas.py
git commit -m "feat: etapas da produção com legenda do YouTube no lugar do Whisper"
```

---

### Task 5: Fila de trabalhos

**Files:**
- Create: `src/cortes/producao/fila.py`
- Test: `tests/test_producao_fila.py`

- [ ] **Step 1: Escrever os testes** (síncronos: chamam `processar` direto, sem thread)

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_producao_fila.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implementar `src/cortes/producao/fila.py`**

```python
"""Fila única da produção: uma thread, um episódio e uma etapa por vez (spec produção §4.4).

GPU, cota do Claude e CPU do render são recursos únicos — por isso nada roda em paralelo.
Erro numa etapa fica no estado.json do episódio e a fila segue com o próximo; erro do LLM
(ex.: limite de uso da assinatura) PAUSA a fila até Davi retomar.
"""
import threading
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from cortes.llm import ErroLLM
from cortes.producao.estado import EstadoEpisodio, concluido, etapa_com_erro, gravar, ler, marcar, proxima, reabrir

RodarEtapa = Callable[[str, Path, EstadoEpisodio], None]


class Fila:
    def __init__(self, raiz: Path, rodar: RodarEtapa, agora: Callable[[], datetime] = datetime.now) -> None:
        self._raiz = raiz
        self._rodar = rodar
        self._agora = agora
        self._trava = threading.Lock()
        self._tem_trabalho = threading.Condition(self._trava)
        self._ids: list[str] = []
        self._atual: dict[str, str] | None = None
        self._pausada: str | None = None
        self._fio: threading.Thread | None = None

    def _pasta(self, id: str) -> Path:
        return self._raiz / "episodios" / id

    def enfileirar(self, id: str) -> None:
        with self._tem_trabalho:
            if id not in self._ids:
                self._ids.append(id)
            self._tem_trabalho.notify()

    def retomar(self) -> None:
        with self._tem_trabalho:
            self._pausada = None
            self._tem_trabalho.notify()

    def situacao(self) -> dict[str, Any]:
        with self._trava:
            return {"atual": self._atual, "na_fila": list(self._ids), "pausada": self._pausada}

    def recuperar(self) -> None:
        """Na subida: o que ficou 'rodando' volta a pendente e entra na fila."""
        for arquivo in sorted(self._raiz.glob("episodios/*/estado.json")):
            e = ler(arquivo.parent)
            if concluido(e) or etapa_com_erro(e):
                continue
            gravar(arquivo.parent, reabrir(e))
            self.enfileirar(e.id)

    def processar(self, id: str) -> None:
        """Roda as etapas pendentes de um episódio até acabar ou falhar. Síncrono (testável)."""
        pasta = self._pasta(id)
        while (etapa := proxima(e := ler(pasta))) is not None:
            with self._trava:
                self._atual = {"episodio": id, "etapa": etapa}
            gravar(pasta, marcar(e, etapa, "rodando", self._agora()))
            try:
                self._rodar(etapa, pasta, e)
            except ErroLLM as ex:
                gravar(pasta, marcar(ler(pasta), etapa, "erro", self._agora(), str(ex)))
                with self._trava:
                    self._pausada = f"fila pausada: {ex}"
                break
            except Exception as ex:   # qualquer falha da etapa fica visível no episódio
                traceback.print_exc()
                gravar(pasta, marcar(ler(pasta), etapa, "erro", self._agora(), f"{type(ex).__name__}: {ex}"))
                break
            gravar(pasta, marcar(ler(pasta), etapa, "ok", self._agora()))
        with self._trava:
            self._atual = None

    def _laco(self) -> None:
        while True:
            with self._tem_trabalho:
                while not self._ids or self._pausada:
                    self._tem_trabalho.wait()
                id = self._ids[0]
            try:
                self.processar(id)
            finally:
                with self._trava:
                    self._ids.remove(id)

    def iniciar(self) -> None:
        self.recuperar()
        self._fio = threading.Thread(target=self._laco, daemon=True, name="fila-producao")
        self._fio.start()
```

Nota: o episódio sai da lista depois de processado (mesmo com erro); "tentar de novo" reabre o
estado e enfileira de novo. `except Exception` é deliberado: a thread da fila não pode morrer
por uma etapa, e a falha fica gravada no estado com tipo e mensagem, e o traceback vai para o
terminal do servidor.

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_producao_fila.py -q`
Expected: `5 passed`

- [ ] **Step 5: Check e commit**

```bash
git add src/cortes/producao/fila.py tests/test_producao_fila.py
git commit -m "feat: fila única da produção com pausa em erro do LLM e retomada na subida"
```

---

### Task 6: Curadoria — aprovar e rejeitar candidatos

**Files:**
- Create: `src/cortes/producao/curadoria.py`
- Test: `tests/test_producao_curadoria.py`

- [ ] **Step 1: Escrever os testes**

```python
import json
from pathlib import Path

import pytest

from cortes.producao.curadoria import MOTIVOS, decidir, decisoes, texto_do_trecho
from cortes.producao.estado import ErroProducao
from cortes.tipos import Palavra

CAND = {"frase_inicio": 0, "frase_fim": 1, "inicio": 10.0, "fim": 12.0, "notas": {}, "bonus": ["humor"],
        "penalidades": [], "justificativa": "j", "titulo": "Ganhei dez mil", "nota_final": 80.0}


def montar(tmp: Path) -> tuple[Path, Path]:
    raiz = tmp
    ex = raiz / "nichos" / "financas" / "exemplos"
    ex.mkdir(parents=True)
    for a in ("bons.jsonl", "ruins.jsonl"):
        (ex / a).write_text("", encoding="utf-8")
    pasta = raiz / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    (pasta / "candidatos.json").write_text(json.dumps([CAND]), encoding="utf-8")
    palavras = [{"texto": t, "inicio": i, "fim": i + 0.5} for t, i in
                [("antes", 9.0), ("Eu", 10.0), ("ganhei", 10.5), ("dez", 11.0), ("mil.", 11.5), ("depois", 12.5)]]
    (pasta / "palavras.json").write_text(json.dumps(palavras), encoding="utf-8")
    return raiz, pasta


def test_texto_do_trecho() -> None:
    ps = [Palavra("a", 0, 1), Palavra("b", 1, 2), Palavra("c", 2, 3)]
    assert texto_do_trecho(ps, 1.0, 2.0) == "b"


def test_aprovar_grava_exemplo_bom(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    decidir(pasta, raiz, "financas", 0, "aprovado", None)
    bons = (raiz / "nichos/financas/exemplos/bons.jsonl").read_text(encoding="utf-8").splitlines()
    ex = json.loads(bons[0])
    assert ex["texto"] == "Eu ganhei dez mil." and ex["titulo"] == "Ganhei dez mil" and ex["episodio"] == "abcdefghijk"
    assert decisoes(pasta) == {0: {"decisao": "aprovado", "motivo": None}}


def test_rejeitar_exige_motivo_e_grava_exemplo_ruim(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    with pytest.raises(ErroProducao, match="motivo"):
        decidir(pasta, raiz, "financas", 0, "rejeitado", " ")
    decidir(pasta, raiz, "financas", 0, "rejeitado", f"{MOTIVOS[0]}: começa no 'e aí'")
    ruins = (raiz / "nichos/financas/exemplos/ruins.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(ruins[0])["motivo"].startswith(MOTIVOS[0])


def test_decisao_e_definitiva(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    decidir(pasta, raiz, "financas", 0, "aprovado", None)
    with pytest.raises(ErroProducao, match="já decidido"):
        decidir(pasta, raiz, "financas", 0, "rejeitado", "outro")


def test_indice_invalido(tmp_path: Path) -> None:
    raiz, pasta = montar(tmp_path)
    with pytest.raises(ErroProducao, match="candidato 5"):
        decidir(pasta, raiz, "financas", 5, "aprovado", None)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_producao_curadoria.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implementar `src/cortes/producao/curadoria.py`**

```python
"""Aprovar ou rejeitar um candidato vira exemplo para o detector (spec produção §4.5).

O exemplo vai para nichos/<nicho>/exemplos/{bons,ruins}.jsonl — o mesmo arquivo que o perfil
lê e o prompt do detector injeta. A decisão fica também em episodios/<id>/curadoria.json para
a tela mostrar. Decisão é definitiva: desfazer exigiria apagar linha do jsonl.
"""
import json
from pathlib import Path
from typing import Any, Literal

from cortes.episodio import ler_json, salvar_json
from cortes.producao.estado import ErroProducao
from cortes.tipos import Palavra

Decisao = Literal["aprovado", "rejeitado"]
MOTIVOS = ("começa no meio", "sem gancho", "não fecha", "fora do tema", "pouco espanto", "outro")


def texto_do_trecho(palavras: list[Palavra], inicio: float, fim: float) -> str:
    return " ".join(p.texto for p in palavras if inicio <= p.inicio < fim)


def decisoes(pasta: Path) -> dict[int, dict[str, Any]]:
    arquivo = pasta / "curadoria.json"
    if not arquivo.exists():
        return {}
    return {int(k): v for k, v in ler_json(arquivo).items()}


def decidir(pasta: Path, raiz: Path, nicho: str, indice: int, decisao: Decisao, motivo: str | None) -> None:
    candidatos = ler_json(pasta / "candidatos.json")
    if not 0 <= indice < len(candidatos):
        raise ErroProducao(f"candidato {indice} não existe ({len(candidatos)} candidatos)")
    if decisao == "rejeitado" and not (motivo and motivo.strip()):
        raise ErroProducao("rejeitar exige motivo")
    if decisao == "aprovado" and motivo is not None:
        raise ErroProducao("aprovar não leva motivo")
    feitas = decisoes(pasta)
    if indice in feitas:
        raise ErroProducao(f"candidato {indice} já decidido: {feitas[indice]['decisao']}")
    c = candidatos[indice]
    palavras = [Palavra(**p) for p in ler_json(pasta / "palavras.json")]
    exemplo = {"episodio": pasta.name, "inicio": c["inicio"], "fim": c["fim"], "titulo": c["titulo"],
               "texto": texto_do_trecho(palavras, c["inicio"], c["fim"])}
    if motivo is not None:
        exemplo["motivo"] = motivo.strip()
    destino = raiz / "nichos" / nicho / "exemplos" / ("bons.jsonl" if decisao == "aprovado" else "ruins.jsonl")
    if not destino.exists():
        raise ErroProducao(f"arquivo de exemplos não existe: {destino}")
    with destino.open("a", encoding="utf-8") as f:
        f.write(json.dumps(exemplo, ensure_ascii=False) + "\n")
    salvar_json(pasta / "curadoria.json",
                {str(k): v for k, v in {**feitas, indice: {"decisao": decisao, "motivo": exemplo.get("motivo")}}.items()})
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_producao_curadoria.py -q`
Expected: `5 passed`

- [ ] **Step 5: Check e commit**

```bash
git add src/cortes/producao/curadoria.py tests/test_producao_curadoria.py
git commit -m "feat: aprovar e rejeitar candidato vira exemplo do detector"
```

---

### Task 7: API da Produção no servidor

**Files:**
- Create: `src/cortes/producao/rotas.py`
- Modify: `src/cortes/painel/servidor.py`
- Test: `tests/test_producao_rotas.py`

- [ ] **Step 1: Escrever os testes**

```python
import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cortes.producao.estado import EstadoEpisodio, gravar, ler, marcar, novo
from cortes.producao.fila import Fila
from cortes.painel.servidor import Config, criar_app

# Reaproveite a fixture `cfg` de tests/test_painel_servidor.py: copie a função de montagem
# (nicho financas, contas.yaml, formatos.yaml, web/static com index.html, skill falsa,
# monkeypatch de shutil.which) para um helper local `montar_cfg(tmp_path, monkeypatch)`.
from tests.test_painel_servidor import cfg as _cfg_fixture  # noqa: F401  (ver nota abaixo)

AGORA = datetime(2026, 10, 2, 9)
CAND = {"frase_inicio": 0, "frase_fim": 1, "inicio": 10.0, "fim": 40.0,
        "notas": {"gancho_3s": 5, "autocontido": 4, "espanto": 4, "historia_ou_virada": 3, "fechamento": 4},
        "bonus": ["humor"], "penalidades": [], "justificativa": "abre com número", "titulo": "Ganhei dez mil",
        "nota_final": 87.5}


def cliente(cfg: Config, rodar=None) -> tuple[TestClient, Fila]:  # type: ignore[no-untyped-def]
    fila = Fila(cfg.raiz, rodar or (lambda n, p, e: None), lambda: AGORA)
    app = criar_app(cfg, executar=lambda a, c: "", abrir=lambda a, c: None, fila=fila)
    return TestClient(app, base_url="http://127.0.0.1"), fila


def test_novo_episodio_entra_na_fila(cfg: Config) -> None:
    c, fila = cliente(cfg)
    r = c.post("/api/episodios", json={"link": "https://www.youtube.com/watch?v=abcdefghijk",
                                       "nicho": "financas", "n_shorts": 5, "formato": "f7"})
    assert r.status_code == 201 and r.json() == {"id": "abcdefghijk"}
    assert fila.situacao()["na_fila"] == ["abcdefghijk"]
    assert ler(cfg.raiz / "episodios" / "abcdefghijk").nicho == "financas"


@pytest.mark.parametrize("corpo, erro", [
    ({"link": "https://www.youtube.com/@canal", "nicho": "financas", "n_shorts": 5, "formato": "f7"}, "sem id"),
    ({"link": "https://youtu.be/abcdefghijk", "nicho": "humor", "n_shorts": 5, "formato": "f7"}, "nicho 'humor'"),
    ({"link": "https://youtu.be/abcdefghijk", "nicho": "financas", "n_shorts": 5, "formato": "f4"}, "formato 'f4'"),
    ({"link": "https://youtu.be/abcdefghijk", "nicho": "financas", "n_shorts": 0, "formato": "f7"}, "n_shorts"),
])
def test_novo_episodio_recusado(cfg: Config, corpo: dict[str, object], erro: str) -> None:
    c, fila = cliente(cfg)
    r = c.post("/api/episodios", json=corpo)
    assert r.status_code == 422 and erro in json.dumps(r.json(), ensure_ascii=False)
    assert fila.situacao()["na_fila"] == []


def test_episodio_repetido_recusado(cfg: Config) -> None:
    c, _ = cliente(cfg)
    corpo = {"link": "https://youtu.be/abcdefghijk", "nicho": "financas", "n_shorts": 5, "formato": "f7"}
    c.post("/api/episodios", json=corpo)
    r = c.post("/api/episodios", json=corpo)
    assert r.status_code == 422 and "já está na produção" in r.json()["detail"]


def preparar_concluido(cfg: Config) -> Path:
    pasta = cfg.raiz / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    e = novo("abcdefghijk", "https://youtu.be/abcdefghijk", "financas", 5, "f7", AGORA)
    for n in e.etapas:
        e = marcar(e, n, "ok", AGORA)
    gravar(pasta, e)
    (pasta / "meta.json").write_text(json.dumps({"titulo": "Ep", "canal": "PrimoCast", "duracao_s": 600,
                                                  "data": "20260929", "id": "abcdefghijk"}), encoding="utf-8")
    (pasta / "candidatos.json").write_text(json.dumps([CAND]), encoding="utf-8")
    (pasta / "palavras.json").write_text(json.dumps([{"texto": "Eu", "inicio": 10.0, "fim": 10.5}]), encoding="utf-8")
    (pasta / "video.mp4").write_bytes(b"0123456789" * 100)
    return pasta


def test_lista_e_detalhe(cfg: Config) -> None:
    preparar_concluido(cfg)
    c, _ = cliente(cfg)
    p = c.get("/api/producao").json()
    assert p["episodios"][0]["id"] == "abcdefghijk" and p["episodios"][0]["titulo"] == "Ep"
    assert p["episodios"][0]["n_candidatos"] == 1 and p["fila"]["pausada"] is None
    d = c.get("/api/episodios/abcdefghijk").json()
    assert d["candidatos"][0]["titulo"] == "Ganhei dez mil" and d["candidatos"][0]["decisao"] is None
    assert d["rubrica"] == ["gancho_3s", "autocontido", "espanto", "historia_ou_virada", "fechamento"]


def test_video_atende_range(cfg: Config) -> None:
    preparar_concluido(cfg)
    c, _ = cliente(cfg)
    r = c.get("/api/episodios/abcdefghijk/video", headers={"Range": "bytes=0-9"})
    assert r.status_code == 206 and r.content == b"0123456789"


def test_id_invalido_nao_vira_caminho(cfg: Config) -> None:
    c, _ = cliente(cfg)
    assert c.get("/api/episodios/..%2F..%2Fcontas").status_code in (404, 422)
    assert c.get("/api/episodios/naoexiste00").status_code == 422


def test_decisao(cfg: Config) -> None:
    preparar_concluido(cfg)
    c, _ = cliente(cfg)
    r = c.post("/api/episodios/abcdefghijk/candidatos/0/decisao", json={"decisao": "rejeitado", "motivo": "sem gancho"})
    assert r.status_code == 200
    assert c.get("/api/episodios/abcdefghijk").json()["candidatos"][0]["decisao"] == "rejeitado"


def test_tentar_de_novo_so_com_erro(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    c, fila = cliente(cfg)
    assert c.post("/api/episodios/abcdefghijk/tentar").status_code == 422
    gravar(pasta, marcar(ler(pasta), "momentos", "erro", AGORA, "falhou"))
    assert c.post("/api/episodios/abcdefghijk/tentar").status_code == 202
    assert fila.situacao()["na_fila"] == ["abcdefghijk"]
    assert ler(pasta).etapas["momentos"].situacao == "pendente"


def test_retomar_fila(cfg: Config) -> None:
    c, fila = cliente(cfg)
    assert c.post("/api/fila/retomar").status_code == 202
```

Nota sobre a fixture: importar uma fixture de outro módulo de teste é frágil. Faça assim:
mova o corpo da fixture `cfg` de `tests/test_painel_servidor.py` para `tests/conftest.py`
(fixture `cfg` com `monkeypatch`), apague-a de `test_painel_servidor.py` (os testes continuam
recebendo `cfg` pelo conftest) e remova a linha `from tests.test_painel_servidor import ...`
acima. Rode a suíte inteira para confirmar que nada do painel quebrou.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_producao_rotas.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cortes.producao.rotas'`

- [ ] **Step 3: Implementar `src/cortes/producao/rotas.py`**

```python
"""API da Produção (spec produção §5). Montada pelo servidor do painel: rotas finas sobre
estado, fila e curadoria."""
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from pydantic import BaseModel

from cortes.episodio import id_do_video, ler_json
from cortes.painel.dados import VIDEO_ID
from cortes.perfil import CRITERIOS
from cortes.producao import curadoria
from cortes.producao.estado import ErroProducao, etapa_com_erro, gravar, ler, novo, reabrir
from cortes.producao.fila import Fila

FORMATOS_RENDER = ("f7", "f1")   # planos D e E acrescentam f4 e f3
N_SHORTS_MAX = 10


class NovoEpisodio(BaseModel):
    link: str
    nicho: str
    n_shorts: int
    formato: str


class PedidoDecisao(BaseModel):
    decisao: Literal["aprovado", "rejeitado"]
    motivo: str | None = None   # obrigatório ao rejeitar (validado em curadoria.decidir)


def _pasta(raiz: Path, id: str) -> Path:
    if not VIDEO_ID.fullmatch(id):
        raise ErroProducao(f"id de episódio inválido: {id!r}")
    pasta = raiz / "episodios" / id
    if not (pasta / "estado.json").exists():
        raise ErroProducao(f"episódio {id} não está na produção")
    return pasta


def _resumo(pasta: Path) -> dict[str, Any]:
    e = ler(pasta)
    meta = ler_json(pasta / "meta.json") if (pasta / "meta.json").exists() else {}
    cands = ler_json(pasta / "candidatos.json") if (pasta / "candidatos.json").exists() else []
    return {**asdict(e), "titulo": meta.get("titulo"), "canal": meta.get("canal"),
            "duracao_s": meta.get("duracao_s"), "n_candidatos": len(cands)}


def _validar(raiz: Path, novo_ep: NovoEpisodio) -> str:
    try:
        id = id_do_video(novo_ep.link)
    except ValueError as ex:
        raise ErroProducao(str(ex)) from ex
    if not (raiz / "nichos" / novo_ep.nicho / "perfil.yaml").exists():
        raise ErroProducao(f"nicho '{novo_ep.nicho}' não existe em {raiz / 'nichos'}")
    if novo_ep.formato not in FORMATOS_RENDER:
        raise ErroProducao(f"formato '{novo_ep.formato}' ainda não renderiza; use um de {FORMATOS_RENDER}")
    if not 1 <= novo_ep.n_shorts <= N_SHORTS_MAX:
        raise ErroProducao(f"n_shorts deve ficar entre 1 e {N_SHORTS_MAX}")
    if (raiz / "episodios" / id / "estado.json").exists():
        raise ErroProducao(f"episódio {id} já está na produção")
    return id


def montar(app: FastAPI, raiz: Path, fila: Fila, agora: Any = datetime.now) -> None:
    @app.get("/api/producao")
    def api_producao() -> Any:
        pastas = [a.parent for a in raiz.glob("episodios/*/estado.json")]
        eps = sorted((_resumo(p) for p in pastas), key=lambda r: r["criado_em"], reverse=True)
        return jsonable_encoder({"fila": fila.situacao(), "episodios": eps, "formatos": FORMATOS_RENDER})

    @app.post("/api/episodios", status_code=201)
    def api_novo(pedido: NovoEpisodio) -> dict[str, str]:
        id = _validar(raiz, pedido)
        pasta = raiz / "episodios" / id
        pasta.mkdir(parents=True, exist_ok=True)
        gravar(pasta, novo(id, f"https://www.youtube.com/watch?v={id}", pedido.nicho,
                           pedido.n_shorts, pedido.formato, agora()))
        fila.enfileirar(id)
        return {"id": id}

    @app.get("/api/episodios/{id}")
    def api_episodio(id: str) -> Any:
        pasta = _pasta(raiz, id)
        feitas = curadoria.decisoes(pasta)
        cands = ler_json(pasta / "candidatos.json") if (pasta / "candidatos.json").exists() else []
        return jsonable_encoder({**_resumo(pasta), "rubrica": list(CRITERIOS), "motivos": curadoria.MOTIVOS,
                                 "candidatos": [{**c, "indice": i, "decisao": feitas.get(i, {}).get("decisao")}
                                                for i, c in enumerate(cands)]})

    @app.get("/api/episodios/{id}/video")
    def api_video(id: str) -> FileResponse:
        video = _pasta(raiz, id) / "video.mp4"
        if not video.exists():
            raise ErroProducao(f"episódio {id} ainda sem vídeo")
        return FileResponse(video, media_type="video/mp4")

    @app.post("/api/episodios/{id}/tentar", status_code=202)
    def api_tentar(id: str) -> dict[str, bool]:
        pasta = _pasta(raiz, id)
        e = ler(pasta)
        if etapa_com_erro(e) is None:
            raise ErroProducao(f"episódio {id} não tem etapa com erro")
        gravar(pasta, reabrir(e))
        fila.enfileirar(id)
        return {"enfileirado": True}

    @app.post("/api/episodios/{id}/candidatos/{indice}/decisao")
    def api_decisao(id: str, indice: int, pedido: PedidoDecisao) -> dict[str, bool]:
        pasta = _pasta(raiz, id)
        curadoria.decidir(pasta, raiz, ler(pasta).nicho, indice, pedido.decisao, pedido.motivo)
        return {"ok": True}

    @app.post("/api/fila/retomar", status_code=202)
    def api_retomar() -> dict[str, bool]:
        fila.retomar()
        return {"retomada": True}
```

Notas:
- `CRITERIOS` existe em `cortes/perfil.py` (ordem da rubrica). Confirme o nome antes.
- A decisão de curadoria escreve em `nichos/<nicho>/exemplos/*.jsonl`: segure a trava de
  escrita do servidor (`escrita`) em volta dela — passe a trava para `montar` (parâmetro
  `escrita: threading.Lock`) e use `with escrita:` em `api_decisao` e `api_novo`.
- Se `montar` passar de 50 linhas, divida em `_rotas_leitura`/`_rotas_acao` como no servidor.

- [ ] **Step 4: Ligar no servidor (`src/cortes/painel/servidor.py`)**

1. Imports:
   ```python
   from contextlib import asynccontextmanager
   from collections.abc import AsyncIterator
   from cortes.producao import rotas as rotas_producao
   from cortes.producao.estado import ErroProducao
   from cortes.producao.etapas import Dependencias, rodar_etapa
   from cortes.producao.fila import Fila
   ```
2. Assinatura: `criar_app(cfg, executar=..., abrir=..., agora=..., fila: Fila | None = None)`.
3. No corpo, antes de criar o app:
   ```python
   if fila is None:
       dep = Dependencias()
       fila = Fila(cfg.raiz, lambda nome, pasta, e: rodar_etapa(nome, pasta, e, cfg.raiz, dep), agora)

   @asynccontextmanager
   async def ciclo(_: FastAPI) -> AsyncIterator[None]:
       fila.iniciar()   # só sob uvicorn (ou `with TestClient`): retoma o que estava rodando
       yield

   app = FastAPI(title="Painel de contas", lifespan=ciclo)
   ```
   Atenção: com `fila` injetada nos testes, o lifespan também chamaria `iniciar()` se o teste
   usasse `with TestClient(...)` — os testes desta tarefa não usam `with`, então a thread não sobe.
4. Handler para `ErroProducao` igual ao de `ErroPainel` (422 com `detail`).
5. Antes do `app.mount("/", StaticFiles...)`: `rotas_producao.montar(app, cfg.raiz, fila, agora)`
   (com a trava `escrita`, conforme a nota do Step 3).
6. `app.state.fila = fila`.

Mantenha `servidor.py` abaixo de 300 linhas.

- [ ] **Step 5: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_producao_rotas.py tests/test_painel_servidor.py -q`
Expected: todos passam (os 12 da produção + os do painel, inalterados).

- [ ] **Step 6: Check e commit**

```bash
git add src/cortes/producao/rotas.py src/cortes/painel/servidor.py tests/test_producao_rotas.py tests/conftest.py tests/test_painel_servidor.py
git commit -m "feat: API da produção no servidor do painel, com a fila subindo junto"
```

---

### Task 8: Navegação em grupos, fila no trilho e tela Episódios

**Files:**
- Modify: `web/static/index.html`, `web/static/painel.css`, `web/static/js/base.js`, `web/static/js/inicio.js`
- Create: `web/static/js/episodios.js`

Sem teste automatizado (JS puro): `node --check` em cada arquivo + verificação visual na Task 10.
**Leia os arquivos atuais antes** — o front mudou depois do plano do painel (token `meu`,
`.barra-mobile`, `esc()` em tudo, `trilho()`).

- [ ] **Step 1: `index.html`**
- Trilho em dois grupos (como o mockup): `<div class="grupo">Produção</div>` com
  `<a href="#episodios" data-tela="episodios">Episódios <span class="cont" id="cont-episodios" hidden></span></a>`,
  depois `<div class="grupo">Retorno</div>` com Contas, Shorts, Comparar.
- No rodapé do trilho, antes de `#trilho-contas`: `<div class="fila" id="fila-trilho" hidden></div>`.
- Barra do celular: acrescentar o link `Episódios` (mesmo padrão dos outros, compacto).
- Scripts: `js/episodios.js` e `js/episodio.js` antes de `js/inicio.js`.

- [ ] **Step 2: CSS** — copiar do mockup (`docs/superpowers/specs/2026-10-02-producao-mockup.html`)
as regras de `nav .grupo`, `.fila`, `.barra`, `.entrada`, `.episodios`, `.ep`, `.etapas`,
`.etapa` (com `.ok`, `.roda`, `.erro`), `.ep .resumo`, adaptando nomes que colidam com
classes existentes (confira `painel.css`; ex.: `.botao` já existe — não duplique). A barra da
etapa `rodando` usa animação de listras ou pulso (não há percentual por etapa no plano A);
respeite `prefers-reduced-motion`. Mobile ≤ 900 px: `.entrada` empilha, `.ep` vira
capa + título em cima e etapas embaixo; sem rolagem horizontal.

- [ ] **Step 3: `inicio.js`** — rota padrão passa a ser `episodios` (`TELAS[hash] ? hash : "episodios"`).

- [ ] **Step 4: `js/episodios.js`**

```js
"use strict";
// Tela Episódios: entrada do link, lista de episódios com as etapas, fila no trilho.
// O detalhe do episódio selecionado é desenhado por blocoEpisodio() (episodio.js).
let P = null;            // /api/producao
let epSel = null;        // id do episódio aberto
const NOMES_ETAPA = { video: "vídeo", legenda: "legenda", sinais: "sinais", momentos: "momentos" };

const temTrabalho = () => P && (P.fila.atual || P.fila.na_fila.length);

function htmlEntrada() {
  const nichos = (E?.nichos ?? []).map(n => `<option value="${esc(n)}">${esc(n)}</option>`).join("");
  const formatos = P.formatos.map(f => `<option value="${esc(f)}">${esc(f)} · ${esc(nomeFormato(f))}</option>`).join("");
  return `<form class="entrada" id="entrada">
    <label>Link do episódio<input class="link" name="link" required placeholder="https://www.youtube.com/watch?v=…"></label>
    <label>Nicho<select name="nicho">${nichos}</select></label>
    <label>Formato<select name="formato">${formatos}</select></label>
    <label>Shorts<select name="n_shorts"><option value="3">3 melhores</option><option value="5" selected>5 melhores</option><option value="10">10 melhores</option></select></label>
    <button class="botao primario">Gerar Shorts</button></form>`;
}

function htmlEtapas(ep) {
  return `<div class="etapas">${Object.entries(ep.etapas).map(([nome, et]) => {
    const cls = { ok: "ok", rodando: "roda", erro: "erro" }[et.situacao] ?? "";
    const rotulo = et.situacao === "erro" ? et.erro : NOMES_ETAPA[nome];
    return `<div class="etapa ${cls}" title="${esc(et.erro ?? et.situacao)}"><i></i>${esc(rotulo)}</div>`;
  }).join("")}</div>`;
}

function htmlEpisodio(ep) {
  const erro = Object.values(ep.etapas).some(et => et.situacao === "erro");
  const dur = ep.duracao_s ? new Date(ep.duracao_s * 1000).toISOString().slice(ep.duracao_s >= 3600 ? 11 : 14, 19) : "";
  const resumo = erro ? `<button class="botao mini" data-tentar="${esc(ep.id)}">tentar de novo</button>`
    : `<b>${ep.n_candidatos || "—"}</b>${ep.n_candidatos ? "candidatos" : "processando"}`;
  return `<div class="ep ${ep.id === epSel ? "sel" : ""}" data-ep="${esc(ep.id)}" tabindex="0" role="button" aria-pressed="${ep.id === epSel}">
    <div class="capa" style="background-image:url(${thumb(ep.id)})"><span>${esc(dur)}</span></div>
    <div><h3>${esc(ep.titulo ?? ep.url)}</h3><p>${esc(ep.canal ?? "")} · ${esc(dataHora(ep.criado_em))}</p></div>
    ${htmlEtapas(ep)}<div class="resumo">${resumo}</div></div>`;
}

function htmlLista() {
  if (!P.episodios.length) return vazio("Nenhum episódio ainda", "Cole o link de um episódio do YouTube acima.");
  return P.episodios.map(htmlEpisodio).join("");
}

function trilhoFila() {
  const el = $("#fila-trilho");
  const f = P?.fila;
  if (!f) return;
  el.hidden = !(f.atual || f.na_fila.length || f.pausada);
  const atual = f.atual ? `${esc(f.atual.etapa)} · ${esc(P.episodios.find(e => e.id === f.atual.episodio)?.titulo ?? f.atual.episodio)}` : "parada";
  el.innerHTML = f.pausada
    ? `<b>Fila pausada</b><div>${esc(f.pausada)}</div><button class="botao mini" id="retomar">retomar</button>`
    : `<div><b>Fila</b> · ${f.na_fila.length} na fila</div><div>${atual}</div>`;
  const b = $("#retomar");
  if (b) b.onclick = () => post("/api/fila/retomar").then(atualizarProducao).catch(e => avisar(e.message));
}

function ligarLista() {
  $$("[data-ep]").forEach(el => {
    const abrir = () => { epSel = el.dataset.ep; desenhar(); };
    el.onclick = ev => { if (!ev.target.closest("[data-tentar]")) abrir(); };
    el.onkeydown = ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); abrir(); } };
  });
  $$("[data-tentar]").forEach(b => {
    b.onclick = () => post(`/api/episodios/${encodeURIComponent(b.dataset.tentar)}/tentar`)
      .then(atualizarProducao).catch(e => avisar(e.message));
  });
}

// Atualiza só a lista e a fila (não redesenha a entrada nem o player do episódio aberto).
async function atualizarProducao() {
  P = await api("/api/producao");
  trilhoFila();
  const lista = $("#lista-episodios");
  if (lista) { lista.innerHTML = htmlLista(); ligarLista(); }
  if (temTrabalho()) { clearTimeout(atualizarProducao.t); atualizarProducao.t = setTimeout(() => atualizarProducao().catch(e => avisar(e.message)), 3000); }
}

async function telaEpisodios(meu) {
  P = await api("/api/producao");
  if (meu !== desenhar.n) return;
  if (!epSel && P.episodios.length) epSel = P.episodios[0].id;
  $("#tela").innerHTML = `<header><div><h1>Produção <em>— do episódio ao Short</em></h1>
    <p class="sub">Cole o link do episódio. O app baixa vídeo e legenda do YouTube e acha os momentos.</p></div></header>
    ${htmlEntrada()}<div class="episodios" id="lista-episodios">${htmlLista()}</div><div id="detalhe-episodio"></div>`;
  trilhoFila();
  ligarLista();
  $("#entrada").onsubmit = async ev => {
    ev.preventDefault();
    const b = ev.submitter; b.disabled = true;
    const d = Object.fromEntries(new FormData(ev.target));
    try {
      const r = await post("/api/episodios", { ...d, n_shorts: Number(d.n_shorts) });
      epSel = r.id; ev.target.reset(); await desenhar();
    } catch (e) { avisar(e.message); } finally { b.disabled = false; }
  };
  if (epSel) await blocoEpisodio(epSel, meu);
  if (temTrabalho()) atualizarProducao.t = setTimeout(() => atualizarProducao().catch(e => avisar(e.message)), 3000);
}
TELAS.episodios = telaEpisodios;
```

Notas:
- `E` (estado do painel) traz `nichos` e `formatos` (nomes); `carregar()` de `base.js` já roda
  na subida. Se `E` ainda não estiver carregado quando a tela abrir, chame `carregar()` antes.
- Quando um episódio sai de "rodando" para "ok" na etapa `momentos`, o detalhe aberto precisa
  aparecer: em `atualizarProducao`, se o episódio selecionado mudou a situação da etapa
  `momentos`, chame `blocoEpisodio(epSel, desenhar.n)` (só nesse caso — não a cada 3 s, para
  não reiniciar o vídeo).
- Contador do trilho `#cont-episodios`: nº de episódios com trabalho (rodando ou na fila) ou
  com erro; atualizar em `trilhoFila()`.

- [ ] **Step 5: `node --check` e check Python; commit**

```bash
git add web/static/index.html web/static/painel.css web/static/js/base.js web/static/js/inicio.js web/static/js/episodios.js
git commit -m "feat: aba Produção com entrada do link, episódios e fila no trilho"
```

---

### Task 9: Detalhe do episódio — candidatos, trecho e curadoria

**Files:**
- Create: `web/static/js/episodio.js`
- Modify: `web/static/painel.css`

- [ ] **Step 1: `js/episodio.js`**

```js
"use strict";
// Detalhe do episódio: candidatos (nota 0–10), painel com o trecho tocando, rubrica, justificativa,
// tags e aprovar/rejeitar. No plano A ainda não há Shorts renderizados: o trecho toca do vídeo
// original (16:9) com fragmento #t=início,fim.
let candSel = 0;
const NOMES_RUBRICA = { gancho_3s: "Gancho 3 s", autocontido: "Autocontido", espanto: "Espanto",
  historia_ou_virada: "História/virada", fechamento: "Fechamento" };
const nota10 = n => (n / 10).toFixed(1).replace(".", ",");
const tempo = s => new Date(s * 1000).toISOString().slice(s >= 3600 ? 11 : 14, 19);

function htmlCandidatos(D) {
  return `<div class="candidatos">
    <div class="cand cab"><span>Nota</span><span>Início</span><span>Dur.</span><span>Candidato e justificativa</span><span></span></div>
    ${D.candidatos.map(c => `<div class="cand ${c.indice === candSel ? "sel" : ""}" data-cand="${c.indice}" tabindex="0" role="button" aria-pressed="${c.indice === candSel}">
      <span class="n ${c.nota_final >= 80 ? "up" : ""}">${nota10(c.nota_final)}</span>
      <span class="num">${tempo(c.inicio)}</span><span class="num">${tempo(c.fim - c.inicio)}</span>
      <div><div class="t">${esc(c.titulo)}</div><div class="j">${esc(c.justificativa)}</div></div>
      <span class="decisao ${esc(c.decisao ?? "")}">${c.decisao ? esc(c.decisao) : ""}</span></div>`).join("")}</div>`;
}

function htmlPainel(D, c) {
  const rub = D.rubrica.map(k => `<div class="rub"><span>${esc(NOMES_RUBRICA[k] ?? k)}</span>
    <div class="b"><i style="width:${(c.notas[k] ?? 0) * 20}%"></i></div><span>${c.notas[k] ?? "—"}</span></div>`).join("");
  const decidido = c.decisao ? `<p class="sub">Decidido: <b>${esc(c.decisao)}</b></p>` :
    `<div class="decide"><button class="botao mini ok" data-decide="aprovado">✓ Aprovar</button>
      <button class="botao mini no" data-decide="rejeitado">✕ Rejeitar</button></div>
     <div class="motivo" hidden><select id="motivo-cat">${D.motivos.map(m => `<option>${esc(m)}</option>`).join("")}</select>
      <input id="motivo-txt" placeholder="detalhe (opcional)"><button class="botao mini no" id="motivo-ok">Rejeitar</button></div>`;
  return `<aside class="painel">
    <video class="trecho" controls preload="metadata" src="/api/episodios/${encodeURIComponent(D.id)}/video#t=${c.inicio},${c.fim}"></video>
    <h3>${esc(c.titulo)}</h3>
    <p class="meta">${esc(D.titulo ?? D.id)} · ${tempo(c.inicio)} → ${tempo(c.fim)} · nota ${nota10(c.nota_final)}</p>
    <div class="rubrica">${rub}</div>
    <p class="porque">${esc(c.justificativa)}</p>
    <div class="tags">${c.bonus.map(t => `<span class="chip">${esc(t)}</span>`).join("")}${c.penalidades.map(t => `<span class="chip no">${esc(t)}</span>`).join("")}</div>
    ${decidido}</aside>`;
}

async function decidir(D, c, decisao, motivo) {
  await post(`/api/episodios/${encodeURIComponent(D.id)}/candidatos/${c.indice}/decisao`, { decisao, motivo });
  await blocoEpisodio(D.id, desenhar.n);
}

function ligarPainel(D, c) {
  const painel = $(".painel");
  $$("[data-decide]", painel).forEach(b => {
    b.onclick = () => {
      if (b.dataset.decide === "aprovado") decidir(D, c, "aprovado", null).catch(e => avisar(e.message));
      else { $(".motivo", painel).hidden = false; $("#motivo-cat").focus(); }
    };
  });
  const ok = $("#motivo-ok");
  if (ok) ok.onclick = () => {
    const txt = $("#motivo-txt").value.trim();
    decidir(D, c, "rejeitado", txt ? `${$("#motivo-cat").value}: ${txt}` : $("#motivo-cat").value).catch(e => avisar(e.message));
  };
  // o fragmento #t=ini,fim pausa no fim do trecho; ao reabrir o mesmo vídeo, volta ao início do trecho
  const v = $("video.trecho", painel);
  v.onplay = () => { if (v.currentTime < c.inicio || v.currentTime >= c.fim) v.currentTime = c.inicio; };
}

async function blocoEpisodio(id, meu) {
  const D = await api(`/api/episodios/${encodeURIComponent(id)}`);
  if (meu !== desenhar.n) return;
  const alvo = $("#detalhe-episodio");
  if (!D.candidatos.length) {
    alvo.innerHTML = Object.values(D.etapas).some(et => et.situacao === "erro") ? ""
      : vazio("Procurando os momentos…", "Os candidatos aparecem aqui quando a etapa 'momentos' terminar.");
    return;
  }
  if (!D.candidatos.some(c => c.indice === candSel)) candSel = D.candidatos[0].indice;
  const c = D.candidatos.find(x => x.indice === candSel);
  alvo.innerHTML = `<div class="detalhe"><div><div class="secao"><h2>Candidatos <em>— ${esc(D.titulo ?? id)}</em></h2>
    <span class="num">${D.candidatos.length} momentos · nota = rubrica do detector (0–10)</span></div>${htmlCandidatos(D)}</div>
    ${htmlPainel(D, c)}</div>`;
  $$("[data-cand]", alvo).forEach(el => {
    const abrir = () => { candSel = Number(el.dataset.cand); blocoEpisodio(id, desenhar.n).catch(e => avisar(e.message)); };
    el.onclick = abrir;
    el.onkeydown = ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); abrir(); } };
  });
  ligarPainel(D, c);
}
```

Nota: trocar de episódio deve zerar `candSel` (em `episodios.js`, ao mudar `epSel`, fazer
`candSel = 0`). `blocoEpisodio` é chamado com `desenhar.n` atual nas re-renderizações locais,
então o guard `meu` só descarta respostas de uma navegação anterior.

- [ ] **Step 2: CSS** — copiar do mockup `.detalhe`, `.secao`, `.candidatos`, `.cand` (+ `.cand.sel`
com a borda laranja à esquerda como `.linha.sel`), `.painel`, `.rubrica`, `.rub`, `.porque`,
`.tags`, `.decide`; `video.trecho { width: 100%; border-radius: 10px; background: #000; aspect-ratio: 16/9; }`;
`.motivo` em linha (select + input + botão); `.decisao.aprovado { color: var(--ok) }`,
`.decisao.rejeitado { color: var(--warn) }`; `.chip.no { color: var(--warn) }`. Mobile ≤ 900 px:
`.detalhe` empilha (painel em cima dos candidatos), `.cand` esconde a justificativa.

- [ ] **Step 3: `node --check`, check Python, commit**

```bash
git add web/static/js/episodio.js web/static/painel.css
git commit -m "feat: candidatos do episódio com trecho tocando, rubrica e curadoria"
```

---

### Task 10: Verificação ponta a ponta com um episódio real

Custa **uma** chamada do detector (`claude -p`, cota da assinatura) e o download de um vídeo.
Antes de rodar, peça a Davi o link de um episódio curto (≤ 20 min, com legenda em português no
YouTube) — ou confirme usar o PrimoCast 536 já baixado (as etapas vídeo e sinais serão puladas;
a legenda só roda se `palavras.json` não existir: para testar a legenda nele, mova o
`palavras.json` do Whisper para `palavras.whisper.json` antes e devolva depois).

- [ ] **Step 1:** subir o painel: `.venv/Scripts/cortes painel` (porta 8790).
- [ ] **Step 2:** no navegador do app, aba **Episódios**: colar o link, nicho `financas`, Gerar.
  Conferir: o episódio aparece; as etapas avançam (vídeo → legenda → sinais → momentos) com a
  fila no trilho; nenhuma recarga da página zera o formulário ou o player.
- [ ] **Step 3:** quando `momentos` ficar ok: candidatos ordenados por nota; clicar num candidato
  troca o painel; o vídeo toca **a partir do início do trecho** e para no fim; rubrica, justificativa
  e tags batem com o `candidatos.json`.
- [ ] **Step 4:** aprovar um candidato e rejeitar outro com motivo; conferir as linhas novas em
  `nichos/financas/exemplos/bons.jsonl` e `ruins.jsonl`. **Depois do teste, pergunte a Davi se
  ficam** — são exemplos reais que o detector passa a ler.
- [ ] **Step 5:** erro visível: colar um link de vídeo sem legenda em português (ou forçar com um
  id inexistente) → a etapa fica em erro com a causa e "tentar de novo" aparece.
- [ ] **Step 6:** 375 px: sem rolagem horizontal; entrada empilhada; detalhe empilhado.
- [ ] **Step 7:** check completo e commit de ajustes visuais, se houver.

```bash
git add web/static
git commit -m "fix: ajustes da verificação ponta a ponta da produção"
```
