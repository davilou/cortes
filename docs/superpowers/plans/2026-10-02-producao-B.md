# Produção B — Render f1 + f7

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Depois que o detector acha os momentos, o painel renderiza sozinho os N melhores em f7 (Conversa) ou f1 (Falante), com pausas cortadas e legenda queimada. Mostra os Shorts numa grade 9:16 com player, aprovar/rejeitar, baixar MP4 e "Renderizar" nos demais candidatos.

**Architecture:** Pacote novo `src/cortes/render/`. Ele porta os protótipos de `testes/comum/` (recorte, rosto, legenda, montagem) com o episódio como parâmetro e põe o render do HyperFrames atrás de um executor injetável. O render vira a 5ª etapa do episódio (`render`) na fila que já existe. Essa etapa planeja os N melhores uma vez e depois renderiza, um por vez, os cortes com `status: na_fila` em `cortes/<indice>/corte.json`. "Renderizar" manual grava um corte `na_fila` e reenfileira o episódio; um gancho `antes` da fila reabre a etapa se ela já tinha fechado. A detecção de rosto roda no Python do ComfyUI (onnxruntime) por subprocesso.

**Tech Stack:** Python 3.13 · numpy · ffmpeg · HyperFrames 0.8.104 (`npx`) · OpenSeeFace ONNX (venv do ComfyUI) · FastAPI · pytest · ruff · mypy --strict · JS puro

**Spec:** `docs/superpowers/specs/2026-10-02-producao-design.md` (plano B: §3, §4.1, §4.3, §4.4, §5 itens 2–4, §8, §9).

## Decisões desta rodada (Davi, 2026-10-02)

- **Corte de pausas: sim, sempre.** Regra do dia 2 (`testes/TEMPLATES.md`): pausa > 0,4 s, 18 dB abaixo da fala, 0,12 s de respiro, zoom 100%/108% em cada emenda.
- **Sem trilha.** Exporta só com a voz; o som em alta entra pelo app do YouTube.

## Desvios da spec (registrar na spec na Task 14)

1. **A decisão aprovado/rejeitado fica em `curadoria.json`, não no `corte.json`.** O índice do corte é o índice do candidato, então a curadoria do plano A já vale para o Short. Repetir a decisão no `corte.json` criaria duas cópias, e uma delas envelheceria. O `status` do `corte.json` é só o do render: `na_fila | renderizando | pronto | erro`.
2. **As pausas são achadas pelo ÁUDIO, não pelo vão entre palavras.** Na legenda do YouTube o fim de cada palavra é o início da seguinte (spec §4.2), então o vão é quase sempre zero e o critério do protótipo não acharia nenhuma pausa.
3. **O detector de rosto mora em `render/visao/rosto.py`, fora de `src/`.** Ele roda no Python do ComfyUI, que tem cv2 e onnxruntime; o venv do projeto não tem, e o mypy de `src` não o enxerga.

## Fatos verificados que este plano usa

- Os protótipos aprovados (`testes/f1-falante-95-carteiras`, `testes/f7-conversa-comediante`, `testes/d2-conversa-comediante`) usam `hyperframes@0.8.104`. O render leva de 1 a 4 min por Short (`render.log`: "55.9s video · rendered in 3m 53.2s"). Linha de comando da skill `hyperframes-cli`: `npx hyperframes render --output out.mp4` (a qualidade padrão é `looks`), rodando dentro da pasta do projeto.
- Templates: `testes/comum/formatos/{falante,conversa}.tpl`. Os placeholders são `{{DUR}}`, `{{TRILHA}}`, `{{LEGENDAS}}`, `{{TRILHA_CHEIO}}` e `{{CORTES}}`. A largura do quadro está fixa em `3413px`, o que só vale para fonte 1920×1080. Os dois carregam GSAP de `cdn.jsdelivr.net` (o render precisa de internet, como nos protótipos).
- O rosto é detectado pelo modelo `C:/Users/User/Documents/IA Local/ComfyUI/custom_nodes/tts_audio_suite/engines/video/openseeface/models/mnv3_detection_opt.onnx`, rodando no Python `C:/Users/User/Documents/IA Local/ComfyUI/venv/Scripts/python.exe`. A troca de câmera é `ffmpeg ... select='gt(scene,0.15)'`.
- O vídeo do episódio tem altura entre 720 e 1080 (`ingestao.ALTURA_MINIMA = 720`, formato `height<=1080`). Por isso a escala vem da altura real e não é fixa.
- `candidatos.json` sai ordenado da maior nota para a menor (`detector/pontuacao.py:90`).
- `salvar_json`/`salvar_texto` (`cortes.episodio`) gravam de forma atômica, mas **não criam a pasta**.
- `curadoria.candidatos(pasta)` devolve `list[dict]` e `curadoria.decisoes(pasta)` devolve `{indice: {...}}`.
- `Fila(raiz, rodar, agora)`; `processar(id)` roda as etapas pendentes; `recuperar()` reabre o que não terminou na subida. Uma falha na etapa fica no `estado.json` e a fila segue.
- O fixture `cfg` (`tests/conftest.py`) troca `shutil.which` por um caminho falso para qualquer nome.
- Check: `.venv/Scripts/python -m ruff check src tests`, `.venv/Scripts/python -m mypy src`, `.venv/Scripts/python -m pytest -q` (o `addopts` já exclui `lento`).

## Efeito colateral a saber antes de rodar

Os episódios do plano A ganham a etapa `render` como `pendente` (migração no `ler`). Na primeira subida do painel depois deste plano, `recuperar()` põe todos eles na fila e cada um renderiza os N melhores, a 1–4 min por Short e em segundo plano.

## Estrutura de arquivos

```
render/formatos/falante.tpl          # f1 (cópia do protótipo: QW parametrizado, sem TRILHA)
render/formatos/conversa.tpl         # f7
render/visao/rosto.py                # detector (Python do ComfyUI), fora do mypy
src/cortes/render/__init__.py
src/cortes/render/processo.py        # executor injetável, ErroRender, exigir()
src/cortes/render/legenda.py         # palavras do corte, grupos, HTML (puro)
src/cortes/render/recorte.py         # pausas pelo áudio, remapear, args do ffmpeg (puro) + recorte fino
src/cortes/render/rosto.py           # rosto.json → enquadramento fixo por plano (puro) + medir fino
src/cortes/render/montagem.py        # formato → template, index.html (puro)
src/cortes/render/hyperframes.py     # projeto + render (fino)
src/cortes/render/corte.py           # corte.json: modelo, transições, planejar, próximo
src/cortes/render/pipeline.py        # um corte: trecho → rosto → html → mp4
src/cortes/producao/render.py        # etapa render (laço) + gancho que reabre a etapa
src/cortes/producao/rotas_cortes.py  # API: renderizar, vídeo do corte, resumo
web/static/js/grade.js               # grade de Shorts
tests/test_render_*.py, tests/test_producao_render.py, tests/test_producao_rotas_cortes.py
```

Modificados: `producao/estado.py` (etapa `render`), `producao/etapas.py` (`_render`), `producao/fila.py` (gancho `antes`), `producao/rotas.py` (resumo, cortes, montar), `painel/servidor.py` (Config, verificação na subida, fila real), `painel/ligacao.py` (título do `corte.json`), `cli.py` (`--py-visao`, `--modelo-rosto`), `web/static/js/{episodio,episodios}.js`, `web/static/index.html`, `web/static/painel.css`, `tests/conftest.py`, testes que listam as 4 etapas, `CLAUDE.md`, a spec.

---

### Task 1: Templates e detector de rosto no repositório

**Files:**
- Create: `render/formatos/falante.tpl`, `render/formatos/conversa.tpl`
- Create: `render/visao/rosto.py`

- [ ] **Step 1: Copiar os templates com a largura parametrizada e sem trilha**

```bash
mkdir -p render/formatos render/visao
for f in falante conversa; do
  sed -e 's/3413px/{{QW}}px/g' -e '/{{TRILHA}}/d' testes/comum/formatos/$f.tpl > render/formatos/$f.tpl
done
grep -o "{{[A-Z_]*}}" render/formatos/*.tpl | sort -u
```

Esperado: os placeholders de cada arquivo são exatamente `{{CORTES}}`, `{{DUR}}`, `{{LEGENDAS}}`, `{{QW}}` e `{{TRILHA_CHEIO}}`, e não sobra nenhum `{{TRILHA}}`.

- [ ] **Step 2: Escrever `render/visao/rosto.py`**

```python
"""Rosto por amostra de um trecho, ciente de troca de câmera.

Roda no Python do ComfyUI (tem cv2 e onnxruntime); o app chama por subprocesso
(src/cortes/render/rosto.py). Portado de testes/comum/rosto.py.

Uso: <python com onnxruntime> rosto.py <trecho.mp4> <modelo.onnx> <saida.json>
Grava {"largura", "altura", "pontos": [{"t", "x", "y", "corte"}]} em pixels da fonte;
corte=true no primeiro ponto depois de uma troca de câmera. Rosto em menos da metade das
amostras → sai com código 1 e a causa no stderr (trilha não confiável).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

LIMIAR = 0.6
PASSO_S = 0.25
CENA = 0.15   # scene > 0,15 = troca de câmera (testes/TEMPLATES.md)
_MEAN = -np.array([0.485, 0.456, 0.406], np.float32) / np.array([0.229, 0.224, 0.225], np.float32)
_STD = 1.0 / (np.array([0.229, 0.224, 0.225], np.float32) * 255.0)


def detectar(frame: np.ndarray, sessao: ort.InferenceSession) -> tuple[float, float] | None:
    im = cv2.resize(frame, (224, 224), interpolation=cv2.INTER_LINEAR)[:, :, ::-1] * _STD + _MEAN
    saida, maxpool = sessao.run([], {"input": np.transpose(im[None].astype(np.float32), (0, 3, 1, 2))})
    mapa = np.where(saida[0, 0] == maxpool[0, 0], saida[0, 0], 0)
    k = int(np.argmax(mapa))
    if mapa.flat[k] < LIMIAR:
        return None
    y, x = divmod(k, 56)
    return x * 4 * frame.shape[1] / 224, y * 4 * frame.shape[0] / 224


def cortes_de_camera(video: Path) -> list[float]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf",
                        f"scale=320:-1,select='gt(scene,{CENA})',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True, errors="replace")
    return [float(t) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def amostrar(video: Path, sessao: ort.InferenceSession, cortes: list[float]) -> tuple[int, int, list[dict], int]:
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    largura, altura = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    tempos = sorted({round(k * PASSO_S, 3) for k in range(int(dur / PASSO_S))} | {round(c + 0.05, 3) for c in cortes})
    pontos: list[dict] = []
    ultimo: int | None = None
    for t in tempos:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, frame = cap.read()
        if not ok or (r := detectar(frame, sessao)) is None:
            continue
        n = sum(1 for c in cortes if c <= t)
        pontos.append({"t": round(t, 2), "x": round(r[0]), "y": round(r[1]), "corte": ultimo is not None and n != ultimo})
        ultimo = n
    return largura, altura, pontos, len(tempos)


def main() -> None:
    trecho, modelo, saida = (Path(a) for a in sys.argv[1:4])
    sessao = ort.InferenceSession(str(modelo), providers=["CPUExecutionProvider"])
    largura, altura, pontos, n = amostrar(trecho, sessao, cortes_de_camera(trecho))
    if len(pontos) < 0.5 * n:
        sys.exit(f"rosto em só {len(pontos)} de {n} amostras — trilha não confiável")
    saida.write_text(json.dumps({"largura": largura, "altura": altura, "pontos": pontos}), encoding="utf-8")
    print(f"rosto em {len(pontos)}/{n} amostras; {sum(p['corte'] for p in pontos)} trocas de câmera")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Conferir no trecho real do f7**

```bash
"C:/Users/User/Documents/IA Local/ComfyUI/venv/Scripts/python.exe" render/visao/rosto.py testes/f7-conversa-comediante/assets/trecho.mp4 "C:/Users/User/Documents/IA Local/ComfyUI/custom_nodes/tts_audio_suite/engines/video/openseeface/models/mnv3_detection_opt.onnx" "$TEMP/rosto-f7.json"
head -c 300 "$TEMP/rosto-f7.json"
```

Esperado: imprime `rosto em N/M amostras; K trocas de câmera` com K ≥ 1 (o f7 troca de câmera), e o JSON começa com `{"largura": 1920, "altura": 1080, "pontos": [`.

- [ ] **Step 4: Commit**

```bash
git add render/
git commit -m "feat: templates f1/f7 e detector de rosto saem de testes/ para render/"
```

---

### Task 2: Executor de processos e erro do render

**Files:**
- Create: `src/cortes/render/__init__.py`, `src/cortes/render/processo.py`
- Test: `tests/test_render_processo.py`

- [ ] **Step 1: Escrever o teste**

```python
from pathlib import Path

import pytest

from cortes.render.processo import ErroRender, exigir


def test_exigir_devolve_a_saida() -> None:
    assert exigir(lambda a, c: (0, "tudo certo"), ["x"], None, "teste") == "tudo certo"


def test_exigir_falha_alto_com_o_fim_do_log() -> None:
    log = "a" * 5000 + "causa real"

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        return 2, log

    with pytest.raises(ErroRender, match=r"recorte falhou \(código 2\).*causa real") as ex:
        exigir(rodar, ["ffmpeg"], None, "recorte")
    assert len(str(ex.value)) < 1700
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_render_processo.py -q`
Esperado: FAIL (`ModuleNotFoundError: cortes.render`).

- [ ] **Step 3: Implementar**

`src/cortes/render/__init__.py`:

```python
"""Render dos Shorts (spec produção §4.1): trecho, rosto, legenda, montagem e HyperFrames."""
```

`src/cortes/render/processo.py`:

```python
"""Processos externos do render (ffmpeg, Python da visão, HyperFrames) atrás de um executor
injetável — os testes passam um falso; nada de rede, GPU ou render de verdade fora do `lento`."""
import subprocess
from collections.abc import Callable
from pathlib import Path

Rodar = Callable[[list[str], Path | None], tuple[int, str]]   # (args, cwd) → (código, stdout+stderr)
CAUDA = 1500   # caracteres do fim do log que vão para a mensagem de erro (a tela mostra)


class ErroRender(RuntimeError):
    """Falha no render de um corte. A mensagem traz o passo e o fim do log."""


def rodar_processo(args: list[str], cwd: Path | None) -> tuple[int, str]:
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout + r.stderr


def exigir(rodar: Rodar, args: list[str], cwd: Path | None, passo: str) -> str:
    codigo, saida = rodar(args, cwd)
    if codigo != 0:
        raise ErroRender(f"{passo} falhou (código {codigo}): {saida[-CAUDA:]}")
    return saida
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_render_processo.py -q`
Esperado: 2 passed.

- [ ] **Step 5: Check e commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
git add src/cortes/render tests/test_render_processo.py
git commit -m "feat: executor injetável e ErroRender para o render"
```

---

### Task 3: Legenda do Short (puro)

**Files:**
- Create: `src/cortes/render/legenda.py`
- Test: `tests/test_render_legenda.py`

- [ ] **Step 1: Escrever os testes**

```python
from cortes.render.legenda import Grupo, grupos, legenda_html, palavras_do_corte
from cortes.tipos import Palavra


def P(texto: str, inicio: float) -> Palavra:
    return Palavra(texto, inicio, round(inicio + 0.3, 3))


def test_palavras_do_corte_ficam_relativas_ao_inicio() -> None:
    ws = [P("antes", 9.0), P("Eu", 10.0), P("ganhei.", 10.5), P("depois", 20.5)]
    assert palavras_do_corte(ws, 10.0, 20.0) == [Palavra("Eu", 0.0, 0.3), Palavra("ganhei.", 0.5, 0.8)]


def test_grupo_fecha_na_pontuacao_com_duas_palavras() -> None:
    gs = grupos([P("Eu", 0.0), P("perdi.", 0.6), P("Tudo", 1.2), P("mesmo", 1.8)], 3.0)
    assert gs == [Grupo(0.0, 1.2, ("Eu", "perdi.")), Grupo(1.2, 1.8, ("Tudo", "mesmo"))]


def test_grupo_fecha_em_cinco_palavras_e_dura_no_maximo_2_6s() -> None:
    gs = grupos([P(f"p{i}", i * 0.6) for i in range(7)], 10.0)
    assert [len(g.palavras) for g in gs] == [5, 2] and gs[0].dur == 2.6


def test_grupos_que_comecam_juntos_se_fundem() -> None:
    gs = grupos([P("Ah", 0.0), P("é.", 0.1), P("Foi", 0.3), P("assim.", 0.4), P("Depois", 2.0)], 3.0)
    assert [g.palavras for g in gs] == [("Ah", "é.", "Foi", "assim."), ("Depois",)]


def test_html_escapa_o_texto() -> None:
    html = legenda_html([Grupo(0.0, 1.0, ("<b>", "&"))])
    assert "&lt;b&gt; &amp;" in html and 'data-start="0.0" data-duration="1.0"' in html
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_render_legenda.py -q`
Esperado: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar `src/cortes/render/legenda.py`**

```python
"""Legenda queimada do Short: palavras do corte e grupos de legenda (puro; spec produção §4.1).

Portado de testes/comum/corte.py (`palavras`, `grupos`, `legenda_html`), sem as trocas manuais
de palavra do protótipo (eram erros do Whisper daquele episódio). Até o editor (plano C), a
legenda sai como veio (spec §10).
"""
import html
import re
from dataclasses import dataclass

from cortes.tipos import Palavra

MAX_PALAVRAS = 5
JUNTA_S = 0.55      # grupos que começam a menos disso um do outro viram um só
JUNTA_MAX = 7       # ... desde que juntos não passem disso
DUR_MAX_S = 2.6
_FECHA = re.compile(r"[.,?!…]$")


@dataclass(frozen=True)
class Grupo:
    ini: float
    dur: float
    palavras: tuple[str, ...]


def palavras_do_corte(palavras: list[Palavra], ini: float, fim: float) -> list[Palavra]:
    """Palavras que COMEÇAM em [ini, fim], com tempo relativo a ini."""
    return [Palavra(p.texto, round(p.inicio - ini, 3), round(p.fim - ini, 3))
            for p in palavras if ini - 0.01 <= p.inicio <= fim + 0.01]


def _brutos(ws: list[Palavra]) -> list[list[Palavra]]:
    gs: list[list[Palavra]] = [[]]
    for w in ws:
        gs[-1].append(w)
        if len(gs[-1]) >= MAX_PALAVRAS or (len(gs[-1]) >= 2 and _FECHA.search(w.texto)):
            gs.append([])
    return [g for g in gs if g]


def _fundir(gs: list[list[Palavra]]) -> list[list[Palavra]]:
    k = 0
    while k < len(gs) - 1:
        if gs[k + 1][0].inicio - gs[k][0].inicio < JUNTA_S and len(gs[k]) + len(gs[k + 1]) <= JUNTA_MAX:
            gs[k] += gs.pop(k + 1)
        else:
            k += 1
    return gs


def grupos(ws: list[Palavra], dur: float) -> list[Grupo]:
    """Fecham em pontuação (2+ palavras) ou em 5 palavras; cada um fica até o próximo, no máx. 2,6 s."""
    gs = _fundir(_brutos(ws))
    res: list[Grupo] = []
    for k, g in enumerate(gs):
        a = g[0].inicio
        b = gs[k + 1][0].inicio if k + 1 < len(gs) else dur
        res.append(Grupo(round(a, 2), round(min(b, a + DUR_MAX_S) - a, 2), tuple(p.texto for p in g)))
    return res


def legenda_html(gs: list[Grupo]) -> str:
    return "\n".join(
        f'      <div class="clip leg" id="leg-{i}" data-start="{g.ini}" data-duration="{g.dur}" '
        f'data-track-index="20"><span>{html.escape(" ".join(g.palavras))}</span></div>'
        for i, g in enumerate(gs))
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_render_legenda.py -q`
Esperado: 5 passed.

- [ ] **Step 5: Check e commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
git add src/cortes/render/legenda.py tests/test_render_legenda.py
git commit -m "feat: grupos de legenda do Short portados do protótipo"
```

---

### Task 4: Pausas pelo áudio e recorte do trecho

**Files:**
- Create: `src/cortes/render/recorte.py`
- Test: `tests/test_render_recorte.py`

- [ ] **Step 1: Escrever os testes**

```python
from pathlib import Path

import numpy as np
import pytest

from cortes.render.processo import ErroRender
from cortes.render.recorte import (
    args_recorte,
    duracao,
    palavras_sem_pausa,
    recortar,
    remapear,
    segmentos_sem_pausa,
    tempos_de_corte,
)
from cortes.tipos import Palavra

TAXA = 1000   # quadro de 20 ms = 20 amostras; seno de 50 Hz = 1 período por quadro (RMS constante)


def tom(s: float, amp: float = 0.5) -> np.ndarray:
    t = np.arange(int(s * TAXA)) / TAXA
    return (amp * np.sin(2 * np.pi * 50 * t)).astype(np.float32)


def silencio(s: float) -> np.ndarray:
    return np.zeros(int(s * TAXA), np.float32)


def test_pausa_longa_e_silenciosa_e_cortada_com_respiro() -> None:
    audio = np.concatenate([tom(1), silencio(1), tom(1)])
    assert segmentos_sem_pausa(audio, TAXA) == [(0.0, 1.12), (1.88, 3.0)]


def test_pausa_curta_fica() -> None:
    audio = np.concatenate([tom(1), silencio(0.3), tom(1)])
    assert segmentos_sem_pausa(audio, TAXA) == [(0.0, 2.3)]


def test_pausa_barulhenta_fica() -> None:   # 10 dB abaixo da fala (riso, reação): não é silêncio
    audio = np.concatenate([tom(1), tom(1, 0.5 * 10 ** (-10 / 20)), tom(1)])
    assert segmentos_sem_pausa(audio, TAXA) == [(0.0, 3.0)]


def test_remapear_leva_tempo_da_pausa_para_a_emenda() -> None:
    segs = [(0.0, 1.12), (1.88, 3.0)]
    assert [remapear(t, segs) for t in (0.5, 1.5, 2.0, 5.0)] == [0.5, 1.12, 1.24, 2.24]
    assert tempos_de_corte(segs) == [1.12] and duracao(segs) == 2.24


def test_palavras_sem_pausa() -> None:
    segs = [(0.0, 1.12), (1.88, 3.0)]
    assert palavras_sem_pausa([Palavra("oi", 2.0, 2.5)], segs) == [Palavra("oi", 1.24, 1.74)]


def test_args_do_recorte_buscam_antes_e_cortam_relativo() -> None:
    args = args_recorte(Path("v.mp4"), Path("t.mp4"), 100.0, [(0.0, 1.12), (1.88, 3.0)])
    assert args[:8] == ["ffmpeg", "-v", "error", "-y", "-ss", "100.000", "-t", "3.000"]
    fc = args[args.index("-filter_complex") + 1]
    assert "trim=0.000:1.120" in fc and "trim=1.880:3.000" in fc and fc.endswith("concat=n=2:v=1:a=1[v][a]")


def test_recortar_grava_por_parcial_e_falha_alto(tmp_path: Path) -> None:
    def ok(args: list[str], cwd: Path | None) -> tuple[int, str]:
        Path(args[-1]).write_bytes(b"mp4")
        return 0, ""

    recortar(Path("v.mp4"), tmp_path / "trecho.mp4", 0.0, [(0.0, 1.0)], ok)
    assert (tmp_path / "trecho.mp4").read_bytes() == b"mp4"
    with pytest.raises(ErroRender, match="recorte do trecho falhou"):
        recortar(Path("v.mp4"), tmp_path / "outro.mp4", 0.0, [(0.0, 1.0)], lambda a, c: (1, "ruim"))
    assert not (tmp_path / "outro.mp4").exists()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_render_recorte.py -q`
Esperado: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar `src/cortes/render/recorte.py`**

```python
"""Trecho do Short: pausas cortadas pela energia do áudio e o recorte no ffmpeg (spec produção §4.1).

Portado de testes/comum/corte.py (dia 2), com uma diferença: as pausas vêm do ÁUDIO, não do vão
entre palavras. Na legenda do YouTube o fim de cada palavra é o início da seguinte (spec §4.2),
então esse vão é quase sempre zero. Regra mantida (testes/TEMPLATES.md, dia 2): pausa > 0,4 s,
só se estiver 18 dB abaixo da fala; 0,12 s de respiro de cada lado. Pausa "barulhenta" (riso,
reação) fica.
"""
import subprocess
from collections.abc import Callable
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from cortes.render.processo import CAUDA, ErroRender, Rodar, exigir
from cortes.tipos import Palavra

PAUSA_MIN = 0.4
RESPIRO = 0.12
SILENCIO_DB = 18.0
QUADRO_S = 0.02
PERCENTIL_FALA = 90   # nível de referência da fala: o trecho de um corte é quase todo fala
TAXA = 16000

Segmento = tuple[float, float]
LerAudio = Callable[[Path, float, float], NDArray[np.float32]]


def _db_por_quadro(audio: NDArray[np.float32], taxa: int) -> NDArray[np.float64]:
    n = int(taxa * QUADRO_S)
    k = len(audio) // n
    if k == 0:
        raise ErroRender("áudio do trecho mais curto que um quadro de 20 ms")
    q = audio[: k * n].astype(np.float64).reshape(k, n)
    return np.asarray(20 * np.log10(np.sqrt(np.mean(q ** 2, axis=1)) + 1e-9), dtype=np.float64)


def _corridas(marcas: NDArray[np.bool_]) -> list[tuple[int, int]]:
    """[início, fim) de cada sequência de True."""
    res: list[tuple[int, int]] = []
    ini: int | None = None
    for i, m in enumerate(marcas):
        if m and ini is None:
            ini = i
        elif not m and ini is not None:
            res.append((ini, i))
            ini = None
    if ini is not None:
        res.append((ini, len(marcas)))
    return res


def segmentos_sem_pausa(audio: NDArray[np.float32], taxa: int = TAXA) -> list[Segmento]:
    """Trechos a manter, em segundos desde o início do áudio."""
    db = _db_por_quadro(audio, taxa)
    silencio = db < float(np.percentile(db, PERCENTIL_FALA)) - SILENCIO_DB
    manter: list[Segmento] = []
    cursor = 0.0
    for a, b in _corridas(silencio):
        ta, tb = a * QUADRO_S, b * QUADRO_S
        if tb - ta <= PAUSA_MIN:
            continue
        manter.append((round(cursor, 3), round(ta + RESPIRO, 3)))
        cursor = tb - RESPIRO
    manter.append((round(cursor, 3), round(len(audio) / taxa, 3)))
    return manter


def remapear(t: float, segs: list[Segmento]) -> float:
    """Tempo do trecho original → tempo sem pausas. Um tempo dentro de uma pausa removida vai para
    a emenda: o início de palavra da legenda tem erro de ~0,3 s e pode cair na pausa sem ser bug."""
    acum = 0.0
    for a, b in segs:
        if t < a:
            return round(acum, 3)
        if t <= b:
            return round(acum + t - a, 3)
        acum += b - a
    return round(acum, 3)


def palavras_sem_pausa(ws: list[Palavra], segs: list[Segmento]) -> list[Palavra]:
    return [Palavra(p.texto, remapear(p.inicio, segs), remapear(p.fim, segs)) for p in ws]


def tempos_de_corte(segs: list[Segmento]) -> list[float]:
    """Instantes, no vídeo novo, em que uma pausa foi removida (onde o template alterna o zoom)."""
    acum, ts = 0.0, []
    for a, b in segs[:-1]:
        acum += b - a
        ts.append(round(acum, 3))
    return ts


def duracao(segs: list[Segmento]) -> float:
    return round(sum(b - a for a, b in segs), 3)


def args_recorte(video: Path, destino: Path, ini: float, segs: list[Segmento]) -> list[str]:
    """`-ss` antes do `-i` (busca rápida num episódio de 1 h) e trims relativos ao início do corte;
    micro-fade de 8 ms em cada emenda para o áudio não estalar."""
    partes, rot = [], []
    for i, (a, b) in enumerate(segs):
        partes.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}];"
                      f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,"
                      f"afade=t=in:d=0.008,afade=t=out:st={max(0.0, b - a - 0.008):.3f}:d=0.008[a{i}];")
        rot.append(f"[v{i}][a{i}]")
    fc = "".join(partes) + "".join(rot) + f"concat=n={len(segs)}:v=1:a=1[v][a]"
    return ["ffmpeg", "-v", "error", "-y", "-ss", f"{ini:.3f}", "-t", f"{segs[-1][1]:.3f}", "-i", str(video),
            "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16",
            "-preset", "fast", "-c:a", "aac", "-b:a", "192k", str(destino)]


def recortar(video: Path, destino: Path, ini: float, segs: list[Segmento], rodar: Rodar) -> None:
    parcial = destino.with_name(destino.stem + ".parcial.mp4")
    exigir(rodar, args_recorte(video, parcial, ini, segs), None, "recorte do trecho")
    parcial.replace(destino)


def ler_trecho_wav(audio: Path, ini: float, dur: float) -> NDArray[np.float32]:
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ini:.3f}", "-t", f"{dur:.3f}", "-i", str(audio),
                        "-ac", "1", "-ar", str(TAXA), "-f", "f32le", "-"], capture_output=True)
    if r.returncode != 0:
        raise ErroRender(f"ffmpeg falhou ao ler {audio}: {r.stderr.decode(errors='replace')[-CAUDA:]}")
    return np.frombuffer(r.stdout, dtype=np.float32)
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_render_recorte.py -q`
Esperado: 7 passed.

- [ ] **Step 5: Check e commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
git add src/cortes/render/recorte.py tests/test_render_recorte.py
git commit -m "feat: pausas do Short pelo áudio e recorte do trecho no ffmpeg"
```

---

### Task 5: Enquadramento fixo por plano

**Files:**
- Create: `src/cortes/render/rosto.py`
- Test: `tests/test_render_rosto.py`

- [ ] **Step 1: Escrever os testes**

```python
import json
from pathlib import Path

import pytest

from cortes.render.processo import ErroRender
from cortes.render.rosto import Ponto, Rosto, largura_quadro, ler_rosto, medir_rosto, planos, trilha_fixa

R = Rosto(1920, 1080, (Ponto(0.0, 960, 540, False), Ponto(0.25, 980, 540, False),
                       Ponto(2.0, 1800, 500, True), Ponto(2.25, 1800, 520, False)))


def test_planos_separam_na_troca_de_camera() -> None:
    assert [len(p) for p in planos(R.pontos)] == [2, 2]


def test_trilha_fixa_usa_a_mediana_e_nao_mostra_borda() -> None:
    assert trilha_fixa(R) == [[0.0, -1184.4, 0.0, 1], [2.0, -2333.3, 0.0, 1]]
    assert largura_quadro(R) == 3413


def test_ler_rosto(tmp_path: Path) -> None:
    arq = tmp_path / "rosto.json"
    arq.write_text(json.dumps({"largura": 1920, "altura": 1080,
                               "pontos": [{"t": 0.0, "x": 960, "y": 540, "corte": False}]}), encoding="utf-8")
    assert ler_rosto(arq) == Rosto(1920, 1080, (Ponto(0.0, 960, 540, False),))
    arq.write_text(json.dumps({"largura": 1920, "altura": 1080, "pontos": []}), encoding="utf-8")
    with pytest.raises(ErroRender, match="rosto.json"):
        ler_rosto(arq)


def test_medir_rosto_chama_o_python_da_visao(tmp_path: Path) -> None:
    vistos: list[list[str]] = []

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        vistos.append(args)
        return 0, ""

    medir_rosto(Path("t.mp4"), Path("r.json"), Path("rosto.py"), Path("py.exe"), Path("m.onnx"), rodar)
    assert vistos == [["py.exe", "rosto.py", "t.mp4", "m.onnx", "r.json"]]
```

Conta do primeiro plano: escala 1920/1080 = 1,7778; mediana x = 970 → 540 − 970 × 1,7778 = −1184,4; y: 700 − 540 × 1,7778 = −260, limitado a 0 porque o quadro tem a altura exata da janela. Segundo plano: 540 − 1800 × 1,7778 = −2660, limitado a 1080 − 3413,3 = −2333,3.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_render_rosto.py -q`
Esperado: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar `src/cortes/render/rosto.py`**

```python
"""Enquadramento do Short: posição FIXA por plano de câmera (spec produção §4.1; testes/TEMPLATES.md).

Dentro de um plano a câmera virtual não se mexe (seguir o rosto o tempo todo deixou o espectador
tonto na rodada 1). A posição é a mediana do rosto no plano e muda com corte seco na troca de câmera.
A detecção roda fora deste Python: render/visao/rosto.py, no venv do ComfyUI (onnxruntime).
"""
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cortes.render.processo import ErroRender, Rodar, exigir

JANELA = (1080, 1920)
ALVO = (540, 700)   # onde o rosto fica na tela 9:16 (protótipo: CAM_CHEIO da rodada 1)


@dataclass(frozen=True)
class Ponto:
    t: float
    x: float
    y: float
    corte: bool


@dataclass(frozen=True)
class Rosto:
    largura: int
    altura: int
    pontos: tuple[Ponto, ...]


def _ponto(p: Any) -> Ponto:
    if not isinstance(p, dict) or not isinstance(p.get("corte"), bool):
        raise ValueError(f"ponto inválido: {p!r}")
    return Ponto(float(p["t"]), float(p["x"]), float(p["y"]), p["corte"])


def ler_rosto(arquivo: Path) -> Rosto:
    try:
        d = json.loads(arquivo.read_text(encoding="utf-8"))
        largura, altura = d["largura"], d["altura"]
        if not (isinstance(largura, int) and isinstance(altura, int) and largura > 0 and altura > 0):
            raise ValueError("largura/altura deveriam ser inteiros positivos")
        pontos = tuple(_ponto(p) for p in d["pontos"])
        if not pontos:
            raise ValueError("nenhum ponto de rosto")
        return Rosto(largura, altura, pontos)
    except (OSError, KeyError, TypeError, ValueError) as ex:
        raise ErroRender(f"{arquivo}: rosto inválido ({ex})") from ex


def escala(r: Rosto) -> float:
    return JANELA[1] / r.altura


def largura_quadro(r: Rosto) -> int:
    return round(r.largura * escala(r))


def planos(pontos: tuple[Ponto, ...]) -> list[list[Ponto]]:
    res: list[list[Ponto]] = [[]]
    for p in pontos:
        if p.corte and res[-1]:
            res.append([])
        res[-1].append(p)
    return res


def trilha_fixa(r: Rosto) -> list[list[float]]:
    """[t, x, y, 1] no início de cada plano: deslocamento do quadro (≤ 0) que leva a mediana do
    rosto ao ALVO sem mostrar borda. O 1 final pede corte seco ao template."""
    e = escala(r)
    jw, jh = JANELA
    qw, qh = r.largura * e, r.altura * e
    res: list[list[float]] = []
    for k, pl in enumerate(planos(r.pontos)):
        x = statistics.median(p.x for p in pl)
        y = statistics.median(p.y for p in pl)
        t = 0.0 if k == 0 else pl[0].t
        res.append([t, round(min(0.0, max(jw - qw, ALVO[0] - x * e)), 1),
                    round(min(0.0, max(jh - qh, ALVO[1] - y * e)), 1), 1])
    return res


def medir_rosto(trecho: Path, destino: Path, script: Path, py_visao: Path, modelo: Path, rodar: Rodar) -> None:
    exigir(rodar, [str(py_visao), str(script), str(trecho), str(modelo), str(destino)], None, "detecção de rosto")
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_render_rosto.py -q`
Esperado: 4 passed.

- [ ] **Step 5: Check e commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
git add src/cortes/render/rosto.py tests/test_render_rosto.py
git commit -m "feat: enquadramento fixo por plano a partir do rosto.json"
```

---

### Task 6: Montagem do index.html

**Files:**
- Create: `src/cortes/render/montagem.py`
- Test: `tests/test_render_montagem.py`

- [ ] **Step 1: Escrever os testes**

```python
from pathlib import Path

import pytest

from cortes.render.legenda import Grupo
from cortes.render.montagem import FORMATOS, caminho_template, montar_html, valores
from cortes.render.processo import ErroRender
from cortes.render.rosto import Ponto, Rosto

REPO = Path(__file__).resolve().parents[1]
R = Rosto(1920, 1080, (Ponto(0.0, 960, 540, False),))


def test_placeholder_sobrando_e_erro() -> None:
    with pytest.raises(ErroRender, match=r"\{\{QW\}\}"):
        montar_html("<p>{{DUR}} {{QW}}</p>", {"DUR": "3"})


def test_formato_sem_template_e_erro() -> None:
    with pytest.raises(ErroRender, match="formato 'f4'"):
        caminho_template(REPO, "f4")


@pytest.mark.parametrize("formato", FORMATOS)
def test_templates_reais_montam_sem_sobra(formato: str) -> None:
    tpl = caminho_template(REPO, formato).read_text(encoding="utf-8")
    html = montar_html(tpl, valores(12.5, R, [Grupo(0.0, 1.0, ("Oi",))], [4.2]))
    assert 'data-duration="12.5"' in html and "3413px" in html and "<span>Oi</span>" in html
    assert "[4.2].forEach" in html
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_render_montagem.py -q`
Esperado: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar `src/cortes/render/montagem.py`**

```python
"""index.html do Short a partir do template do formato (puro; spec produção §4.1, §9)."""
import json
import re
from pathlib import Path

from cortes.render.legenda import Grupo, legenda_html
from cortes.render.processo import ErroRender
from cortes.render.rosto import Rosto, largura_quadro, trilha_fixa

FORMATOS = ("f7", "f1")   # ordem da tela; planos D e E acrescentam f4 e f3
_TEMPLATES = {"f7": "conversa", "f1": "falante"}
_PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")


def caminho_template(raiz: Path, formato: str) -> Path:
    if formato not in _TEMPLATES:
        raise ErroRender(f"formato '{formato}' sem template; use um de {FORMATOS}")
    return raiz / "render" / "formatos" / f"{_TEMPLATES[formato]}.tpl"


def montar_html(tpl: str, valores: dict[str, str]) -> str:
    html = tpl
    for k, v in valores.items():
        html = html.replace("{{" + k + "}}", v)
    if sobra := _PLACEHOLDER.findall(html):
        raise ErroRender(f"placeholders sem valor: {sorted(set(sobra))}")
    return html


def valores(dur: float, rosto: Rosto, grupos: list[Grupo], cortes: list[float]) -> dict[str, str]:
    return {"DUR": str(round(dur, 2)), "QW": str(largura_quadro(rosto)), "LEGENDAS": legenda_html(grupos),
            "TRILHA_CHEIO": json.dumps(trilha_fixa(rosto)), "CORTES": json.dumps(cortes)}
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_render_montagem.py -q`
Esperado: 4 passed.

- [ ] **Step 5: Check e commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
git add src/cortes/render/montagem.py tests/test_render_montagem.py
git commit -m "feat: montagem do index.html do Short a partir do template"
```

---

### Task 7: Projeto e render do HyperFrames

**Files:**
- Create: `src/cortes/render/hyperframes.py`
- Test: `tests/test_render_hyperframes.py`

- [ ] **Step 1: Escrever os testes**

```python
import json
from pathlib import Path

import pytest

from cortes.render.hyperframes import HYPERFRAMES, criar_projeto, renderizar
from cortes.render.processo import ErroRender


def test_criar_projeto(tmp_path: Path) -> None:
    criar_projeto(tmp_path / "projeto", "<html></html>")
    assert (tmp_path / "projeto" / "index.html").read_text(encoding="utf-8") == "<html></html>"
    assert json.loads((tmp_path / "projeto" / "hyperframes.json").read_text(encoding="utf-8"))["paths"]["assets"] == "assets"


def test_renderizar_grava_por_parcial_e_guarda_o_log(tmp_path: Path) -> None:
    vistos: list[tuple[list[str], Path | None]] = []

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        vistos.append((args, cwd))
        Path(args[-1]).write_bytes(b"mp4")
        return 0, "Render complete"

    renderizar(tmp_path, tmp_path / "short-v1.mp4", "npx", rodar)
    assert (tmp_path / "short-v1.mp4").read_bytes() == b"mp4"
    assert vistos[0][0][:5] == ["npx", "--yes", HYPERFRAMES, "render", "--output"] and vistos[0][1] == tmp_path
    assert (tmp_path / "render.log").read_text(encoding="utf-8") == "Render complete"


def test_render_que_falha_nao_deixa_mp4(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="render falhou.*timeline"):
        renderizar(tmp_path, tmp_path / "short-v1.mp4", "npx", lambda a, c: (1, "erro na timeline"))
    assert not (tmp_path / "short-v1.mp4").exists()


def test_render_sem_arquivo_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ErroRender, match="sem gerar"):
        renderizar(tmp_path, tmp_path / "short-v1.mp4", "npx", lambda a, c: (0, "ok"))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_render_hyperframes.py -q`
Esperado: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar `src/cortes/render/hyperframes.py`**

```python
"""Projeto HyperFrames de um corte e o render em MP4 (spec produção §4.1).

O MP4 sai primeiro como `.parcial.mp4` e só vira `short-v<k>.mp4` se o render terminar: um render
que falha mantém a versão anterior intacta (spec §8).
"""
from pathlib import Path

from cortes.episodio import salvar_json, salvar_texto
from cortes.render.processo import CAUDA, ErroRender, Rodar

HYPERFRAMES = "hyperframes@0.8.104"   # a versão dos protótipos aprovados (testes/*/package.json)
_CONFIG = {
    "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
    "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
    "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
    "media": {"autoProxy": True},
}


def criar_projeto(proj: Path, html: str) -> None:
    proj.mkdir(parents=True, exist_ok=True)
    salvar_json(proj / "hyperframes.json", _CONFIG)
    salvar_texto(proj / "index.html", html)


def renderizar(proj: Path, saida: Path, npx: str, rodar: Rodar) -> None:
    parcial = saida.with_name(saida.stem + ".parcial.mp4")
    codigo, log = rodar([npx, "--yes", HYPERFRAMES, "render", "--output", str(parcial)], proj)
    salvar_texto(proj / "render.log", log)
    if codigo != 0:
        raise ErroRender(f"render falhou (código {codigo}): {log[-CAUDA:]}")
    if not parcial.exists() or parcial.stat().st_size == 0:
        raise ErroRender(f"render terminou sem gerar {parcial.name}: {log[-CAUDA:]}")
    parcial.replace(saida)
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_render_hyperframes.py -q`
Esperado: 4 passed.

- [ ] **Step 5: Check e commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
git add src/cortes/render/hyperframes.py tests/test_render_hyperframes.py
git commit -m "feat: projeto e render do HyperFrames atrás do executor"
```

---

### Task 8: O corte (corte.json)

**Files:**
- Create: `src/cortes/render/corte.py`
- Test: `tests/test_render_corte.py`

- [ ] **Step 1: Escrever os testes**

```python
import json
from pathlib import Path

import pytest

from cortes.producao.estado import ErroProducao
from cortes.render.corte import (
    PLANEJADO,
    Corte,
    concluir,
    cortes_do_episodio,
    falhar,
    gravar_corte,
    iniciar,
    ler_corte,
    melhores,
    novo_corte,
    pasta_corte,
    planejar,
    proximo,
    reenfileirar,
    video,
)

CANDS = [{"inicio": 10.0, "fim": 40.0, "titulo": "A", "nota_final": 50.0},
         {"inicio": 50.0, "fim": 80.0, "titulo": "B", "nota_final": 90.0},
         {"inicio": 90.0, "fim": 120.0, "titulo": "C", "nota_final": 70.0}]


def test_melhores_pela_nota() -> None:
    assert melhores(CANDS, 2) == [1, 2] and melhores(CANDS, 10) == [1, 2, 0]


def test_transicoes() -> None:
    c = novo_corte(1, CANDS[1], "f7")
    assert c == Corte(1, 50.0, 80.0, "f7", "B", "na_fila")
    pronto = concluir(iniciar(c))
    assert pronto.status == "pronto" and pronto.versao == 1
    erro = falhar(iniciar(pronto), "ErroRender: x")
    assert erro.status == "erro" and erro.versao == 1 and erro.erro == "ErroRender: x"
    de_novo = reenfileirar(erro, "f1")
    assert de_novo.status == "na_fila" and de_novo.formato == "f1" and de_novo.erro is None


@pytest.mark.parametrize("status", ["na_fila", "renderizando"])
def test_reenfileirar_recusa_quem_ja_esta_na_fila(status: str) -> None:
    c = novo_corte(0, CANDS[0], "f7")
    c = iniciar(c) if status == "renderizando" else c
    with pytest.raises(ErroProducao, match="já está na fila"):
        reenfileirar(c, "f7")


def test_proximo_retoma_quem_ficou_renderizando() -> None:
    a, b = novo_corte(0, CANDS[0], "f7"), iniciar(novo_corte(2, CANDS[2], "f7"))
    assert proximo([a, b]) == b
    assert proximo([a, concluir(b)]) == a and proximo([concluir(a)]) is None


def test_gravar_ler_e_listar(tmp_path: Path) -> None:
    c = novo_corte(2, CANDS[2], "f1")
    gravar_corte(pasta_corte(tmp_path, 2), c)
    assert ler_corte(pasta_corte(tmp_path, 2)) == c
    assert cortes_do_episodio(tmp_path) == [c] and video(tmp_path, c) is None
    assert video(tmp_path, concluir(c)) == tmp_path / "cortes" / "2" / "short-v1.mp4"


def test_corte_invalido(tmp_path: Path) -> None:
    d = pasta_corte(tmp_path, 0)
    d.mkdir(parents=True)
    (d / "corte.json").write_text(json.dumps({"indice": 0, "status": "voando"}), encoding="utf-8")
    with pytest.raises(ErroProducao, match="corte.json"):
        ler_corte(d)


def test_planejar_uma_vez_sem_pisar_no_manual(tmp_path: Path) -> None:
    gravar_corte(pasta_corte(tmp_path, 1), novo_corte(1, CANDS[1], "f1"))   # Renderizar manual antes
    planejar(tmp_path, "f7", 2, CANDS)
    assert [(c.indice, c.formato) for c in cortes_do_episodio(tmp_path)] == [(1, "f1"), (2, "f7")]
    assert (tmp_path / "cortes" / PLANEJADO).exists()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_render_corte.py -q`
Esperado: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar `src/cortes/render/corte.py`**

```python
"""Corte de um episódio: o candidato que vira Short, o formato e o status do render (spec §4.3).

episodios/<id>/cortes/<indice>/corte.json. O `indice` é o do candidato em candidatos.json, então a
curadoria do plano A (curadoria.json, por índice) vale para o Short. Aprovado e rejeitado ficam lá,
não aqui (uma decisão, um arquivo); o status deste arquivo é só o do render.
"""
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Literal, cast

from cortes.episodio import ler_json, salvar_json
from cortes.producao.estado import ErroProducao

Status = Literal["na_fila", "renderizando", "pronto", "erro"]
STATUS = ("na_fila", "renderizando", "pronto", "erro")
ARQUIVO = "corte.json"
PLANEJADO = "planejado.json"   # marcador: os N melhores já foram postos na fila (uma vez por episódio)


@dataclass(frozen=True)
class Corte:
    indice: int
    inicio: float
    fim: float
    formato: str
    titulo: str
    status: Status
    versao: int = 0            # última versão pronta (short-v<versao>.mp4); 0 = nenhuma
    erro: str | None = None


def pasta_corte(pasta_ep: Path, indice: int) -> Path:
    return pasta_ep / "cortes" / str(indice)


def video(pasta_ep: Path, c: Corte) -> Path | None:
    return pasta_corte(pasta_ep, c.indice) / f"short-v{c.versao}.mp4" if c.versao else None


def novo_corte(indice: int, cand: dict[str, Any], formato: str) -> Corte:
    return Corte(indice, float(cand["inicio"]), float(cand["fim"]), formato, str(cand["titulo"]), "na_fila")


def melhores(cands: list[dict[str, Any]], n: int) -> list[int]:
    return sorted(range(len(cands)), key=lambda i: (-float(cands[i]["nota_final"]), i))[:n]


def iniciar(c: Corte) -> Corte:
    return replace(c, status="renderizando", erro=None)


def concluir(c: Corte) -> Corte:
    return replace(c, status="pronto", versao=c.versao + 1, erro=None)


def falhar(c: Corte, msg: str) -> Corte:
    """A versão anterior (se houver) continua valendo: o MP4 dela não foi tocado (spec §8)."""
    return replace(c, status="erro", erro=msg)


def reenfileirar(c: Corte, formato: str) -> Corte:
    if c.status in ("na_fila", "renderizando"):
        raise ErroProducao(f"corte {c.indice} já está na fila do render")
    return replace(c, status="na_fila", formato=formato, erro=None)


def proximo(cortes: list[Corte]) -> Corte | None:
    """Quem ficou 'renderizando' numa queda volta primeiro; depois a fila pela ordem do índice
    (candidatos.json vem da maior nota para a menor)."""
    pendentes = [c for c in cortes if c.status in ("renderizando", "na_fila")]
    return min(pendentes, key=lambda c: (c.status != "renderizando", c.indice), default=None)


def gravar_corte(d: Path, c: Corte) -> None:
    d.mkdir(parents=True, exist_ok=True)
    salvar_json(d / ARQUIVO, asdict(c))


def _campo(x: dict[str, Any], nome: str, tipo: type | tuple[type, ...]) -> Any:
    """Bool é recusado mesmo onde se espera número (em Python, True é um int)."""
    v = x[nome]
    if not isinstance(v, tipo) or isinstance(v, bool):
        raise ValueError(f"campo '{nome}' deveria ser {getattr(tipo, '__name__', tipo)}, veio {v!r}")
    return v


def ler_corte(d: Path) -> Corte:
    arq = d / ARQUIVO
    try:
        x = ler_json(arq)
        if x["status"] not in STATUS:
            raise ValueError(f"status '{x['status']}' inválido; use um de {STATUS}")
        if x["erro"] is not None and not isinstance(x["erro"], str):
            raise ValueError("campo 'erro' deveria ser texto ou nulo")
        return Corte(_campo(x, "indice", int), float(_campo(x, "inicio", (int, float))),
                     float(_campo(x, "fim", (int, float))), _campo(x, "formato", str), _campo(x, "titulo", str),
                     cast(Status, x["status"]), _campo(x, "versao", int), x["erro"])
    except (OSError, KeyError, TypeError, ValueError) as ex:
        raise ErroProducao(f"{arq}: corte inválido ({ex})") from ex


def cortes_do_episodio(pasta_ep: Path) -> list[Corte]:
    arqs = sorted((pasta_ep / "cortes").glob(f"*/{ARQUIVO}"), key=lambda a: int(a.parent.name))
    return [ler_corte(a.parent) for a in arqs]


def planejar(pasta_ep: Path, formato: str, n: int, cands: list[dict[str, Any]]) -> None:
    """Põe os N melhores na fila do render, uma vez por episódio. Um corte que já existe (Renderizar
    manual antes do automático) fica como está."""
    (pasta_ep / "cortes").mkdir(parents=True, exist_ok=True)
    for i in melhores(cands, n):
        d = pasta_corte(pasta_ep, i)
        if not (d / ARQUIVO).exists():
            gravar_corte(d, novo_corte(i, cands[i], formato))
    salvar_json(pasta_ep / "cortes" / PLANEJADO, {"n": n, "formato": formato})
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_render_corte.py -q`
Esperado: 8 passed.

- [ ] **Step 5: Check e commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
git add src/cortes/render/corte.py tests/test_render_corte.py
git commit -m "feat: corte.json com status do render, transições e planejamento dos N melhores"
```

---

### Task 9: Pipeline de um corte

**Files:**
- Create: `src/cortes/render/pipeline.py`
- Test: `tests/test_render_pipeline.py`

- [ ] **Step 1: Escrever os testes**

```python
import json
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np

from cortes.render.corte import concluir, novo_corte
from cortes.render.pipeline import DepRender, janela, renderizar_corte

REPO = Path(__file__).resolve().parents[1]
ROSTO = {"largura": 1920, "altura": 1080, "pontos": [{"t": 0.0, "x": 960, "y": 540, "corte": False}]}


class Falso:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def rodar(self, args: list[str], cwd: Path | None) -> tuple[int, str]:
        self.chamadas.append(args[0])
        if args[0] == "ffmpeg" or args[0] == "npx":
            Path(args[-1]).write_bytes(b"mp4")
        elif args[0] == "py-visao":
            Path(args[4]).write_text(json.dumps(ROSTO), encoding="utf-8")
        return 0, "ok"

    def dep(self) -> DepRender:
        def tom(audio: Path, ini: float, dur: float) -> np.ndarray:
            t = np.arange(int(dur * 16000)) / 16000
            return (0.5 * np.sin(2 * np.pi * 50 * t)).astype(np.float32)

        return DepRender(Path("py-visao"), Path("m.onnx"), "npx", self.rodar, tom)


def episodio(tmp: Path) -> Path:
    shutil.copytree(REPO / "render", tmp / "render")
    pasta = tmp / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    palavras = [{"texto": "Eu", "inicio": 10.1, "fim": 10.5}, {"texto": "ganhei.", "inicio": 10.5, "fim": 11.0}]
    (pasta / "palavras.json").write_text(json.dumps(palavras), encoding="utf-8")
    return pasta


C = novo_corte(0, {"inicio": 10.3, "fim": 14.0, "titulo": "T"}, "f7")


def test_janela_da_folga_no_inicio() -> None:
    assert janela(C) == (10.0, 14.0)
    assert janela(replace(C, inicio=0.1)) == (0.0, 14.0)


def test_renderiza_o_corte_ponta_a_ponta(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, C, tmp_path, f.dep())
    d = pasta / "cortes" / "0"
    assert (d / "short-v1.mp4").exists() and f.chamadas == ["ffmpeg", "py-visao", "npx"]
    html = (d / "projeto" / "index.html").read_text(encoding="utf-8")
    assert "{{" not in html and "<span>Eu ganhei.</span>" in html and 'data-duration="4.0"' in html


def test_segunda_versao_reaproveita_trecho_e_rosto(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, C, tmp_path, f.dep())
    renderizar_corte(pasta, concluir(C), tmp_path, f.dep())
    assert f.chamadas == ["ffmpeg", "py-visao", "npx", "npx"]
    assert (pasta / "cortes" / "0" / "short-v2.mp4").exists()


def test_novo_inicio_refaz_trecho_e_rosto(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    renderizar_corte(pasta, C, tmp_path, f.dep())
    renderizar_corte(pasta, replace(concluir(C), inicio=11.0), tmp_path, f.dep())
    assert f.chamadas == ["ffmpeg", "py-visao", "npx", "ffmpeg", "py-visao", "npx"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_render_pipeline.py -q`
Esperado: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar `src/cortes/render/pipeline.py`**

```python
"""Render de um corte, do trecho ao MP4 (spec produção §4.1).

Trecho e rosto são caros e só dependem de início/fim: ficam gravados com `recorte.json` como
marcador, que é escrito por último. Se início/fim mudarem (editor, plano C), os dois são refeitos.
"""
from dataclasses import dataclass
from pathlib import Path

from cortes.episodio import ler_json, salvar_json
from cortes.render.corte import Corte, pasta_corte
from cortes.render.hyperframes import criar_projeto, renderizar
from cortes.render.legenda import grupos, palavras_do_corte
from cortes.render.montagem import caminho_template, montar_html, valores
from cortes.render.processo import Rodar, rodar_processo
from cortes.render.recorte import (
    LerAudio,
    Segmento,
    duracao,
    ler_trecho_wav,
    palavras_sem_pausa,
    recortar,
    segmentos_sem_pausa,
    tempos_de_corte,
)
from cortes.render.rosto import ler_rosto, medir_rosto
from cortes.tipos import Palavra

FOLGA_INICIO = 0.3   # s: a legenda do YouTube começa a palavra ~0,2–0,4 s depois do Whisper (spec §4.2)
SCRIPT_ROSTO = Path("render") / "visao" / "rosto.py"


@dataclass(frozen=True)
class DepRender:
    py_visao: Path
    modelo_rosto: Path
    npx: str
    rodar: Rodar = rodar_processo
    ler_audio: LerAudio = ler_trecho_wav


def janela(c: Corte) -> tuple[float, float]:
    return max(0.0, round(c.inicio - FOLGA_INICIO, 3)), c.fim


def preparar_trecho(pasta_ep: Path, c: Corte, raiz: Path, dep: DepRender) -> list[Segmento]:
    d = pasta_corte(pasta_ep, c.indice)
    ini, fim = janela(c)
    marca = d / "recorte.json"
    if marca.exists():
        r = ler_json(marca)
        if r["inicio"] == ini and r["fim"] == fim:
            return [(float(a), float(b)) for a, b in r["segmentos"]]
    segs = segmentos_sem_pausa(dep.ler_audio(pasta_ep / "audio.wav", ini, fim - ini))
    trecho = d / "projeto" / "assets" / "trecho.mp4"
    trecho.parent.mkdir(parents=True, exist_ok=True)
    recortar(pasta_ep / "video.mp4", trecho, ini, segs, dep.rodar)
    medir_rosto(trecho, d / "rosto.json", raiz / SCRIPT_ROSTO, dep.py_visao, dep.modelo_rosto, dep.rodar)
    salvar_json(marca, {"inicio": ini, "fim": fim, "segmentos": segs})
    return segs


def _html(pasta_ep: Path, c: Corte, raiz: Path, segs: list[Segmento]) -> str:
    ini, fim = janela(c)
    todas = [Palavra(**p) for p in ler_json(pasta_ep / "palavras.json")]
    ws = palavras_sem_pausa(palavras_do_corte(todas, ini, fim), segs)
    dur = duracao(segs)
    rosto = ler_rosto(pasta_corte(pasta_ep, c.indice) / "rosto.json")
    tpl = caminho_template(raiz, c.formato).read_text(encoding="utf-8")
    return montar_html(tpl, valores(dur, rosto, grupos(ws, dur), tempos_de_corte(segs)))


def renderizar_corte(pasta_ep: Path, c: Corte, raiz: Path, dep: DepRender) -> None:
    """Gera cortes/<indice>/short-v<versao+1>.mp4. Falha alto (ErroRender) em qualquer passo."""
    segs = preparar_trecho(pasta_ep, c, raiz, dep)
    proj = pasta_corte(pasta_ep, c.indice) / "projeto"
    criar_projeto(proj, _html(pasta_ep, c, raiz, segs))
    renderizar(proj, pasta_corte(pasta_ep, c.indice) / f"short-v{c.versao + 1}.mp4", dep.npx, dep.rodar)
```

Confira o `data-duration="4.0"` do teste: o tom não tem pausa, então só há um segmento (0, 4.0), `duracao` = 4.0 e `str(round(4.0, 2))` = `"4.0"`.

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_render_pipeline.py -q`
Esperado: todos passam.

- [ ] **Step 5: Check e commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
git add src/cortes/render/pipeline.py tests/test_render_pipeline.py
git commit -m "feat: pipeline de render de um corte com trecho e rosto reaproveitados"
```

---

### Task 10: Etapa `render` na fila

**Files:**
- Modify: `src/cortes/producao/estado.py` (ETAPAS, `ler`)
- Create: `src/cortes/producao/render.py`
- Modify: `src/cortes/producao/etapas.py` (`Dependencias.render`, `_render`, `_ETAPAS`)
- Modify: `src/cortes/producao/fila.py` (gancho `antes`)
- Test: `tests/test_producao_render.py`; ajustar `tests/test_producao_estado.py`, `tests/test_producao_fila.py:36,195`, `tests/test_producao_rotas.py:174`

- [ ] **Step 1: Escrever os testes novos**

`tests/test_producao_render.py`:

```python
import json
from datetime import datetime
from pathlib import Path

from cortes.producao.estado import gravar, ler, marcar, novo
from cortes.producao.fila import Fila
from cortes.producao.render import reabrir_render, render_pendente, rodar_render
from cortes.render.corte import Corte, cortes_do_episodio, gravar_corte, novo_corte, pasta_corte
from cortes.render.pipeline import DepRender

AGORA = datetime(2026, 10, 2, 9)
DEP = DepRender(Path("py"), Path("m.onnx"), "npx")
CANDS = [{"inicio": 10.0, "fim": 40.0, "titulo": "A", "nota_final": 50.0},
         {"inicio": 50.0, "fim": 80.0, "titulo": "B", "nota_final": 90.0},
         {"inicio": 90.0, "fim": 120.0, "titulo": "C", "nota_final": 70.0}]


def episodio(tmp: Path, n: int = 2) -> Path:
    pasta = tmp / "episodios" / "abcdefghijk"
    pasta.mkdir(parents=True)
    e = novo("abcdefghijk", "https://youtu.be/abcdefghijk", "financas", n, "f7", AGORA)
    for nome in ("video", "legenda", "sinais", "momentos"):
        e = marcar(e, nome, "ok", AGORA)
    gravar(pasta, e)
    (pasta / "candidatos.json").write_text(json.dumps(CANDS), encoding="utf-8")
    return pasta


def test_planeja_os_melhores_e_renderiza_um_por_vez(tmp_path: Path) -> None:
    pasta, feitos = episodio(tmp_path), []

    def falso(p: Path, c: Corte, raiz: Path, dep: DepRender) -> None:
        feitos.append((c.indice, c.status))

    rodar_render(pasta, ler(pasta), tmp_path, DEP, falso)
    assert feitos == [(1, "na_fila"), (2, "na_fila")]
    assert [(c.indice, c.status, c.versao) for c in cortes_do_episodio(pasta)] == [(1, "pronto", 1), (2, "pronto", 1)]


def test_um_corte_que_falha_nao_para_os_outros(tmp_path: Path) -> None:
    pasta = episodio(tmp_path)

    def falso(p: Path, c: Corte, raiz: Path, dep: DepRender) -> None:
        if c.indice == 1:
            raise RuntimeError("npx sumiu")

    rodar_render(pasta, ler(pasta), tmp_path, DEP, falso)
    um, dois = cortes_do_episodio(pasta)
    assert um.status == "erro" and um.erro == "RuntimeError: npx sumiu" and dois.status == "pronto"


def test_nao_replaneja(tmp_path: Path) -> None:
    pasta, feitos = episodio(tmp_path), []
    rodar_render(pasta, ler(pasta), tmp_path, DEP, lambda p, c, r, d: None)
    rodar_render(pasta, ler(pasta), tmp_path, DEP, lambda p, c, r, d: feitos.append(c.indice))
    assert feitos == [] and len(cortes_do_episodio(pasta)) == 2


def test_reabre_a_etapa_quando_um_render_foi_pedido_depois(tmp_path: Path) -> None:
    pasta = episodio(tmp_path)
    gravar(pasta, marcar(ler(pasta), "render", "ok", AGORA))
    assert not render_pendente(ler(pasta), cortes_do_episodio(pasta))
    gravar_corte(pasta_corte(pasta, 0), novo_corte(0, CANDS[0], "f1"))
    reabrir_render(pasta, AGORA)
    assert ler(pasta).etapas["render"].situacao == "pendente"


def test_fila_chama_o_gancho_antes_de_processar_e_na_subida(tmp_path: Path) -> None:
    episodio(tmp_path)
    vistos: list[str] = []
    f = Fila(tmp_path, lambda n, p, e: None, lambda: AGORA, antes=lambda p: vistos.append(p.name))
    f.recuperar()
    f.processar("abcdefghijk")
    assert vistos == ["abcdefghijk", "abcdefghijk"]
```

Em `tests/test_producao_estado.py`, acrescente:

```python
def test_estado_do_plano_a_sem_render_migra_para_pendente(tmp_path: Path) -> None:
    e = novo("abcdefghijk", "u", "financas", 5, "f7", datetime(2026, 10, 2))
    d = asdict(e)
    del d["etapas"]["render"]
    (tmp_path / "estado.json").write_text(json.dumps(d), encoding="utf-8")
    assert ler(tmp_path).etapas["render"] == Etapa()
```

Confira os imports desse arquivo: são necessários `json`, `asdict`, `datetime`, `Etapa`, `ler` e `novo`. Os testes que já existem iteram por `ETAPAS` e passam a incluir `render` sozinhos.

Nos testes que listam as etapas rodadas pela fila falsa, inclua `"render"` no fim: `tests/test_producao_fila.py:36` e `:195` passam a esperar `["video", "legenda", "sinais", "momentos", "render"]`, e `tests/test_producao_rotas.py:174` também.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_producao_render.py tests/test_producao_estado.py tests/test_producao_fila.py -q`
Esperado: FAIL (`cortes.producao.render` não existe; as listas de etapas não batem).

- [ ] **Step 3: Etapa `render` no estado**

Em `src/cortes/producao/estado.py`:

```python
ETAPAS = ("video", "legenda", "sinais", "momentos", "render")
```

e em `ler`, troque a linha `etapas = {n: _etapa(d["etapas"][n]) for n in ETAPAS}` por:

```python
        brutas = d["etapas"]
        # 'render' entrou no plano B: o estado.json do plano A não tem a chave e a etapa nasce
        # pendente. É migração explícita de uma etapa nova, não default para dado que falta.
        etapas = {n: Etapa() if n == "render" and n not in brutas else _etapa(brutas[n]) for n in ETAPAS}
```

- [ ] **Step 4: Criar `src/cortes/producao/render.py`**

```python
"""Etapa `render` do episódio (spec produção §4.4): planeja os N melhores uma vez e renderiza, um
por vez, os cortes na fila. Um corte que falha fica em erro com a causa no corte.json e os outros
seguem; a etapa só fica em erro se nem o planejamento der certo.

"Renderizar" manual grava um corte `na_fila` e enfileira o episódio; se a etapa já tinha fechado
(ok), `reabrir_render` — o gancho `antes` da fila, que roda na thread da fila — reabre a etapa.
Por rodar na mesma thread que marca a etapa como ok, não há corrida entre os dois.
"""
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from cortes.producao import curadoria
from cortes.producao.estado import EstadoEpisodio, gravar, ler, marcar
from cortes.render.corte import (
    PLANEJADO,
    Corte,
    concluir,
    cortes_do_episodio,
    falhar,
    gravar_corte,
    iniciar,
    pasta_corte,
    planejar,
    proximo,
)
from cortes.render.pipeline import DepRender, renderizar_corte

Renderizar = Callable[[Path, Corte, Path, DepRender], None]


def rodar_render(pasta: Path, e: EstadoEpisodio, raiz: Path, dep: DepRender,
                 renderizar: Renderizar = renderizar_corte) -> None:
    if not (pasta / "cortes" / PLANEJADO).exists():
        planejar(pasta, e.formato, e.n_shorts, curadoria.candidatos(pasta))
    while (c := proximo(cortes_do_episodio(pasta))) is not None:   # relê o disco: pega pedido novo
        _um(pasta, c, raiz, dep, renderizar)


def _um(pasta: Path, c: Corte, raiz: Path, dep: DepRender, renderizar: Renderizar) -> None:
    d = pasta_corte(pasta, c.indice)
    gravar_corte(d, iniciar(c))
    try:
        renderizar(pasta, c, raiz, dep)
    except Exception as ex:   # um corte ruim não para os outros; a causa fica visível no corte.json
        traceback.print_exc()
        gravar_corte(d, falhar(c, f"{type(ex).__name__}: {ex}"))
        return
    gravar_corte(d, concluir(c))


def render_pendente(e: EstadoEpisodio, cortes: list[Corte]) -> bool:
    return e.etapas["render"].situacao == "ok" and proximo(cortes) is not None


def reabrir_render(pasta: Path, agora: datetime) -> None:
    e = ler(pasta)
    if render_pendente(e, cortes_do_episodio(pasta)):
        gravar(pasta, marcar(e, "render", "pendente", agora))
```

- [ ] **Step 5: Ligar a etapa em `src/cortes/producao/etapas.py`**

Acrescente os imports `from cortes.producao.render import rodar_render` e `from cortes.render.pipeline import DepRender`. Acrescente também o campo em `Dependencias`, depois de `modelo`:

```python
    render: DepRender | None = None   # o servidor monta com a configuração verificada na subida
```

Acrescente a função e registre-a:

```python
def _render(pasta: Path, e: EstadoEpisodio, raiz: Path, dep: Dependencias) -> None:
    if dep.render is None:
        raise ErroProducao("render sem configuração: o servidor não montou Dependencias.render")
    rodar_render(pasta, e, raiz, dep.render)


_ETAPAS = {"video": _video, "legenda": _legenda, "sinais": _sinais, "momentos": _momentos, "render": _render}
```

Atualize a docstring do módulo: "As 5 etapas do episódio no painel: vídeo, legenda do YouTube (ou transcrição colada), sinais, momentos, render."

- [ ] **Step 6: Gancho `antes` na `src/cortes/producao/fila.py`**

```python
RodarEtapa = Callable[[str, Path, EstadoEpisodio], None]
Antes = Callable[[Path], None]   # roda na thread da fila antes de processar (e na subida)


def _nada(pasta: Path) -> None:
    return None
```

No `__init__`, acrescente o parâmetro `antes: Antes = _nada` depois de `agora` e guarde em `self._antes = antes`. Em `recuperar`, a primeira linha dentro do `for` vira `self._antes(arquivo.parent)` (antes de `e = ler(arquivo.parent)`). Em `processar`, logo depois de `pasta = self._pasta(id)`, coloque `self._antes(pasta)`. Na docstring da classe (topo do módulo), acrescente: "`antes(pasta)` roda na thread da fila antes de cada episódio e na subida — é o que reabre a etapa render quando um Renderizar chega depois de ela fechar."

- [ ] **Step 7: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_producao_render.py tests/test_producao_estado.py tests/test_producao_fila.py tests/test_producao_etapas.py tests/test_producao_rotas.py -q`
Esperado: todos passam.

- [ ] **Step 8: Check e commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
git add src/cortes/producao tests
git commit -m "feat: etapa render na fila, com N melhores planejados e reabertura por pedido manual"
```

---

### Task 11: Configuração do render verificada na subida

**Files:**
- Modify: `src/cortes/painel/servidor.py` (`Config`, `verificar_render`, `criar_app`, `_fila_real`)
- Modify: `src/cortes/cli.py` (`--py-visao`, `--modelo-rosto`)
- Modify: `tests/conftest.py`, `tests/test_painel_servidor.py:147`
- Modify: `CLAUDE.md`
- Test: `tests/test_painel_servidor.py`

- [ ] **Step 1: Escrever os testes**

Acrescente em `tests/test_painel_servidor.py` (o arquivo já importa `pytest`, `Config`, `criar_app` e `ErroPainel`; acrescente `from dataclasses import replace`):

```python
def test_nao_sobe_sem_o_python_da_visao(cfg: Config) -> None:
    with pytest.raises(ErroPainel, match="Python da visão"):
        criar_app(replace(cfg, py_visao=cfg.raiz / "nada.exe"))


def test_nao_sobe_sem_ffmpeg(cfg: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda nome: None if nome == "ffmpeg" else "C:/fake/x.exe")
    with pytest.raises(ErroPainel, match="ffmpeg não está no PATH"):
        criar_app(cfg)


def test_nao_sobe_sem_template(cfg: Config) -> None:
    (cfg.raiz / "render" / "formatos" / "falante.tpl").unlink()
    with pytest.raises(ErroPainel, match="falante.tpl"):
        criar_app(cfg)
```

Troque `tests/test_painel_servidor.py:147` por `criar_app(replace(cfg, skill_dir=cfg.raiz / "nada"))`.

Em `tests/conftest.py`, antes de `c = Config(...)`:

```python
    for arq in ("render/formatos/falante.tpl", "render/formatos/conversa.tpl", "render/visao/rosto.py",
                "visao/python.exe", "visao/rosto.onnx"):
        (tmp_path / arq).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / arq).write_text("", encoding="utf-8")
```

e passe a montar `Config(raiz=tmp_path, skill_dir=skill, estatico=estatico, py_visao=tmp_path / "visao" / "python.exe", modelo_rosto=tmp_path / "visao" / "rosto.onnx")`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_painel_servidor.py -q`
Esperado: FAIL (`Config` não aceita `py_visao`).

- [ ] **Step 3: Implementar em `src/cortes/painel/servidor.py`**

Acrescente os campos ao `Config`, depois de `estatico`:

```python
    py_visao: Path      # Python com onnxruntime e cv2 (venv do ComfyUI) para o detector de rosto
    modelo_rosto: Path  # mnv3_detection_opt.onnx do OpenSeeFace
```

Acrescente a função (imports: `import shutil`, `from cortes.render.montagem import FORMATOS, caminho_template`, `from cortes.render.pipeline import SCRIPT_ROSTO, DepRender`, `from cortes.producao.render import reabrir_render`):

```python
def verificar_render(cfg: Config) -> str:
    """Configuração do render ausente → o servidor não sobe e diz o que falta (spec produção §8).
    Devolve o caminho do npx (no Windows, npx.cmd)."""
    faltas = [f"{nome} não está no PATH" for nome in ("ffmpeg", "npx") if shutil.which(nome) is None]
    arquivos = [("Python da visão (--py-visao)", cfg.py_visao), ("modelo do rosto (--modelo-rosto)", cfg.modelo_rosto),
                ("detector de rosto", cfg.raiz / SCRIPT_ROSTO)]
    arquivos += [("template", caminho_template(cfg.raiz, f)) for f in FORMATOS]
    faltas += [f"{rotulo} não existe: {p}" for rotulo, p in arquivos if not p.exists()]
    npx = shutil.which("npx")
    if faltas or npx is None:
        raise ErroPainel("render sem configuração: " + "; ".join(faltas))
    return npx
```

Em `criar_app`, depois de `coleta.verificar_skill(cfg.skill_dir)`:

```python
    npx = verificar_render(cfg)
    fila = fila if fila is not None else _fila_real(cfg, agora, npx)
```

E troque `_fila_real` por:

```python
def _fila_real(cfg: Config, agora: Callable[[], datetime], npx: str) -> Fila:
    dep = Dependencias(render=DepRender(cfg.py_visao, cfg.modelo_rosto, npx))
    return Fila(cfg.raiz, lambda nome, pasta, e: rodar_etapa(nome, pasta, e, cfg.raiz, dep), agora,
                antes=lambda pasta: reabrir_render(pasta, agora()))
```

- [ ] **Step 4: CLI**

Em `src/cortes/cli.py`, junto de `SKILL_ANALYTICS`:

```python
COMFYUI = Path("C:/Users/User/Documents/IA Local/ComfyUI")
PY_VISAO = COMFYUI / "venv" / "Scripts" / "python.exe"
MODELO_ROSTO = (COMFYUI / "custom_nodes" / "tts_audio_suite" / "engines" / "video" / "openseeface" / "models"
                / "mnv3_detection_opt.onnx")
```

No subparser `painel`:

```python
    pn.add_argument("--py-visao", type=Path, default=PY_VISAO, help="Python com onnxruntime (venv do ComfyUI)")
    pn.add_argument("--modelo-rosto", type=Path, default=MODELO_ROSTO, help="detector de rosto do OpenSeeFace")
```

`rodar_painel(porta, skill, raiz, py_visao, modelo_rosto)` monta `Config(raiz=raiz, skill_dir=skill, estatico=ESTATICO, py_visao=py_visao, modelo_rosto=modelo_rosto)`, e `main` passa `args.py_visao, args.modelo_rosto`. Se `tests/test_cli_painel.py` chamar `rodar_painel` ou conferir os argumentos, acompanhe a assinatura nova.

- [ ] **Step 5: `CLAUDE.md`**

Na seção "Painel de contas", depois do comando:

```
O painel também renderiza os Shorts (plano B) e não sobe sem: `ffmpeg` e `npx` no PATH, o
Python do ComfyUI (`--py-visao`) e o detector de rosto do OpenSeeFace (`--modelo-rosto`).
Render real fica fora do check: `.venv/Scripts/python -m pytest -m lento`.
```

- [ ] **Step 6: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_painel_servidor.py tests/test_cli_painel.py -q`
Esperado: todos passam.

- [ ] **Step 7: Check e commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
git add src/cortes/painel/servidor.py src/cortes/cli.py tests CLAUDE.md
git commit -m "feat: painel não sobe sem ffmpeg, npx, Python da visão e templates do render"
```

---

### Task 12: API dos Shorts

**Files:**
- Create: `src/cortes/producao/rotas_cortes.py`
- Modify: `src/cortes/producao/rotas.py`
- Test: `tests/test_producao_rotas_cortes.py`

- [ ] **Step 1: Escrever os testes**

```python
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from cortes.painel.servidor import Config, criar_app
from cortes.producao.estado import EstadoEpisodio, gravar, ler, marcar
from cortes.producao.fila import Fila
from cortes.producao.render import reabrir_render
from cortes.render.corte import concluir, cortes_do_episodio, gravar_corte, ler_corte, novo_corte, pasta_corte
from tests.test_producao_rotas import CAND, preparar_concluido

AGORA = datetime(2026, 10, 2, 9)
EP = "/api/episodios/abcdefghijk"


def montar(cfg: Config, rodadas: list[str] | None = None) -> tuple[TestClient, Fila]:
    def rodar(nome: str, pasta: Path, e: EstadoEpisodio) -> None:
        if rodadas is not None:
            rodadas.append(nome)

    fila = Fila(cfg.raiz, rodar, lambda: AGORA, antes=lambda p: reabrir_render(p, AGORA))
    app = criar_app(cfg, executar=lambda a, c: "", abrir=lambda a, c: None, fila=fila)
    return TestClient(app, base_url="http://127.0.0.1"), fila


def test_renderizar_candidato_cria_corte_e_reabre_a_etapa(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    rodadas: list[str] = []
    c, fila = montar(cfg, rodadas)
    r = c.post(f"{EP}/cortes/0/renderizar", json={"formato": "f1"})
    assert r.status_code == 202 and fila.situacao()["na_fila"] == ["abcdefghijk"]
    assert ler_corte(pasta_corte(pasta, 0)).formato == "f1"
    fila.processar("abcdefghijk")
    assert rodadas == ["render"]   # o gancho reabriu só a etapa render


def test_renderizar_recusa(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    c, _ = montar(cfg)
    assert "não existe" in c.post(f"{EP}/cortes/7/renderizar", json={}).json()["detail"]
    assert "formato 'f4'" in c.post(f"{EP}/cortes/0/renderizar", json={"formato": "f4"}).json()["detail"]
    c.post(f"{EP}/cortes/0/renderizar", json={})
    assert "já está na fila" in c.post(f"{EP}/cortes/0/renderizar", json={}).json()["detail"]
    gravar(pasta, marcar(ler(pasta), "momentos", "pendente", AGORA))
    assert "momentos" in c.post(f"{EP}/cortes/0/renderizar", json={}).json()["detail"]


def test_detalhe_traz_cortes_e_resumo(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    gravar_corte(pasta_corte(pasta, 0), concluir(novo_corte(0, CAND, "f7")))
    c, _ = montar(cfg)
    d = c.get(EP).json()
    assert d["cortes"][0]["video"] == f"{EP}/cortes/0/video" and d["candidatos"][0]["corte"] == "pronto"
    assert d["render"] == {"prontos": 1, "total": 1, "rodando": None, "erros": 0}
    assert c.get("/api/producao").json()["episodios"][0]["render"]["prontos"] == 1


def test_video_do_corte_e_download(cfg: Config) -> None:
    pasta = preparar_concluido(cfg)
    corte = concluir(novo_corte(0, CAND, "f7"))
    gravar_corte(pasta_corte(pasta, 0), corte)
    (pasta_corte(pasta, 0) / "short-v1.mp4").write_bytes(b"mp4")
    c, _ = montar(cfg)
    assert c.get(f"{EP}/cortes/0/video").content == b"mp4"
    r = c.get(f"{EP}/cortes/0/video", params={"baixar": "true"})
    assert 'attachment; filename="abcdefghijk-0-v1.mp4"' in r.headers["content-disposition"]
    assert c.get(f"{EP}/cortes/3/video").status_code == 422
    assert cortes_do_episodio(pasta) == [corte]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_producao_rotas_cortes.py -q`
Esperado: FAIL (404 nas rotas novas / `KeyError: 'cortes'`).

- [ ] **Step 3: Criar `src/cortes/producao/rotas_cortes.py`**

```python
"""API dos Shorts de um episódio (plano B; spec produção §5): Renderizar, o MP4 do corte e o
resumo do render para a barra de etapas. `pasta_de` vem de rotas.py (valida o id do episódio)."""
import threading
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from cortes.producao import curadoria
from cortes.producao.estado import ErroProducao, ler
from cortes.producao.fila import Fila
from cortes.render.corte import (
    ARQUIVO,
    cortes_do_episodio,
    gravar_corte,
    ler_corte,
    novo_corte,
    pasta_corte,
    reenfileirar,
    video,
)
from cortes.render.montagem import FORMATOS


class PedidoRender(BaseModel):
    formato: str | None = None   # None: o formato do corte, ou o do episódio se o corte é novo


def resumo_render(pasta: Path) -> dict[str, Any]:
    cs = cortes_do_episodio(pasta)
    rodando = next((c.indice for c in cs if c.status == "renderizando"), None)
    return {"prontos": sum(c.status == "pronto" for c in cs), "total": len(cs), "rodando": rodando,
            "erros": sum(c.status == "erro" for c in cs)}


def cortes_json(pasta: Path) -> list[dict[str, Any]]:
    return [{**asdict(c), "video": f"/api/episodios/{pasta.name}/cortes/{c.indice}/video" if c.versao else None}
            for c in cortes_do_episodio(pasta)]


def pedir_render(pasta: Path, indice: int, formato: str | None) -> None:
    e = ler(pasta)
    if e.etapas["momentos"].situacao != "ok":
        raise ErroProducao(f"episódio {e.id} ainda não tem os momentos; espere a etapa terminar")
    cands = curadoria.candidatos(pasta)
    if not 0 <= indice < len(cands):
        raise ErroProducao(f"candidato {indice} não existe (o episódio tem {len(cands)})")
    if formato is not None and formato not in FORMATOS:
        raise ErroProducao(f"formato '{formato}' ainda não renderiza; use um de {FORMATOS}")
    d = pasta_corte(pasta, indice)
    if (d / ARQUIVO).exists():
        atual = ler_corte(d)
        gravar_corte(d, reenfileirar(atual, formato or atual.formato))
    else:
        gravar_corte(d, novo_corte(indice, cands[indice], formato or e.formato))


def montar(app: FastAPI, pasta_de: Callable[[str], Path], fila: Fila, escrita: threading.Lock) -> None:
    @app.post("/api/episodios/{id}/cortes/{indice}/renderizar", status_code=202)
    def api_renderizar(id: str, indice: int, pedido: PedidoRender) -> dict[str, bool]:
        pasta = pasta_de(id)
        with escrita:
            pedir_render(pasta, indice, pedido.formato)
        fila.enfileirar(id)
        return {"enfileirado": True}

    @app.get("/api/episodios/{id}/cortes/{indice}/video")
    def api_video_corte(id: str, indice: int, baixar: bool = False) -> FileResponse:
        pasta = pasta_de(id)
        d = pasta_corte(pasta, indice)
        if not (d / ARQUIVO).exists():
            raise ErroProducao(f"corte {indice} não existe")
        c = ler_corte(d)
        arq = video(pasta, c)
        if arq is None or not arq.exists():
            raise ErroProducao(f"corte {indice} ainda sem vídeo")
        return FileResponse(arq, media_type="video/mp4", filename=f"{id}-{indice}-v{c.versao}.mp4" if baixar else None)
```

Corrida: o corte só é tocado pela fila enquanto está `na_fila`/`renderizando`, e `reenfileirar` recusa justamente esses dois. A rota e a fila nunca escrevem o mesmo `corte.json` ao mesmo tempo.

- [ ] **Step 4: Ligar em `src/cortes/producao/rotas.py`**

- Troque `FORMATOS_RENDER = ("f7", "f1")   # planos D e E acrescentam f4 e f3` por `FORMATOS_RENDER = FORMATOS   # render/montagem.py; planos D e E acrescentam f4 e f3`, com `from cortes.render.montagem import FORMATOS`.
- Acrescente `from cortes.producao import rotas_cortes` e `from cortes.render.corte import cortes_do_episodio`.
- Em `_resumo`, acrescente a chave `"render": rotas_cortes.resumo_render(pasta)`.
- Em `api_episodio`:

```python
        pasta = _pasta(raiz, id)
        feitas = curadoria.decisoes(pasta)
        status = {c.indice: c.status for c in cortes_do_episodio(pasta)}
        cands = [{**c, "indice": i, "decisao": feitas.get(i, {}).get("decisao"), "corte": status.get(i)}
                 for i, c in enumerate(_candidatos(pasta))]
        return jsonable_encoder({**_resumo(pasta), "rubrica": list(CRITERIOS), "motivos": curadoria.MOTIVOS,
                                 "candidatos": cands, "cortes": rotas_cortes.cortes_json(pasta)})
```

- Em `montar`, depois de `_rota_transcricao(...)`: `rotas_cortes.montar(app, lambda id: _pasta(raiz, id), fila, escrita)`.

- [ ] **Step 5: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_producao_rotas_cortes.py tests/test_producao_rotas.py -q`
Esperado: todos passam.

- [ ] **Step 6: Check e commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
git add src/cortes/producao tests/test_producao_rotas_cortes.py
git commit -m "feat: API dos Shorts — renderizar candidato, vídeo do corte e resumo do render"
```

---

### Task 13: Tela — grade de Shorts, player, Renderizar, baixar

**Files:**
- Create: `web/static/js/grade.js`
- Modify: `web/static/js/episodio.js`, `web/static/js/episodios.js`, `web/static/index.html`, `web/static/painel.css`

- [ ] **Step 1: `web/static/js/grade.js`**

```js
"use strict";
// Grade de Shorts do episódio (plano B): um cartão 9:16 por corte, com nota, formato, status do
// render e a decisão da curadoria — que é por índice do candidato, o mesmo índice do corte.
const NOMES_STATUS = { na_fila: "na fila", renderizando: "renderizando…", pronto: "pronto", erro: "erro no render" };

function htmlCartao(D, k) {
  const c = D.candidatos.find(x => x.indice === k.indice);
  const midia = k.video
    ? `<video src="${esc(k.video)}" preload="metadata" muted playsinline></video>`
    : `<div class="sem-video">${esc(NOMES_STATUS[k.status])}</div>`;
  return `<div class="short ${k.indice === candSel ? "sel" : ""}" data-cand="${k.indice}" tabindex="0" role="button" aria-pressed="${k.indice === candSel}">
    ${midia}
    <div class="short-info">
      <div><span class="n">${nota10(c.nota_final)}</span><span class="chip f">${esc(k.formato)}</span>
        <span class="status ${esc(k.status)}">${esc(NOMES_STATUS[k.status])}</span></div>
      <div class="t">${esc(k.titulo)}</div>
      ${c.decisao ? `<span class="decisao ${esc(c.decisao)}">${esc(c.decisao)}</span>` : ""}
    </div></div>`;
}

function htmlGrade(D) {
  if (!D.cortes.length) return "";
  return `<div class="secao"><h2>Shorts</h2><span class="num">${D.render.prontos}/${D.render.total} prontos</span></div>
    <div class="grade">${D.cortes.map(k => htmlCartao(D, k)).join("")}</div>`;
}
```

- [ ] **Step 2: `index.html`** — carregar a grade antes do detalhe

```html
<script src="js/grade.js"></script>
<script src="js/episodio.js"></script>
```

- [ ] **Step 3: `episodio.js`** — Renderizar na tabela, Short no painel

Atualize o comentário do topo: no plano B, o painel toca o Short renderizado quando existe; sem Short, toca o trecho do vídeo original como antes.

Acrescente, depois de `rubPct`:

```js
const NOMES_CORTE = { na_fila: "na fila do render", renderizando: "renderizando…", pronto: "Short pronto", erro: "erro no render" };
const corteDe = (D, indice) => D.cortes.find(k => k.indice === indice);

function htmlAcaoRender(c) {
  return c.corte ? `<span class="chip">${esc(NOMES_CORTE[c.corte])}</span>`
    : `<button class="botao mini" data-renderizar="${c.indice}">Renderizar</button>`;
}
```

Em `htmlCandidatos`, troque `<div><div class="t">${esc(c.titulo)}</div><div class="j">${esc(c.justificativa)}</div></div>` por:

```js
      <div><div class="t">${esc(c.titulo)}</div><div class="j">${esc(c.justificativa)}</div><div class="cand-render">${htmlAcaoRender(c)}</div></div>
```

Em `htmlPainel(D, c)`, troque a linha do `<video class="trecho" ...>` por `${htmlMidia(D, c)}` e acrescente:

```js
function htmlMidia(D, c) {
  const k = corteDe(D, c.indice);
  const erro = k?.status === "erro"
    ? `<p class="erro-txt" title="${esc(k.erro)}">${esc(k.erro)}</p><button class="botao mini" data-renderizar="${c.indice}">tentar de novo</button>` : "";
  if (!k?.video) {
    return `<video class="trecho" controls preload="metadata" src="/api/episodios/${encodeURIComponent(D.id)}/video#t=${c.inicio},${c.fim}"></video>${erro}`;
  }
  return `<video class="short-video" controls preload="metadata" src="${esc(k.video)}"></video>${erro}
    <div class="short-acoes"><a class="botao mini" href="${esc(k.video)}?baixar=true">Baixar MP4</a>
      <button class="botao mini" data-copiar>Copiar título</button><span class="num">v${k.versao} · ${esc(k.formato)}</span></div>`;
}

async function pedirRender(D, indice, botao) {
  const meu = desenhar.n;
  botao.disabled = true;
  try {
    await post(`/api/episodios/${encodeURIComponent(D.id)}/cortes/${indice}/renderizar`, {});
    atualizarProducao();   // religa o polling: a fila tem trabalho de novo
    if (meu !== desenhar.n || D.id !== epSel) return;
    await blocoEpisodio(D.id, desenhar.n);
  } catch (e) {
    if (meu !== desenhar.n || D.id !== epSel) return;
    avisar(e.message);
    botao.disabled = false;
  }
}
```

Em `ligarPainel(D, c)`, troque a última linha `ligarVideo($("video.trecho", painel), c);` por:

```js
  const trecho = $("video.trecho", painel);
  if (trecho) ligarVideo(trecho, c);
  const copiar = $("[data-copiar]", painel);
  if (copiar) copiar.onclick = () => navigator.clipboard.writeText(c.titulo).then(() => avisar("título copiado"));
```

Em `blocoEpisodio`, monte o detalhe com a grade antes da tabela:

```js
  alvo.innerHTML = `<div class="detalhe"><div>${htmlGrade(D)}<div class="secao"><h2>Candidatos <em>— ${esc(D.titulo ?? id)}</em></h2>
    <span class="num">${D.candidatos.length} momentos · nota = rubrica do detector (0–10)</span></div>${htmlCandidatos(D)}</div>
    ${htmlPainel(D, c)}</div>`;
```

Logo depois do laço `$$("[data-cand]", alvo).forEach(...)`, que já liga os cartões da grade porque eles usam o mesmo `data-cand`:

```js
  $$("[data-renderizar]", alvo).forEach(b => {
    b.onclick = ev => { ev.stopPropagation(); pedirRender(D, Number(b.dataset.renderizar), b); };
  });
```

- [ ] **Step 4: `episodios.js`** — etapa render k/N e redesenho no progresso

```js
const NOMES_ETAPA = { video: "vídeo", legenda: "transcrição", sinais: "sinais", momentos: "momentos", render: "render" };
```

Em `htmlEtapas`, troque a linha do `rotulo` por:

```js
    const rotulo = et.situacao === "erro" ? "erro"
      : nome === "render" && ep.render?.total ? `render ${ep.render.prontos}/${ep.render.total}` : NOMES_ETAPA[nome];
```

Em `atualizarProducao`, a assinatura do detalhe passa a incluir o progresso do render. Sem isso, o cartão fica em "renderizando…" até outra etapa mudar.

```js
    const assinatura = ep => ep ? JSON.stringify([ep.etapas, ep.render]) : undefined;
    const antes = epSel ? assinatura(anteriorP?.episodios.find(e => e.id === epSel)) : undefined;
    const depois = epSel ? assinatura(P.episodios.find(e => e.id === epSel)) : undefined;
```

Atualize o comentário acima ("a ASSINATURA inteira de `etapas` e do resumo do render").

- [ ] **Step 5: `painel.css`**

```css
/* Grade de Shorts (plano B): cartões 9:16; o vídeo só carrega metadados até Davi abrir no painel. */
.grade { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; margin-bottom: 22px; }
.short { background: var(--surface); border: 1px solid var(--line-soft); border-radius: 12px; overflow: hidden; cursor: pointer; min-width: 0; }
.short.sel { box-shadow: inset 0 0 0 2px var(--up); }
.short:focus-visible { outline: 1px solid var(--up); outline-offset: 2px; }
.short video, .short .sem-video { width: 100%; aspect-ratio: 9/16; display: block; background: #000; object-fit: cover; }
.short .sem-video { display: grid; place-items: center; font: 11px var(--mono); color: var(--faint); }
.short-info { padding: 9px 10px; display: grid; gap: 5px; }
.short-info > div:first-child { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.short-info .n { font: 400 18px var(--serif); }
.short-info .t { font-weight: 600; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.short-info .status { font: 10.5px var(--mono); color: var(--muted); }
.short-info .status.erro { color: var(--warn); }
.short-info .decisao { font: 500 10.5px var(--mono); }
.short-info .decisao.aprovado { color: var(--ok); }
.short-info .decisao.rejeitado { color: var(--warn); }
.cand-render { margin-top: 6px; }
video.short-video { width: 100%; max-height: 70vh; aspect-ratio: 9/16; border-radius: 10px; background: #000; display: block; }
.short-acoes { display: flex; gap: 8px; align-items: center; margin-top: 10px; flex-wrap: wrap; }
```

- [ ] **Step 6: Conferir no navegador**

Suba o painel (`.venv/Scripts/cortes painel`), abra `http://127.0.0.1:8790` na aba Episódios e escolha um episódio com momentos. Confira:

- a barra de etapas mostra `render k/N`;
- a grade aparece com os cartões e o status muda sozinho de "na fila" para "renderizando…" e depois "pronto";
- o cartão pronto abre o Short 9:16 no painel;
- "Baixar MP4" salva o arquivo;
- "Copiar título" funciona;
- "Renderizar" num candidato fora dos N cria o cartão "na fila";
- não aparece erro no console (`read_console_messages`).

Teste também em largura de celular (375 px): a grade não pode estourar na horizontal.

- [ ] **Step 7: Check e commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
git add web/static
git commit -m "feat: grade de Shorts com player, Renderizar, baixar MP4 e render k/N na barra"
```

---

### Task 14: Título do corte na ligação, render real e spec

**Files:**
- Modify: `src/cortes/painel/ligacao.py`
- Test: `tests/test_painel_ligacao.py`
- Create: `tests/test_render_lento.py`
- Modify: `docs/superpowers/specs/2026-10-02-producao-design.md`

- [ ] **Step 1: Teste da ligação pelo título**

Em `tests/test_painel_ligacao.py`:

```python
def test_corte_de_episodio_usa_o_titulo_do_corte_json(tmp_path: Path) -> None:
    from cortes.render.corte import gravar_corte, novo_corte, pasta_corte
    ep = tmp_path / "episodios" / "abcdefghijk"
    ep.mkdir(parents=True)
    (ep / "meta.json").write_text('{"canal": "PrimoCast"}', encoding="utf-8")
    gravar_corte(pasta_corte(ep, 3), novo_corte(3, {"inicio": 1, "fim": 30, "titulo": "O comediante que mais vende"}, "f7"))
    [c] = listar_cortes(tmp_path, {"f7"})
    assert (c.nome, c.formato, c.podcast) == ("O comediante que mais vende", "f7", "PrimoCast")
    assert sugerir("comediante que mais vende #shorts", [c])[0] == c
```

Run: `.venv/Scripts/python -m pytest tests/test_painel_ligacao.py -q` → FAIL (o nome sai `"3"`).

- [ ] **Step 2: Implementar em `src/cortes/painel/ligacao.py`**

Troque, na docstring do módulo, o parágrafo "Limite conhecido..." por: "Cortes em `episodios/*/cortes/<n>` usam o título do `corte.json` como nome, para casar com o título do Short. A tela sempre pede confirmação antes de ligar." Depois acrescente:

```python
def _corte_de_episodio(raiz: Path, pasta: Path, formatos: Collection[str], podcast: str) -> CorteConhecido:
    if not (pasta / ARQUIVO).exists():
        return _corte(raiz, pasta, formatos, podcast)
    try:
        c = ler_corte(pasta)
    except ErroProducao as ex:
        raise ErroPainel(str(ex)) from ex
    return CorteConhecido(pasta.relative_to(raiz).as_posix(), c.titulo,
                          c.formato if c.formato in formatos else None, podcast)
```

Os imports são `from cortes.producao.estado import ErroProducao` e `from cortes.render.corte import ARQUIVO, ler_corte`. Em `listar_cortes`, troque `cortes.append(_corte(raiz, p, formatos, podcast))` (o do laço de episódios) por `cortes.append(_corte_de_episodio(raiz, p, formatos, podcast))`.

Run: `.venv/Scripts/python -m pytest tests/test_painel_ligacao.py -q` → passa.

- [ ] **Step 3: Teste lento, com render real de um corte do PrimoCast 536**

`tests/test_render_lento.py`:

```python
"""Render de verdade (ffmpeg + rosto no ComfyUI + HyperFrames): 1–4 min. Fora do check padrão."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from cortes.cli import MODELO_ROSTO, PY_VISAO
from cortes.render.corte import novo_corte
from cortes.render.pipeline import DepRender, renderizar_corte

REPO = Path(__file__).resolve().parents[1]
EP = REPO / "episodios" / "c5xqNNWFT9w"


@pytest.mark.lento
@pytest.mark.skipif(not (EP / "candidatos.json").exists(), reason="episódio de referência não baixado")
def test_render_real_do_comediante(tmp_path: Path) -> None:
    pasta = tmp_path / "episodios" / "c5xqNNWFT9w"
    pasta.mkdir(parents=True)
    for arq in ("video.mp4", "audio.wav", "palavras.json"):
        os.link(EP / arq, pasta / arq)
    shutil.copytree(REPO / "render", tmp_path / "render")
    cand = next(c for c in json.loads((EP / "candidatos.json").read_text(encoding="utf-8"))
                if c["titulo"] == "O comediante que mais vende")
    npx = shutil.which("npx")
    assert npx
    renderizar_corte(pasta, novo_corte(0, cand, "f7"), tmp_path, DepRender(PY_VISAO, MODELO_ROSTO, npx))
    mp4 = pasta / "cortes" / "0" / "short-v1.mp4"
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(mp4)], capture_output=True, text=True, check=True).stdout)
    segs = json.loads((pasta / "cortes" / "0" / "recorte.json").read_text(encoding="utf-8"))["segmentos"]
    assert abs(dur - sum(b - a for a, b in segs)) < 0.5
```

Se a pasta `episodios/c5xqNNWFT9w` usar Whisper (`palavras.json` do `cortes detectar`), o teste continua válido: ele só lê `texto/inicio/fim`.

Run: `.venv/Scripts/python -m pytest -m lento tests/test_render_lento.py -q` (demora minutos)
Esperado: 1 passed.

Se o HyperFrames reclamar do projeto (ex.: exigir `package.json` ou `meta.json`), acrescente em `criar_projeto` o arquivo mínimo que o erro pedir, com teste em `test_render_hyperframes.py`, e rode de novo. **Não** siga para o próximo passo com o lento falhando.

- [ ] **Step 4: Assistir**

Abra `short-v1.mp4` (caminho impresso pelo `tmp_path` do pytest, ou rode pelo painel na Task 13) e compare com `testes/d2-conversa-comediante/d2-conversa-comediante.mp4`. Pontos a conferir:

- enquadramento fixo por plano, com corte seco e flash na troca de câmera;
- pausas cortadas com zoom alternado na emenda;
- legenda sincronizada (com a legenda do YouTube, ±0,3 s é o esperado).

Mande o MP4 a Davi (SendUserFile) para o veredito.

- [ ] **Step 5: Spec**

Em `docs/superpowers/specs/2026-10-02-producao-design.md`:

- §4.1: troque `rosto.py         # rostos por quadro (até 3) + trocas de câmera` por `rosto.py         # enquadramento fixo por plano (puro) + chamada ao detector`. Acrescente `render/visao/rosto.py  # detector (Python do ComfyUI, fora do mypy)`, `corte.py`, `pipeline.py` e `processo.py`, e a nota "pausas pelo áudio (a legenda do YouTube não tem vão entre palavras)".
- §4.3: no `corte.json`, troque `status: na_fila | renderizando | pronto | aprovado | rejeitado (+ motivo)` por `status do render: na_fila | renderizando | pronto | erro (+ causa)`, com a nota "aprovado/rejeitado ficam em curadoria.json (índice do candidato = índice do corte)". Acrescente `recorte.json` (início/fim/segmentos: marcador de trecho e rosto prontos) e `cortes/planejado.json`.
- §4.4: "o render é a 5ª etapa do episódio; Renderizar manual reabre a etapa pelo gancho `antes` da fila".
- §3, linha do plano B: acrescente "pausas cortadas sempre; sem trilha (Davi, 2026-10-02)".

- [ ] **Step 6: Check e commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
git add src/cortes/painel/ligacao.py tests docs
git commit -m "feat: corte de episódio casa pelo título; render real testado; spec atualizada com o plano B"
```
