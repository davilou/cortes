# Produção C — Editor do Short

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um editor de três colunas para cada Short:
- **prévia 9:16:** o próprio projeto HyperFrames tocando no navegador;
- **transcrição palavra a palavra:** mover início e fim, corrigir o texto da legenda, mascarar palavrão, com aviso quando o início depende de contexto;
- **ajustes:** título, formato, quem aparece por plano de câmera (com miniatura de cada rosto), renderizar e versões.

**Architecture:**
- **Edições:** ficam em `corte.json` (`edicoes`: legenda e mascaradas por índice global da palavra em `palavras.json`; rostos por plano) e são aplicadas pelo pipeline. Prévia e render geram o mesmo `index.html`.
- **Prévia:** o `index.html` do corte, servido pelo painel com o runtime do HyperFrames injetado, dentro de `<hyperframes-player>`.
- **Montagem da prévia:** roda numa thread própria (`Previas`), fora da fila do render. Recortar o trecho e medir o rosto leva de 10 a 30 s quando início ou fim mudam.
- **Quem aparece:** o detector de rosto passa a achar até 3 rostos por amostra (formato 2 do `rosto.json`). Cada plano agrupa os rostos em pessoas pela posição x, e o enquadramento usa a pessoa escolhida ou, por padrão, a mais confiável.

**Tech Stack:** Python 3.13 · FastAPI · ffmpeg · OpenSeeFace ONNX (venv do ComfyUI) · `@hyperframes/player` e `@hyperframes/core` 0.8.104 (jsDelivr) · pytest · ruff · mypy --strict · JS puro

**Spec:** `docs/superpowers/specs/2026-10-02-producao-design.md` (§3 plano C, §5 "Editor"). Base: plano B (`docs/superpowers/plans/2026-10-02-producao-B.md`), já implementado nesta branch.

## Decisões (Davi, 2026-10-02)

- **Plano único:** o editor completo, incluindo "quem aparece" com vários rostos.
- **Prévia fora da fila:** uma thread só para prévias. Ela não espera atrás dos renders.
- **Palavrão:** clicar numa palavra alterna o mascaramento, e o botão "Mascarar palavrões" aplica uma lista fixa.

## Decisões de desenho deste plano

1. **Legenda editável por palavra.** Isso cobre corrigir nome ou número, juntar palavras (editar uma e apagar a outra com texto vazio) e apagar. A quebra manual de grupo fica fora; os grupos continuam saindo da regra de `legenda.grupos`.
2. **Edição recusada enquanto o corte está `na_fila`/`renderizando` ou com a prévia sendo preparada.** E vice-versa: "Renderizar" é recusado com a prévia em preparo. Assim nunca há dois escritores no mesmo `projeto/`.
3. **Mudar início ou fim zera as escolhas de rosto.** Os planos de câmera mudam com o trecho; a escolha antiga apontaria para outro plano.
4. **"Editar" só existe para candidato que já tem corte** (`corte.json`), ou seja, que foi renderizado ou pedido.
5. **`alterado` no `corte.json`:** fica `true` quando há edição ainda não renderizada e volta a `false` no `concluir`.
6. **Situação da prévia depois de reiniciar o painel:** a memória da thread se perde. Vale o disco: se o `projeto/index.html` é mais novo que o `corte.json`, a prévia está "pronta"; se é mais velho, "desatualizada"; sem o arquivo, "ausente". A tela pede a prévia sozinha nos dois últimos casos.

## Fatos verificados que este plano usa

- **Teste da prévia (2026-10-02):** `npx hyperframes@0.8.104 play` serve a página com `<hyperframes-player src="/composition/index.html" controls>` e `<script src="/player.js">`. Rodado no `testes/d2-conversa-comediante`, o player tocou no navegador: `seek(10.9)`, depois `play()`, e o `currentTime` foi a 12,65 s, com legenda e troca de câmera e sem erro no console.
  - O `/composition/index.html` servido é o `index.html` original com **uma** diferença: `<script src="/runtime.js"></script>` logo depois de `<head>`.
  - O `runtime.js` é byte a byte igual a `https://cdn.jsdelivr.net/npm/@hyperframes/core@0.8.104/dist/hyperframe.runtime.iife.js` (mesmo md5).
  - O player está em `https://cdn.jsdelivr.net/npm/@hyperframes/player@0.8.104/dist/hyperframes-player.global.js`.
  - O elemento expõe `play()`, `pause()`, `seek(t)`, `currentTime`, `duration`, `paused` e `ready`. A composição pede `assets/trecho.mp4` relativo ao `index.html`.
- **Saída do detector OpenSeeFace (`mnv3_detection_opt.onnx`):** `saida[0,0]` é o mapa de calor 56×56, `saida[0,1]` é o raio (×112 dá pixels em 224), e o `maxpool` marca os picos locais. É o mesmo `detect_faces` do OpenSeeFace, que pega os N maiores picos acima do limiar.
- **Estado atual (plano B):**
  - `render/rosto.py`: `Rosto(largura, altura, pontos, cortes)`; `trilha_fixa(r)` faz a mediana por intervalo entre `cortes` reais.
  - `render/visao/rosto.py`: grava `{"largura","altura","pontos":[{t,x,y,corte}],"cortes"}`.
  - `pipeline.preparar_trecho`: o cache `recorte.json` exige `trecho.mp4` e `rosto.json`.
  - `rotas_cortes.montar(app, pasta_de, fila, escrita)`.
  - `servidor.criar_app(cfg, executar, abrir, agora, fila)` monta `rotas_producao.montar(app, cfg.raiz, fila, escrita, agora)`.
  - `ErroRender` **não** tem handler no servidor (vira 500).
- `cortes.regra_inicio.comeca_no_meio(texto) -> bool`: conectivo de continuação no começo.
- **Roteamento da tela** (`web/static/js/inicio.js` `desenhar`): `TELAS[location.hash.slice(1)]`, sem parâmetros. Globais úteis: `$`, `$$`, `esc`, `api`, `post`, `avisar`, `desenhar.n`, `carregar`, `E` (base.js); `tempo`, `NOMES_CORTE` (episodio.js); `atualizarProducao` (episodios.js); `nomeFormato` (base.js).
- **Check:** `.venv/Scripts/python -m ruff check src tests`, `.venv/Scripts/python -m mypy src`, `.venv/Scripts/python -m pytest -q`.
  - No worktree `Cortes-producao-b`: `PY="../Cortes/.venv/Scripts/python"; PYTHONPATH=src $PY -m ...`, rodando de dentro do worktree.

## Estrutura de arquivos

```
render/visao/rosto.py               # (mod) até 3 rostos por amostra, formato 2
src/cortes/render/rosto.py          # (mod) Face/Amostra/Pessoa/Plano, planos(), trilha_fixa(r, escolhas)
src/cortes/render/corte.py          # (mod) Edicoes, alterado
src/cortes/render/edicao.py         # (novo) mascarar, palavrões, palavras_editadas, Edicao, aplicar
src/cortes/render/montagem.py       # (mod) valores(..., escolhas)
src/cortes/render/pipeline.py       # (mod) aplica edições; montar_projeto; cache exige formato 2
src/cortes/render/miniatura.py      # (novo) quadro recortado em volta de um rosto
src/cortes/render/previa.py         # (novo) runtime injetado no index.html
src/cortes/producao/previas.py      # (novo) thread de prévias
src/cortes/producao/rotas_editor.py # (novo) API do editor
src/cortes/producao/rotas_cortes.py # (mod) renderizar recusa com prévia em preparo; vídeo por versão
src/cortes/producao/rotas.py        # (mod) monta rotas_editor
src/cortes/painel/servidor.py       # (mod) Previas, DepRender único, handler de ErroRender
web/static/js/editor.js             # (novo) tela do editor
web/static/js/transcricao.js        # (novo) coluna de palavras
web/static/js/planos.js             # (novo) quem aparece
web/static/js/inicio.js, episodio.js, index.html, painel.css  # (mod)
```

---

### Task 1: Detector com até 3 rostos por amostra

**Files:**
- Modify: `render/visao/rosto.py`

- [ ] **Step 1: Reescrever `detectar`, `amostrar` e `main`**

Substitua o docstring do módulo e as funções `detectar`, `amostrar` e `main` por este código. `cortes_de_camera`, `_cortes_validos`, as constantes e os imports continuam:

```python
"""Rostos por amostra de um trecho (até 3), cientes de troca de câmera.

Roda no Python do ComfyUI (tem cv2 e onnxruntime); o app chama por subprocesso
(src/cortes/render/rosto.py). Portado de testes/comum/rosto.py.

Uso: <python com onnxruntime> rosto.py <trecho.mp4> <modelo.onnx> <saida.json>
Grava (formato 2):
  {"formato": 2, "largura", "altura", "cortes": [instantes reais das trocas de câmera],
   "amostras": [{"t", "rostos": [{"x", "y", "r", "conf"}]}]}
em pixels da fonte; `r` é o raio do rosto. Até MAX_ROSTOS por amostra, como o `detect_faces` do
OpenSeeFace: os maiores picos do mapa de calor acima do limiar. Rosto em menos da metade das
amostras → sai com código 1 e a causa no stderr (trilha não confiável).
"""
```

```python
MAX_ROSTOS = 3


def detectar(frame: np.ndarray, sessao: ort.InferenceSession) -> list[dict]:
    altura, largura = frame.shape[:2]
    im = cv2.resize(frame, (224, 224), interpolation=cv2.INTER_LINEAR)[:, :, ::-1] * _STD + _MEAN
    saida, maxpool = sessao.run([], {"input": np.transpose(im[None].astype(np.float32), (0, 3, 1, 2))})
    calor, raio = saida[0, 0], saida[0, 1]
    picos = np.where(calor == maxpool[0, 0], calor, 0)
    rostos: list[dict] = []
    for k in np.argsort(picos.ravel())[::-1][:MAX_ROSTOS]:
        conf = float(picos.flat[k])
        if conf < LIMIAR:
            break
        y, x = divmod(int(k), 56)
        r = float(raio[y, x]) * 112
        rostos.append({"x": round(x * 4 * largura / 224), "y": round(y * 4 * altura / 224),
                       "r": round(r * largura / 224), "conf": round(conf, 3)})
    return rostos


def amostrar(video: Path, sessao: ort.InferenceSession, cortes: list[float]) -> tuple[int, int, list[dict]]:
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    largura, altura = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    tempos = sorted({round(k * PASSO_S, 3) for k in range(int(dur / PASSO_S))}
                    | {round(c + 0.05, 3) for c in cortes})
    amostras: list[dict] = []
    for t in tempos:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, frame = cap.read()
        amostras.append({"t": round(t, 2), "rostos": detectar(frame, sessao) if ok else []})
    return largura, altura, amostras


def main() -> None:
    trecho, modelo, saida = (Path(a) for a in sys.argv[1:4])
    sessao = ort.InferenceSession(str(modelo), providers=["CPUExecutionProvider"])
    cortes = cortes_de_camera(trecho)
    largura, altura, amostras = amostrar(trecho, sessao, cortes)
    com_rosto = sum(1 for a in amostras if a["rostos"])
    if com_rosto < 0.5 * len(amostras):
        sys.exit(f"rosto em só {com_rosto} de {len(amostras)} amostras — trilha não confiável")
    saida.write_text(json.dumps({"formato": 2, "largura": largura, "altura": altura, "cortes": cortes,
                                 "amostras": amostras}), encoding="utf-8")
    varios = sum(1 for a in amostras if len(a["rostos"]) > 1)
    print(f"rosto em {com_rosto}/{len(amostras)} amostras; {varios} com 2+ rostos; {len(cortes)} trocas de câmera")
```

- [ ] **Step 2: Conferir num trecho real**

```bash
"C:/Users/User/Documents/IA Local/ComfyUI/venv/Scripts/python.exe" render/visao/rosto.py ../Cortes/testes/f7-conversa-comediante/assets/trecho.mp4 "C:/Users/User/Documents/IA Local/ComfyUI/custom_nodes/tts_audio_suite/engines/video/openseeface/models/mnv3_detection_opt.onnx" "$TEMP/rosto-v2.json"
head -c 400 "$TEMP/rosto-v2.json"
```

Esperado: `rosto em N/M amostras; K com 2+ rostos; 2 trocas de câmera`, e o JSON começa com `{"formato": 2, "largura": 1920, "altura": 1080, "cortes": [`. Anote o K no relatório: pode ser 0 num trecho só de close, e isso não é erro.

- [ ] **Step 3: Commit**

```bash
git add render/visao/rosto.py
git commit -m "feat: detector acha até 3 rostos por amostra (rosto.json formato 2)"
```

---

### Task 2: Pessoas por plano e enquadramento com escolha

**Files:**
- Modify: `src/cortes/render/rosto.py` (reescrita)
- Test: `tests/test_render_rosto.py` (reescrita)

- [ ] **Step 1: Escrever os testes**

Substitua `tests/test_render_rosto.py` inteiro:

```python
import json
from pathlib import Path

import pytest

from cortes.render.processo import ErroRender
from cortes.render.rosto import (
    Amostra,
    Face,
    Rosto,
    largura_quadro,
    ler_rosto,
    medir_rosto,
    pessoas,
    planos,
    trilha_fixa,
)


def F(x: float, y: float) -> Face:
    return Face(x, y, 80.0, 0.9)


R = Rosto(1920, 1080, (
    Amostra(0.0, (F(960, 540),)), Amostra(0.25, (F(980, 540),)), Amostra(1.9, ()),
    Amostra(2.0, (F(1800, 500), F(400, 520))), Amostra(2.25, (F(1800, 520), F(420, 500))),
    Amostra(2.5, (F(1790, 510),)),
), (1.9,))


def test_pessoas_separam_pela_posicao_x() -> None:
    ps = pessoas([F(1800, 500), F(400, 520), F(1800, 520), F(420, 500), F(1790, 510)], 1920)
    assert [(p.x, p.n) for p in ps] == [(410.0, 2), (1800.0, 3)]


def test_pessoa_com_poucas_deteccoes_e_ruido() -> None:
    ps = pessoas([F(900, 500)] * 10 + [F(100, 500)], 1920)
    assert [p.x for p in ps] == [900.0]


def test_planos_e_padrao() -> None:
    pl = planos(R)
    assert [(p.k, p.ini, len(p.pessoas), p.padrao) for p in pl] == [(0, 0.0, 1, 0), (1, 1.9, 2, 1)]
    assert pl[1].fim == 2.75


def test_trilha_fixa_padrao_e_escolha() -> None:
    assert trilha_fixa(R, {}) == [[0.0, -1184.4, 0.0, 1], [1.9, -2333.3, 0.0, 1]]
    assert trilha_fixa(R, {1: 0}) == [[0.0, -1184.4, 0.0, 1], [1.9, -188.9, 0.0, 1]]
    assert largura_quadro(R) == 3413


def test_escolha_inexistente_e_erro() -> None:
    with pytest.raises(ErroRender, match="pessoa 5"):
        trilha_fixa(R, {1: 5})


def test_plano_sem_rosto_herda_o_anterior() -> None:
    r = Rosto(1920, 1080, (Amostra(0.0, (F(960, 540),)), Amostra(1.5, ()), Amostra(2.2, (F(1800, 500),))),
              (1.0, 2.0))
    assert [t[1] for t in trilha_fixa(r, {})] == [-1166.7, -1166.7, -2333.3]


def test_ler_rosto_formato_2(tmp_path: Path) -> None:
    arq = tmp_path / "rosto.json"
    arq.write_text(json.dumps({"formato": 2, "largura": 1920, "altura": 1080, "cortes": [1.9],
                               "amostras": [{"t": 0.0, "rostos": [{"x": 960, "y": 540, "r": 80, "conf": 0.9}]},
                                            {"t": 2.0, "rostos": []}]}), encoding="utf-8")
    assert ler_rosto(arq) == Rosto(1920, 1080, (Amostra(0.0, (Face(960, 540, 80, 0.9),)), Amostra(2.0, ())), (1.9,))


@pytest.mark.parametrize("dados, erro", [
    ({"largura": 1920, "altura": 1080, "pontos": [], "cortes": []}, "formato"),
    ({"formato": 2, "largura": 1920, "altura": 1080, "cortes": [], "amostras": [{"t": 0.0, "rostos": []}]},
     "nenhuma amostra"),
    ({"formato": 2, "largura": 1920, "altura": 1080, "cortes": [2.0, 1.0], "amostras": []}, "cortes"),
])
def test_ler_rosto_invalido(tmp_path: Path, dados: dict[str, object], erro: str) -> None:
    arq = tmp_path / "rosto.json"
    arq.write_text(json.dumps(dados), encoding="utf-8")
    with pytest.raises(ErroRender, match=erro):
        ler_rosto(arq)


def test_medir_rosto_chama_o_python_da_visao() -> None:
    vistos: list[list[str]] = []

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        vistos.append(args)
        return 0, ""

    medir_rosto(Path("t.mp4"), Path("r.json"), Path("rosto.py"), Path("py.exe"), Path("m.onnx"), rodar)
    assert vistos == [["py.exe", "rosto.py", "t.mp4", "m.onnx", "r.json"]]
```

Contas:
- **Plano 1:** as pessoas ficam em x 400/420 (n=2) e 1790/1800/1800 (n=3). O vão entre 420 e 1790 é maior que 0,08 × 1920 = 153,6. O padrão é a de n=3 (índice 1, porque a ordem é da esquerda para a direita). A mediana x = 1800 dá −2333,3; a escolha 0 dá x = 410 → 540 − 410 × 1,7778 = −188,9.
- **Ruído:** n=1 contra n=10, e 1 < 0,2 × 10.
- **`fim` do último plano:** última amostra 2,5 + passo 0,25 = 2,75.
- **Herança:** o plano [1,0; 2,0) não tem rosto e herda x = 960 → 540 − 1706,7 = −1166,7.

- [ ] **Step 2: Rodar e ver falhar**

Run: `PYTHONPATH=src $PY -m pytest tests/test_render_rosto.py -q` (no worktree). Esperado: FAIL (`ImportError`).

- [ ] **Step 3: Reescrever `src/cortes/render/rosto.py`**

```python
"""Enquadramento do Short: posição FIXA por plano de câmera, na pessoa escolhida
(spec produção §4.1 e §5 "quem aparece"; testes/TEMPLATES.md).

Dentro de um plano a câmera virtual não se mexe (seguir o rosto o tempo todo deixou o espectador
tonto na rodada 1). Em cada plano — intervalo entre trocas reais de câmera — os rostos detectados
viram pessoas pela posição x (câmera parada: cada pessoa fica no seu lugar). O enquadramento usa
a pessoa escolhida no editor ou, por padrão, a mais confiável (mais detecções, depois maior
confiança). A detecção roda fora deste Python: render/visao/rosto.py, no venv do ComfyUI.
"""
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cortes.render.processo import ErroRender, Rodar, exigir

FORMATO_ROSTO = 2          # rosto.json com até 3 rostos por amostra (render/visao/rosto.py)
JANELA = (1080, 1920)
ALVO = (540, 700)          # onde o rosto fica na tela 9:16 (protótipo: CAM_CHEIO da rodada 1)
PASSO_S = 0.25             # passo da amostragem em render/visao/rosto.py
SEPARA = 0.08              # rostos a mais que isso (fração da largura) no eixo x são pessoas diferentes
RUIDO = 0.2                # pessoa com menos que isso × as detecções da maior é ruído do detector
MAX_PESSOAS = 3


@dataclass(frozen=True)
class Face:
    x: float
    y: float
    r: float
    conf: float


@dataclass(frozen=True)
class Amostra:
    t: float
    rostos: tuple[Face, ...]


@dataclass(frozen=True)
class Rosto:
    largura: int
    altura: int
    amostras: tuple[Amostra, ...]
    cortes: tuple[float, ...]   # instantes reais das trocas de câmera


@dataclass(frozen=True)
class Pessoa:
    x: float
    y: float
    r: float
    n: int
    conf: float


@dataclass(frozen=True)
class Plano:
    k: int
    ini: float
    fim: float
    pessoas: tuple[Pessoa, ...]   # da esquerda para a direita
    padrao: int | None            # índice da mais confiável; None sem rosto


def _numero(v: Any, nome: str) -> float:
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        raise ValueError(f"{nome} deveria ser número, veio {v!r}")
    return float(v)


def _face(f: Any) -> Face:
    if not isinstance(f, dict):
        raise ValueError(f"rosto inválido: {f!r}")
    return Face(*(_numero(f[c], c) for c in ("x", "y", "r", "conf")))


def _amostra(a: Any) -> Amostra:
    if not isinstance(a, dict) or not isinstance(a.get("rostos"), list):
        raise ValueError(f"amostra inválida: {a!r}")
    return Amostra(_numero(a["t"], "t"), tuple(_face(f) for f in a["rostos"]))


def _cortes(valores: Any) -> tuple[float, ...]:
    if not isinstance(valores, list):
        raise ValueError(f"cortes inválido: {valores!r}")
    cortes = tuple(_numero(v, "corte") for v in valores)
    if any(v < 0 for v in cortes) or any(a >= b for a, b in zip(cortes, cortes[1:], strict=False)):
        raise ValueError(f"cortes deveria ser crescente e não-negativo: {cortes!r}")
    return cortes


def ler_rosto(arquivo: Path) -> Rosto:
    try:
        d = json.loads(arquivo.read_text(encoding="utf-8"))
        if d.get("formato") != FORMATO_ROSTO:
            raise ValueError(f"formato {d.get('formato')!r}, esperado {FORMATO_ROSTO}: meça o rosto de novo")
        largura, altura = d["largura"], d["altura"]
        if not (isinstance(largura, int) and isinstance(altura, int) and largura > 0 and altura > 0):
            raise ValueError("largura/altura deveriam ser inteiros positivos")
        cortes = _cortes(d["cortes"])
        amostras = tuple(_amostra(a) for a in d["amostras"])
        if not any(a.rostos for a in amostras):
            raise ValueError("nenhuma amostra com rosto")
        return Rosto(largura, altura, amostras, cortes)
    except (OSError, KeyError, TypeError, ValueError) as ex:
        raise ErroRender(f"{arquivo}: rosto inválido ({ex})") from ex


def escala(r: Rosto) -> float:
    return JANELA[1] / r.altura


def largura_quadro(r: Rosto) -> int:
    return round(r.largura * escala(r))


def pessoas(faces: list[Face], largura: int) -> tuple[Pessoa, ...]:
    """Agrupa os rostos de um plano pela posição x; descarta o ruído; até MAX_PESSOAS."""
    if not faces:
        return ()
    fs = sorted(faces, key=lambda f: f.x)
    grupos: list[list[Face]] = [[fs[0]]]
    for f in fs[1:]:
        if f.x - grupos[-1][-1].x > SEPARA * largura:
            grupos.append([f])
        else:
            grupos[-1].append(f)
    ps = [Pessoa(statistics.median(f.x for f in g), statistics.median(f.y for f in g),
                 statistics.median(f.r for f in g), len(g), round(statistics.fmean(f.conf for f in g), 3))
          for g in grupos]
    maior = max(p.n for p in ps)
    ps = sorted((p for p in ps if p.n >= RUIDO * maior), key=lambda p: (-p.n, -p.conf))[:MAX_PESSOAS]
    return tuple(sorted(ps, key=lambda p: p.x))


def _padrao(ps: tuple[Pessoa, ...]) -> int | None:
    if not ps:
        return None
    return max(range(len(ps)), key=lambda i: (ps[i].n, ps[i].conf))


def planos(r: Rosto) -> list[Plano]:
    """Um plano por intervalo entre trocas reais de câmera: [0, c1), [c1, c2), …, [cN, fim)."""
    limites = [0.0, *r.cortes]
    fim_total = r.amostras[-1].t + PASSO_S if r.amostras else 0.0
    res: list[Plano] = []
    for k, ini in enumerate(limites):
        fim = limites[k + 1] if k + 1 < len(limites) else max(fim_total, ini)
        faces = [f for a in r.amostras if ini <= a.t < fim for f in a.rostos]
        ps = pessoas(faces, r.largura)
        res.append(Plano(k, ini, round(fim, 2), ps, _padrao(ps)))
    return res


def _escolhida(p: Plano, escolhas: dict[int, int]) -> Pessoa | None:
    if not p.pessoas:
        return None
    j = escolhas.get(p.k, p.padrao)
    if j is None or not 0 <= j < len(p.pessoas):
        raise ErroRender(f"plano {p.k}: pessoa {j} não existe (há {len(p.pessoas)})")
    return p.pessoas[j]


def trilha_fixa(r: Rosto, escolhas: dict[int, int]) -> list[list[float]]:
    """[t, x, y, 1] no início de cada plano: deslocamento do quadro (≤ 0) que leva a pessoa do plano
    ao ALVO sem mostrar borda. Plano sem rosto herda a posição do anterior (o primeiro, a do próximo
    com rosto); nenhum plano com rosto é erro. O 1 final pede corte seco ao template."""
    pls = planos(r)
    alvos = [_escolhida(p, escolhas) for p in pls]
    if all(a is None for a in alvos):
        raise ErroRender("nenhum plano de câmera tem rosto")
    for i in range(1, len(alvos)):
        alvos[i] = alvos[i] or alvos[i - 1]
    for i in range(len(alvos) - 2, -1, -1):
        alvos[i] = alvos[i] or alvos[i + 1]
    e = escala(r)
    jw, jh = JANELA
    qw, qh = r.largura * e, r.altura * e
    res: list[list[float]] = []
    for p, a in zip(pls, alvos, strict=True):
        assert a is not None
        res.append([p.ini, round(min(0.0, max(jw - qw, ALVO[0] - a.x * e)), 1),
                    round(min(0.0, max(jh - qh, ALVO[1] - a.y * e)), 1), 1])
    return res


def medir_rosto(
    trecho: Path, destino: Path, script: Path, py_visao: Path, modelo: Path, rodar: Rodar,
) -> None:
    args = [str(py_visao), str(script), str(trecho), str(modelo), str(destino)]
    exigir(rodar, args, None, "detecção de rosto")
```

- [ ] **Step 4: Ajustar os outros consumidores para o check passar**

- `src/cortes/render/montagem.py`: `valores(dur, rosto, grupos, cortes, escolhas: dict[int, int])`, chamando `trilha_fixa(rosto, escolhas)`.
- `src/cortes/render/pipeline.py` `_html`: passe `c.edicoes.rostos` se a Task 3 já tiver sido feita; por ora, passe `{}`.
- `_cache_valido` em `pipeline.py`: além de `trecho.mp4` e `rosto.json` existirem, o `rosto.json` precisa ser do formato atual. Faça `try: ler_rosto(d / "rosto.json") except ErroRender: return None`, com um comentário dizendo que um rosto.json velho (formato 1, do plano B) obriga a medir de novo. Teste novo em `tests/test_render_pipeline.py`: um `rosto.json` formato 1 com o marcador presente faz rodar `ffmpeg` e `py-visao` de novo.
- **Fixtures:** `tests/test_render_montagem.py` e `tests/test_render_pipeline.py` (o `ROSTO` do falso) passam a usar formato 2: `{"formato": 2, "largura": 1920, "altura": 1080, "cortes": [], "amostras": [{"t": 0.0, "rostos": [{"x": 960, "y": 540, "r": 80, "conf": 0.9}]}]}`. Em `test_render_montagem.py`, monte o `Rosto` com `Amostra`/`Face`.

- [ ] **Step 5: Rodar o check inteiro** e depois commitar.

```bash
git add src/cortes/render tests
git commit -m "feat: pessoas por plano e enquadramento na pessoa escolhida (rosto.json formato 2)"
```

---

### Task 3: Edições no corte.json

**Files:**
- Modify: `src/cortes/render/corte.py`
- Test: `tests/test_render_corte.py`

- [ ] **Step 1: Testes** (acrescente)

```python
from cortes.render.corte import Edicoes


def test_edicoes_vao_e_voltam_do_disco(tmp_path: Path) -> None:
    c = replace(novo_corte(2, CANDS[2], "f7"), edicoes=Edicoes({5: "ChatGPT", 6: ""}, (9,), {1: 0}), alterado=True)
    gravar_corte(pasta_corte(tmp_path, 2), c)
    assert ler_corte(pasta_corte(tmp_path, 2)) == c


def test_corte_do_plano_b_sem_edicoes_migra(tmp_path: Path) -> None:
    d = pasta_corte(tmp_path, 0)
    d.mkdir(parents=True)
    x = {"indice": 0, "inicio": 10.0, "fim": 40.0, "formato": "f7", "titulo": "A", "status": "na_fila",
         "versao": 0, "erro": None}
    (d / "corte.json").write_text(json.dumps(x), encoding="utf-8")
    c = ler_corte(d)
    assert c.edicoes == Edicoes() and c.alterado is False


def test_concluir_limpa_alterado() -> None:
    c = replace(iniciar(novo_corte(0, CANDS[0], "f7")), alterado=True)
    assert concluir(c).alterado is False


@pytest.mark.parametrize("edicoes", [
    {"legenda": {"x": "a"}, "mascaradas": [], "rostos": {}},
    {"legenda": {"1": 3}, "mascaradas": [], "rostos": {}},
    {"legenda": {}, "mascaradas": ["a"], "rostos": {}},
    {"legenda": {}, "mascaradas": [], "rostos": {"0": "a"}},
])
def test_edicoes_invalidas(tmp_path: Path, edicoes: dict[str, object]) -> None:
    d = pasta_corte(tmp_path, 0)
    gravar_corte(d, novo_corte(0, CANDS[0], "f7"))
    x = json.loads((d / "corte.json").read_text(encoding="utf-8"))
    (d / "corte.json").write_text(json.dumps({**x, "edicoes": edicoes}), encoding="utf-8")
    with pytest.raises(ErroProducao, match="edicoes"):
        ler_corte(d)
```

(acrescente `from dataclasses import replace` aos imports do arquivo de teste, se faltar)

- [ ] **Step 2: Ver falhar**, e depois implementar em `corte.py`:

```python
from dataclasses import asdict, dataclass, field, replace


@dataclass(frozen=True)
class Edicoes:
    """Edições do editor (plano C). Chaves de legenda/mascaradas são índices em palavras.json — não
    mudam quando início/fim mudam. Rostos: plano de câmera → pessoa (zera com novo início/fim)."""
    legenda: dict[int, str] = field(default_factory=dict)   # "" tira a palavra da legenda
    mascaradas: tuple[int, ...] = ()
    rostos: dict[int, int] = field(default_factory=dict)
```

`Corte` ganha, no fim:

```python
    edicoes: Edicoes = field(default_factory=Edicoes)
    alterado: bool = False     # edição salva e ainda não renderizada
```

`concluir`: `return replace(c, status="pronto", versao=c.versao + 1, erro=None, alterado=False)`.

Leitura (funções novas mais duas linhas em `ler_corte`):

```python
def _int(v: Any, onde: str) -> int:
    if isinstance(v, bool):
        raise ValueError(f"{onde}: {v!r} não é inteiro")
    try:
        return int(v)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{onde}: {v!r} não é inteiro") from ex


def _edicoes(x: Any) -> Edicoes:
    """Corte do plano B não tem 'edicoes': nasce sem edição (migração explícita de campo novo)."""
    if x is None:
        return Edicoes()
    if not isinstance(x, dict):
        raise ValueError("edicoes deveria ser um objeto")
    legenda = {_int(k, "edicoes.legenda"): v for k, v in x["legenda"].items()}
    if not all(isinstance(v, str) for v in legenda.values()):
        raise ValueError("edicoes.legenda: textos deveriam ser texto")
    mascaradas = tuple(sorted(_int(i, "edicoes.mascaradas") for i in x["mascaradas"]))
    rostos = {_int(k, "edicoes.rostos"): _int(v, "edicoes.rostos") for k, v in x["rostos"].items()}
    return Edicoes(legenda, mascaradas, rostos)
```

Em `ler_corte`, antes do `return`:

```python
        alterado = x.get("alterado", False)   # ausente: corte do plano B (migração)
        if not isinstance(alterado, bool):
            raise ValueError("campo 'alterado' deveria ser booleano")
```

Passe também `_edicoes(x.get("edicoes"))` e `alterado` ao construtor. Se `ler_corte` passar de 50 linhas, extraia a validação dos campos simples para uma função `_basicos(x, d)`.

- [ ] **Step 3: Check e commit**

```bash
git add src/cortes/render/corte.py tests/test_render_corte.py
git commit -m "feat: corte.json guarda as edições do editor e se há edição não renderizada"
```

---

### Task 4: Regras de edição (puro)

**Files:**
- Create: `src/cortes/render/edicao.py`
- Test: `tests/test_render_edicao.py`

- [ ] **Step 1: Testes**

```python
from dataclasses import replace

import pytest

from cortes.producao.estado import ErroProducao
from cortes.render.corte import Edicoes, novo_corte
from cortes.render.edicao import (
    Edicao,
    aplicar,
    eh_palavrao,
    indices_do_corte,
    mascarar,
    palavras_editadas,
)
from cortes.tipos import Palavra

TODAS = [Palavra(t, float(i), i + 0.8) for i, t in
         enumerate(["Antes.", "Mas", "eu", "perdi", "porra,", "tudo", "no", "chat", "GPT.", "Depois"])]
C = novo_corte(0, {"inicio": 1.0, "fim": 8.8, "titulo": "T"}, "f7")


@pytest.mark.parametrize("antes, depois", [
    ("porra,", "p*rra,"), ("Merda.", "M*rda."), ("cu", "c*"), ("123", "123")])
def test_mascarar(antes: str, depois: str) -> None:
    assert mascarar(antes) == depois


def test_eh_palavrao_ignora_caixa_acento_e_pontuacao() -> None:
    assert eh_palavrao("Porra,") and eh_palavrao("DESGRAÇA!") and not eh_palavrao("porta")


def test_indices_do_corte() -> None:
    assert indices_do_corte(TODAS, 1.0, 8.8) == (1, 8)
    with pytest.raises(ErroProducao, match="nenhuma palavra"):
        indices_do_corte(TODAS, 20.0, 30.0)


def test_palavras_editadas_troca_apaga_e_mascara() -> None:
    ws = palavras_editadas(TODAS, Edicoes({7: "ChatGPT.", 8: ""}, (4,), {}))
    assert [w.texto for w in ws][3:8] == ["perdi", "p*rra,", "tudo", "no", "ChatGPT."]
    assert len(ws) == 9


def test_mover_inicio_e_fim_por_palavra_zera_rostos() -> None:
    c = replace(C, edicoes=Edicoes(rostos={0: 1}))
    novo = aplicar(c, Edicao(inicio_palavra=2, fim_palavra=6), TODAS, [2])
    assert (novo.inicio, novo.fim, novo.edicoes.rostos, novo.alterado) == (2.0, 6.8, {}, True)


@pytest.mark.parametrize("ed, erro", [
    (Edicao(inicio_palavra=6, fim_palavra=2), "antes do fim"),
    (Edicao(inicio_palavra=99), "palavra 99"),
    (Edicao(inicio_palavra=3, fim_palavra=3), "duração"),
    (Edicao(titulo="  "), "título"),
    (Edicao(formato="f4"), "formato 'f4'"),
    (Edicao(rosto=(0, 2)), "pessoa 2"),
    (Edicao(rosto=(3, 0)), "plano 3"),
])
def test_edicao_recusada(ed: Edicao, erro: str) -> None:
    with pytest.raises(ErroProducao, match=erro):
        aplicar(C, ed, TODAS, [2])


def test_legenda_mascarar_e_palavroes() -> None:
    novo = aplicar(C, Edicao(legenda={7: "ChatGPT.", 8: "", 2: "eu"}, mascarar_palavroes=True), TODAS, [])
    assert novo.edicoes.legenda == {7: "ChatGPT.", 8: ""} and novo.edicoes.mascaradas == (4,)
    de_volta = aplicar(novo, Edicao(legenda={7: None}, mascarar={4: False}), TODAS, [])
    assert de_volta.edicoes.legenda == {8: ""} and de_volta.edicoes.mascaradas == ()


def test_sem_mudanca_nao_marca_alterado() -> None:
    assert aplicar(C, Edicao(titulo="T"), TODAS, []).alterado is False
    assert aplicar(C, Edicao(rosto=(0, 1)), TODAS, [2]).edicoes.rostos == {0: 1}
```

Contas:
- **Janela do corte:** C é [1,0; 8,8], então as palavras de índice 1 a 8 começam dentro dela.
- **Duração de 3 a 3:** 3,0 a 3,8 dá 0,8 s, menos que o mínimo de 3 s.
- **Mover início e fim** de 2 ("eu") a 6 ("no") dá [2,0; 6,8].
- **`legenda {2: "eu"}`** é igual ao original e não vira edição.

- [ ] **Step 2: Ver falhar e implementar `src/cortes/render/edicao.py`**

```python
"""Regras de edição do editor (plano C; spec produção §5): início/fim por palavra, texto da legenda,
mascarar palavrão (só na legenda), título, formato e quem aparece. Puro: recebe o corte e as
palavras do episódio e devolve o corte novo, ou ErroProducao com a causa."""
import re
import unicodedata
from dataclasses import dataclass, field, replace

from cortes.producao.estado import ErroProducao
from cortes.render.corte import Corte, Edicoes
from cortes.render.montagem import FORMATOS
from cortes.tipos import Palavra

DURACAO_MIN_S = 3.0
DURACAO_MAX_S = 180.0      # limite do Short no YouTube
TITULO_MAX = 100           # limite do título no YouTube
# Lista fixa (Davi, 2026-10-02): palavrões fortes que o protótipo mascarou e os comuns do português.
PALAVROES = frozenset({
    "porra", "merda", "puta", "puto", "caralho", "foda", "foder", "fodido", "fodeu", "cacete",
    "bosta", "buceta", "cu", "cagado", "cagada", "cagar", "desgraca", "desgracado", "arrombado",
})
_VOGAL = re.compile(r"(?<=\w)[aeiouáéíóúâêôãõà]", re.IGNORECASE)


@dataclass(frozen=True)
class Edicao:
    inicio_palavra: int | None = None
    fim_palavra: int | None = None
    titulo: str | None = None
    formato: str | None = None
    legenda: dict[int, str | None] = field(default_factory=dict)   # None volta ao original
    mascarar: dict[int, bool] = field(default_factory=dict)
    mascarar_palavroes: bool = False
    rosto: tuple[int, int] | None = None                           # (plano, pessoa)


def mascarar(texto: str) -> str:
    """Primeira vogal depois da primeira letra vira '*' (porra → p*rra), como a legenda dos protótipos."""
    return _VOGAL.sub("*", texto, count=1)


def _normal(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", sem_acento.lower())


def eh_palavrao(texto: str) -> bool:
    return _normal(texto) in PALAVROES


def indices_do_corte(todas: list[Palavra], inicio: float, fim: float) -> tuple[int, int]:
    """Primeira e última palavra que COMEÇAM no corte (mesma tolerância de legenda.palavras_do_corte)."""
    dentro = [i for i, p in enumerate(todas) if inicio - 0.01 <= p.inicio <= fim + 0.01]
    if not dentro:
        raise ErroProducao(f"nenhuma palavra entre {inicio:.2f}s e {fim:.2f}s")
    return dentro[0], dentro[-1]


def palavras_editadas(todas: list[Palavra], ed: Edicoes) -> list[Palavra]:
    """Texto da legenda com as edições: troca, mascara e tira as apagadas (texto vazio)."""
    res: list[Palavra] = []
    for i, p in enumerate(todas):
        texto = ed.legenda.get(i, p.texto)
        if i in ed.mascaradas:
            texto = mascarar(texto)
        if texto.strip():
            res.append(replace(p, texto=texto))
    return res


def _exigir_indice(i: int, todas: list[Palavra]) -> None:
    if not 0 <= i < len(todas):
        raise ErroProducao(f"palavra {i} não existe (o episódio tem {len(todas)})")


def _janela(c: Corte, ed: Edicao, todas: list[Palavra]) -> Corte:
    if ed.inicio_palavra is None and ed.fim_palavra is None:
        return c
    i0, i1 = indices_do_corte(todas, c.inicio, c.fim)
    i = i0 if ed.inicio_palavra is None else ed.inicio_palavra
    j = i1 if ed.fim_palavra is None else ed.fim_palavra
    _exigir_indice(i, todas)
    _exigir_indice(j, todas)
    if i > j:
        raise ErroProducao("o início tem que vir antes do fim")
    inicio, fim = todas[i].inicio, todas[j].fim
    if not DURACAO_MIN_S <= fim - inicio <= DURACAO_MAX_S:
        raise ErroProducao(f"duração {fim - inicio:.1f}s fora de {DURACAO_MIN_S:.0f}-{DURACAO_MAX_S:.0f}s")
    if (inicio, fim) == (c.inicio, c.fim):
        return c
    return replace(c, inicio=inicio, fim=fim, edicoes=replace(c.edicoes, rostos={}))


def _textos(c: Corte, ed: Edicao, todas: list[Palavra]) -> Corte:
    legenda = dict(c.edicoes.legenda)
    for i, t in ed.legenda.items():
        _exigir_indice(i, todas)
        if t is None or t.strip() == todas[i].texto:
            legenda.pop(i, None)
        else:
            legenda[i] = t.strip()
    masc = set(c.edicoes.mascaradas)
    for i, m in ed.mascarar.items():
        _exigir_indice(i, todas)
        (masc.add if m else masc.discard)(i)
    if ed.mascarar_palavroes:
        i0, i1 = indices_do_corte(todas, c.inicio, c.fim)
        masc |= {i for i in range(i0, i1 + 1) if eh_palavrao(legenda.get(i, todas[i].texto))}
    return replace(c, edicoes=replace(c.edicoes, legenda=legenda, mascaradas=tuple(sorted(masc))))


def _rosto(c: Corte, ed: Edicao, pessoas_por_plano: list[int]) -> Corte:
    if ed.rosto is None:
        return c
    k, j = ed.rosto
    if not 0 <= k < len(pessoas_por_plano):
        raise ErroProducao(f"plano {k} não existe (o trecho tem {len(pessoas_por_plano)})")
    if not 0 <= j < pessoas_por_plano[k]:
        raise ErroProducao(f"pessoa {j} não existe no plano {k}")
    return replace(c, edicoes=replace(c.edicoes, rostos={**c.edicoes.rostos, k: j}))


def _titulo_formato(c: Corte, ed: Edicao) -> Corte:
    if ed.titulo is not None:
        titulo = ed.titulo.strip()
        if not titulo or len(titulo) > TITULO_MAX:
            raise ErroProducao(f"título vazio ou com mais de {TITULO_MAX} caracteres")
        c = replace(c, titulo=titulo)
    if ed.formato is not None:
        if ed.formato not in FORMATOS:
            raise ErroProducao(f"formato '{ed.formato}' ainda não renderiza; use um de {FORMATOS}")
        c = replace(c, formato=ed.formato)
    return c


def aplicar(c: Corte, ed: Edicao, todas: list[Palavra], pessoas_por_plano: list[int]) -> Corte:
    """`pessoas_por_plano[k]` = quantas pessoas o plano k tem (do rosto.json atual)."""
    novo = _titulo_formato(_rosto(_textos(_janela(c, ed, todas), ed, todas), ed, pessoas_por_plano), ed)
    return novo if novo == c else replace(novo, alterado=True)
```

Nota: `edicao.py` importa `montagem`, que importa `rosto`/`legenda`; nenhum deles importa `edicao` (não há ciclo).

- [ ] **Step 3: Check e commit**

```bash
git add src/cortes/render/edicao.py tests/test_render_edicao.py
git commit -m "feat: regras de edição do Short — início/fim por palavra, legenda, palavrão, rosto"
```

---

### Task 5: Pipeline aplica as edições; montar projeto separado do render

**Files:**
- Modify: `src/cortes/render/pipeline.py`
- Test: `tests/test_render_pipeline.py`

- [ ] **Step 1: Testes** (acrescente; use o `Falso` e o `episodio` do arquivo)

```python
from cortes.render.corte import Edicoes
from cortes.render.pipeline import montar_projeto


def test_projeto_aplica_legenda_e_mascara(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    c = replace(C, edicoes=Edicoes({0: "Eu,"}, (1,), {}))
    montar_projeto(pasta, c, tmp_path, f.dep())
    html = (pasta / "cortes" / "0" / "projeto" / "index.html").read_text(encoding="utf-8")
    assert "<span>Eu, g*nhei.</span>" in html and f.chamadas == ["ffmpeg", "py-visao"]


def test_novo_trecho_apaga_miniaturas_velhas(tmp_path: Path) -> None:
    pasta, f = episodio(tmp_path), Falso()
    montar_projeto(pasta, C, tmp_path, f.dep())
    mini = pasta / "cortes" / "0" / "miniaturas"
    mini.mkdir()
    (mini / "p0-0.jpg").write_bytes(b"x")
    montar_projeto(pasta, replace(C, inicio=11.0), tmp_path, f.dep())
    assert not mini.exists()
```

(`montar_projeto` não chama o npx. A palavra `ganhei.` tem índice 1 no `palavras.json` da fixture; `mascarar("ganhei.")` dá `g*nhei.`.)

- [ ] **Step 2: Implementar**

Em `pipeline.py`:
- `_html` passa a usar `todas = palavras_editadas([Palavra(**p) for p in ler_json(...)], c.edicoes)` (import de `cortes.render.edicao`) e chama `valores(..., c.edicoes.rostos)`.
- Em `preparar_trecho`, logo antes de recortar (cache inválido), apague as miniaturas velhas: `mini = d / "miniaturas"`, e `if mini.exists(): shutil.rmtree(mini)`. Comentário: as miniaturas são quadros do trecho anterior.
- Funções novas:

```python
def montar_projeto(pasta_ep: Path, c: Corte, raiz: Path, dep: DepRender) -> None:
    """Trecho + rosto (com cache) e o index.html com as edições — o que a prévia do editor mostra
    e o render grava em MP4. Rápido quando início/fim não mudaram (só regera o HTML)."""
    segs = preparar_trecho(pasta_ep, c, raiz, dep)
    criar_projeto(pasta_corte(pasta_ep, c.indice) / "projeto", _html(pasta_ep, c, raiz, segs))


def renderizar_corte(pasta_ep: Path, c: Corte, raiz: Path, dep: DepRender) -> None:
    """Gera cortes/<indice>/short-v<versao+1>.mp4. Falha alto (ErroRender) em qualquer passo."""
    montar_projeto(pasta_ep, c, raiz, dep)
    d = pasta_corte(pasta_ep, c.indice)
    renderizar(d / "projeto", d / f"short-v{c.versao + 1}.mp4", dep.npx, dep.rodar)
```

- [ ] **Step 3: Check e commit**

```bash
git add src/cortes/render/pipeline.py tests/test_render_pipeline.py
git commit -m "feat: projeto do corte aplica as edições; montar_projeto separado do render"
```

---

### Task 6: Miniatura do rosto e runtime da prévia (puro + fino)

**Files:**
- Create: `src/cortes/render/miniatura.py`, `src/cortes/render/previa.py`
- Test: `tests/test_render_miniatura.py`

- [ ] **Step 1: Testes**

```python
from pathlib import Path

import pytest

from cortes.render.miniatura import args_miniatura, gerar_miniatura
from cortes.render.previa import RUNTIME, com_runtime
from cortes.render.processo import ErroRender
from cortes.render.rosto import Pessoa, Plano


def test_args_recortam_quadrado_em_volta_do_rosto() -> None:
    args = args_miniatura(Path("t.mp4"), Path("m.jpg"), 1.5, Pessoa(960, 540, 80, 3, 0.9), 1920, 1080)
    assert args[args.index("-ss") + 1] == "1.500"
    assert args[args.index("-vf") + 1] == "crop=256:256:832:412,scale=160:160"


def test_quadrado_nao_sai_do_quadro() -> None:
    args = args_miniatura(Path("t.mp4"), Path("m.jpg"), 0.0, Pessoa(20, 1070, 30, 1, 0.9), 1920, 1080)
    assert args[args.index("-vf") + 1] == "crop=160:160:0:920,scale=160:160"


def test_gerar_usa_o_meio_do_plano(tmp_path: Path) -> None:
    vistos: list[list[str]] = []

    def rodar(args: list[str], cwd: Path | None) -> tuple[int, str]:
        vistos.append(args)
        Path(args[-1]).write_bytes(b"jpg")
        return 0, ""

    destino = tmp_path / "mini" / "p0-0.jpg"
    plano = Plano(0, 1.0, 3.0, (Pessoa(960, 540, 80, 3, 0.9),), 0)
    gerar_miniatura(Path("t.mp4"), destino, plano, 0, 1920, 1080, rodar)
    assert destino.read_bytes() == b"jpg" and vistos[0][vistos[0].index("-ss") + 1] == "2.000"


def test_runtime_entra_logo_depois_do_head() -> None:
    assert com_runtime("<html>\n  <head>\n<meta>") == f'<html>\n  <head>\n<script src="{RUNTIME}"></script>\n<meta>'
    with pytest.raises(ErroRender, match="<head>"):
        com_runtime("<html></html>")
```

Contas:
- **Lado do quadrado:** max(160, 3,2 × 80) = 256. x0 = 960 − 128 = 832; y0 = 540 − 128 = 412.
- **Caso na borda:** lado = max(160, 96) = 160. x0 = clamp(20 − 80) = 0; y0 = clamp(1070 − 80, 0, 1080 − 160) = 920.

- [ ] **Step 2: Implementar**

`src/cortes/render/miniatura.py`:

```python
"""Miniatura de uma pessoa num plano (editor, quem aparece): o quadro do meio do plano, recortado
num quadrado em volta do rosto. ffmpeg atrás do executor injetável."""
from pathlib import Path

from cortes.render.processo import Rodar, exigir
from cortes.render.rosto import Pessoa, Plano

LADO_PX = 160          # lado da miniatura na tela
FATOR = 3.2            # o quadrado cobre ~3,2× o raio do rosto (cabeça e um pouco de ombro)


def args_miniatura(trecho: Path, destino: Path, t: float, p: Pessoa, largura: int, altura: int) -> list[str]:
    lado = int(min(largura, altura, max(LADO_PX, FATOR * p.r)))
    x0 = int(min(max(0, round(p.x - lado / 2)), largura - lado))
    y0 = int(min(max(0, round(p.y - lado / 2)), altura - lado))
    return ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(trecho), "-frames:v", "1",
            "-vf", f"crop={lado}:{lado}:{x0}:{y0},scale={LADO_PX}:{LADO_PX}", "-q:v", "4", str(destino)]


def gerar_miniatura(trecho: Path, destino: Path, plano: Plano, j: int, largura: int, altura: int,
                    rodar: Rodar) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    t = (plano.ini + plano.fim) / 2
    exigir(rodar, args_miniatura(trecho, destino, t, plano.pessoas[j], largura, altura), None, "miniatura")
```

`src/cortes/render/previa.py`:

```python
"""Prévia do editor no navegador: o index.html do corte com o runtime do HyperFrames, como o
`hyperframes play` serve (testado em 2026-10-02: a única diferença do arquivo servido é essa linha).
O player (`<hyperframes-player>`) vem do mesmo pacote, versão fixa em web/static/index.html."""
from cortes.render.hyperframes import HYPERFRAMES
from cortes.render.processo import ErroRender

_VERSAO = HYPERFRAMES.split("@")[1]
RUNTIME = f"https://cdn.jsdelivr.net/npm/@hyperframes/core@{_VERSAO}/dist/hyperframe.runtime.iife.js"


def com_runtime(html: str) -> str:
    if "<head>" not in html:
        raise ErroRender("index.html sem <head>: não dá para injetar o runtime da prévia")
    return html.replace("<head>", f'<head>\n<script src="{RUNTIME}"></script>', 1)
```

- [ ] **Step 3: Check e commit**

```bash
git add src/cortes/render/miniatura.py src/cortes/render/previa.py tests/test_render_miniatura.py
git commit -m "feat: miniatura do rosto por plano e runtime injetado para a prévia"
```

---

### Task 7: Thread de prévias

**Files:**
- Create: `src/cortes/producao/previas.py`
- Test: `tests/test_producao_previas.py`

- [ ] **Step 1: Testes**

```python
from pathlib import Path

from cortes.producao.previas import Previas, SituacaoPrevia
from cortes.render.corte import Corte, gravar_corte, novo_corte, pasta_corte


def episodio(tmp: Path) -> Path:
    pasta = tmp / "episodios" / "abcdefghijk"
    gravar_corte(pasta_corte(pasta, 0), novo_corte(0, {"inicio": 1.0, "fim": 9.0, "titulo": "T"}, "f7"))
    return pasta


def test_pedido_vira_pronta(tmp_path: Path) -> None:
    episodio(tmp_path)
    feitos: list[int] = []
    p = Previas(tmp_path, lambda pasta, c: feitos.append(c.indice))
    p.pedir("abcdefghijk", 0)
    assert p.situacao("abcdefghijk", 0) == SituacaoPrevia("preparando") and p.preparando("abcdefghijk", 0)
    p.processar("abcdefghijk", 0)
    assert feitos == [0] and p.situacao("abcdefghijk", 0) == SituacaoPrevia("pronta")


def test_erro_fica_visivel(tmp_path: Path) -> None:
    episodio(tmp_path)

    def falha(pasta: Path, c: Corte) -> None:
        raise RuntimeError("ffmpeg sumiu")

    p = Previas(tmp_path, falha)
    p.pedir("abcdefghijk", 0)
    p.processar("abcdefghijk", 0)
    assert p.situacao("abcdefghijk", 0) == SituacaoPrevia("erro", "RuntimeError: ffmpeg sumiu")


def test_pedido_durante_o_preparo_continua_preparando(tmp_path: Path) -> None:
    episodio(tmp_path)
    p = Previas(tmp_path, lambda pasta, c: p.pedir("abcdefghijk", 0))
    p.pedir("abcdefghijk", 0)
    p._proximo()   # retira da fila como a thread faria
    p.processar("abcdefghijk", 0)
    assert p.preparando("abcdefghijk", 0)


def test_sem_pedido_nao_ha_situacao(tmp_path: Path) -> None:
    assert Previas(tmp_path, lambda pasta, c: None).situacao("abcdefghijk", 0) is None
```

- [ ] **Step 2: Implementar `src/cortes/producao/previas.py`**

```python
"""Prévia do editor (plano C): monta o projeto HyperFrames de um corte FORA da fila do render.

Recortar o trecho e medir o rosto leva 10–30 s quando início/fim mudam; esperar atrás de 5 renders
(10–20 min) mataria o editor (Davi, 2026-10-02). Uma thread só para prévias, um corte por vez; o
último pedido de cada corte vale (pedidos repetidos enquanto ele espera não se acumulam).
A situação fica em memória; depois de reiniciar o painel, quem decide é o disco (rotas_editor).
"""
import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cortes.render.corte import Corte, ler_corte, pasta_corte

Montar = Callable[[Path, Corte], None]


@dataclass(frozen=True)
class SituacaoPrevia:
    situacao: Literal["preparando", "pronta", "erro"]
    erro: str | None = None


class Previas:
    def __init__(self, raiz: Path, montar: Montar) -> None:
        self._raiz = raiz
        self._montar = montar
        self._trava = threading.Lock()
        self._tem_pedido = threading.Condition(self._trava)
        self._pedidos: list[tuple[str, int]] = []
        self._situacao: dict[tuple[str, int], SituacaoPrevia] = {}
        self._fio: threading.Thread | None = None

    def pedir(self, id: str, n: int) -> None:
        with self._tem_pedido:
            self._situacao[(id, n)] = SituacaoPrevia("preparando")
            if (id, n) not in self._pedidos:
                self._pedidos.append((id, n))
            self._tem_pedido.notify()

    def situacao(self, id: str, n: int) -> SituacaoPrevia | None:
        with self._trava:
            return self._situacao.get((id, n))

    def preparando(self, id: str, n: int) -> bool:
        s = self.situacao(id, n)
        return s is not None and s.situacao == "preparando"

    def processar(self, id: str, n: int) -> None:
        """Síncrono (testável). Um pedido novo que chegou durante o preparo mantém 'preparando':
        ele já está na fila e o resultado deste preparo seria de um estado antigo."""
        pasta = self._raiz / "episodios" / id
        try:
            self._montar(pasta, ler_corte(pasta_corte(pasta, n)))
            fim = SituacaoPrevia("pronta")
        except Exception as ex:   # qualquer falha fica visível no editor; a thread segue
            traceback.print_exc()
            fim = SituacaoPrevia("erro", f"{type(ex).__name__}: {ex}")
        with self._trava:
            if (id, n) not in self._pedidos:
                self._situacao[(id, n)] = fim

    def _proximo(self) -> tuple[str, int]:
        with self._tem_pedido:
            while not self._pedidos:
                self._tem_pedido.wait()
            return self._pedidos.pop(0)

    def _laco(self) -> None:
        while True:
            self.processar(*self._proximo())

    def iniciar(self) -> None:
        with self._trava:
            if self._fio is not None:
                raise RuntimeError("prévias já iniciadas")
            self._fio = threading.Thread(target=self._laco, daemon=True, name="previas")
        self._fio.start()
```

- [ ] **Step 3: Check e commit**

```bash
git add src/cortes/producao/previas.py tests/test_producao_previas.py
git commit -m "feat: thread de prévias do editor, fora da fila do render"
```

---

### Task 8: API do editor — leitura, prévia, miniaturas, versões

**Files:**
- Create: `src/cortes/producao/rotas_editor.py`
- Modify: `src/cortes/producao/rotas_cortes.py`, `src/cortes/producao/rotas.py`, `src/cortes/painel/servidor.py`
- Test: `tests/test_producao_rotas_editor.py`

- [ ] **Step 1: Fixture e testes de leitura**

```python
import json
import os
import time
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from cortes.painel.servidor import Config, criar_app
from cortes.producao.estado import EstadoEpisodio
from cortes.producao.fila import Fila
from cortes.producao.previas import Previas
from cortes.render.corte import Corte, concluir, gravar_corte, novo_corte, pasta_corte
from cortes.render.previa import RUNTIME
from tests.test_producao_rotas import preparar_concluido

AGORA = datetime(2026, 10, 2, 9)
EP = "/api/episodios/abcdefghijk"
PALAVRAS = [{"texto": t, "inicio": float(i), "fim": i + 0.8} for i, t in
            enumerate(["Antes.", "Mas", "eu", "ganhei", "porra,", "dez", "mil", "reais.", "Depois"])]
ROSTO = {"formato": 2, "largura": 1920, "altura": 1080, "cortes": [2.0],
         "amostras": [{"t": 0.0, "rostos": [{"x": 960, "y": 540, "r": 80, "conf": 0.9}]},
                      {"t": 2.5, "rostos": [{"x": 400, "y": 500, "r": 80, "conf": 0.9},
                                            {"x": 1500, "y": 500, "r": 80, "conf": 0.8}]},
                      {"t": 2.75, "rostos": [{"x": 410, "y": 500, "r": 80, "conf": 0.9},
                                             {"x": 1510, "y": 500, "r": 80, "conf": 0.8}]}]}


class Ambiente:
    def __init__(self, cfg: Config) -> None:
        self.pasta = preparar_concluido(cfg)
        (self.pasta / "palavras.json").write_text(json.dumps(PALAVRAS), encoding="utf-8")
        self.d = pasta_corte(self.pasta, 0)
        gravar_corte(self.d, concluir(novo_corte(0, {"inicio": 1.0, "fim": 7.8, "titulo": "Ganhei"}, "f7")))
        (self.d / "short-v1.mp4").write_bytes(b"v1")
        (self.d / "rosto.json").write_text(json.dumps(ROSTO), encoding="utf-8")
        proj = self.d / "projeto"
        (proj / "assets").mkdir(parents=True)
        (proj / "assets" / "trecho.mp4").write_bytes(b"trecho")
        time.sleep(0.01)
        (proj / "index.html").write_text("<html>\n  <head>\n</head></html>", encoding="utf-8")
        self.montados: list[Corte] = []
        self.rodados: list[list[str]] = []
        self.previas = Previas(cfg.raiz, lambda p, c: self.montados.append(c))
        fila = Fila(cfg.raiz, self._nada, lambda: AGORA)
        app = criar_app(cfg, executar=lambda a, c: "", abrir=lambda a, c: None, fila=fila,
                        previas=self.previas, rodar=self._rodar)
        self.c = TestClient(app, base_url="http://127.0.0.1")

    def _nada(self, nome: str, pasta: Path, e: EstadoEpisodio) -> None:
        return None

    def _rodar(self, args: list[str], cwd: Path | None) -> tuple[int, str]:
        self.rodados.append(args)
        Path(args[-1]).write_bytes(b"jpg")
        return 0, ""


def test_estado_do_editor(cfg: Config) -> None:
    a = Ambiente(cfg)
    d = a.c.get(f"{EP}/cortes/0/editor").json()
    assert (d["inicio_palavra"], d["fim_palavra"]) == (1, 7) and d["aviso_inicio"] is True
    assert [p["dentro"] for p in d["palavras"]] == [False] + [True] * 7 + [False]
    assert d["previa"]["situacao"] == "pronta" and d["previa"]["url"].startswith(f"{EP}/cortes/0/previa/index.html?v=")
    assert [(p["k"], len(p["pessoas"]), p["escolha"]) for p in d["planos"]] == [(0, 1, 0), (1, 2, 0)]
    assert d["versoes"] == [{"versao": 1, "url": f"{EP}/cortes/0/video?versao=1"}]
    assert d["editavel"] is True and d["formatos"] == ["f7", "f1"]


def test_previa_desatualizada_quando_o_corte_e_mais_novo(cfg: Config) -> None:
    a = Ambiente(cfg)
    os.utime(a.d / "projeto" / "index.html", (1, 1))
    assert a.c.get(f"{EP}/cortes/0/editor").json()["previa"]["situacao"] == "desatualizada"


def test_arquivos_da_previa(cfg: Config) -> None:
    a = Ambiente(cfg)
    html = a.c.get(f"{EP}/cortes/0/previa/index.html").text
    assert RUNTIME in html
    r = a.c.get(f"{EP}/cortes/0/previa/assets/trecho.mp4")
    assert r.content == b"trecho" and r.headers["cache-control"] == "no-store"
    assert a.c.get(f"{EP}/cortes/0/previa/../corte.json").status_code in (404, 422)
    assert a.c.get(f"{EP}/cortes/0/previa/hyperframes.json").status_code == 422


def test_miniatura_gerada_uma_vez(cfg: Config) -> None:
    a = Ambiente(cfg)
    assert a.c.get(f"{EP}/cortes/0/planos/1/pessoas/1").content == b"jpg"
    a.c.get(f"{EP}/cortes/0/planos/1/pessoas/1")
    assert len(a.rodados) == 1
    assert a.c.get(f"{EP}/cortes/0/planos/1/pessoas/5").status_code == 422


def test_video_por_versao(cfg: Config) -> None:
    a = Ambiente(cfg)
    assert a.c.get(f"{EP}/cortes/0/video", params={"versao": 1}).content == b"v1"
    assert a.c.get(f"{EP}/cortes/0/video", params={"versao": 2}).status_code == 422
```

Contas:
- **Janela do corte:** [1,0; 7,8] pega as palavras de índice 1 a 7. A janela de 30 s mostra todas as 9 palavras.
- **Aviso de início:** "Mas eu ganhei…" começa com conectivo, então `aviso_inicio` é verdadeiro.
- **Planos:** o 0 vai de [0; 2,0) com 1 pessoa. O 1 vai de [2,0; 3,0) com 2 pessoas, n=2 cada; o padrão é a de maior confiança (0,9), que é a da esquerda, índice 0.

- [ ] **Step 2: Implementar `src/cortes/producao/rotas_editor.py` (leitura)**

```python
"""API do editor (plano C; spec produção §5 "Editor"): estado do editor, edições, a prévia no
navegador (o projeto HyperFrames do corte com o runtime injetado), miniaturas dos rostos por plano
e as versões renderizadas. `pasta_de` vem de rotas.py (valida o id do episódio)."""
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response

from cortes.episodio import ler_json
from cortes.producao.estado import ErroProducao
from cortes.producao.previas import Previas
from cortes.regra_inicio import comeca_no_meio
from cortes.render.corte import ARQUIVO, Corte, ler_corte, pasta_corte
from cortes.render.edicao import indices_do_corte, mascarar
from cortes.render.miniatura import gerar_miniatura
from cortes.render.montagem import FORMATOS
from cortes.render.previa import com_runtime
from cortes.render.processo import Rodar
from cortes.render.rosto import Plano, Rosto, ler_rosto, planos
from cortes.tipos import Palavra

JANELA_S = 30.0                 # transcrição mostrada em volta do corte, para mover início/fim
PALAVRAS_AVISO = 8              # quantas palavras do início a regra de início lê
SEM_CACHE = {"Cache-Control": "no-store"}
_VERSAO = re.compile(r"short-v(\d+)\.mp4$")


def _url(id: str, n: int) -> str:
    return f"/api/episodios/{id}/cortes/{n}"


def corte_de(pasta: Path, n: int) -> Corte:
    d = pasta_corte(pasta, n)
    if not (d / ARQUIVO).exists():
        raise ErroProducao(f"corte {n} não existe; renderize o candidato antes de editar")
    return ler_corte(d)


def palavras_do_episodio(pasta: Path) -> list[Palavra]:
    return [Palavra(**p) for p in ler_json(pasta / "palavras.json")]


def _palavras_json(todas: list[Palavra], c: Corte) -> list[dict[str, Any]]:
    res = []
    for i, p in enumerate(todas):
        if not c.inicio - JANELA_S <= p.inicio <= c.fim + JANELA_S:
            continue
        texto = c.edicoes.legenda.get(i, p.texto)
        masc = i in c.edicoes.mascaradas
        res.append({"i": i, "texto": mascarar(texto) if masc else texto, "original": p.texto,
                    "inicio": p.inicio, "fim": p.fim, "dentro": c.inicio - 0.01 <= p.inicio <= c.fim + 0.01,
                    "mascarada": masc, "editada": i in c.edicoes.legenda})
    return res


def rosto_do_corte(d: Path) -> tuple[Rosto, list[Plano]] | None:
    if not (d / "rosto.json").exists():
        return None
    r = ler_rosto(d / "rosto.json")
    return r, planos(r)


def _planos_json(id: str, d: Path, c: Corte) -> list[dict[str, Any]]:
    rp = rosto_do_corte(d)
    if rp is None:
        return []
    marca = d / "recorte.json"
    v = int(marca.stat().st_mtime) if marca.exists() else 0
    return [{"k": p.k, "ini": p.ini, "fim": p.fim, "padrao": p.padrao,
             "escolha": c.edicoes.rostos.get(p.k, p.padrao),
             "pessoas": [{"j": j, "x": s.x, "y": s.y, "n": s.n,
                          "miniatura": f"{_url(id, c.indice)}/planos/{p.k}/pessoas/{j}?v={v}"}
                         for j, s in enumerate(p.pessoas)]} for p in rp[1]]


def situacao_previa(previas: Previas, d: Path, id: str, c: Corte) -> dict[str, Any]:
    """Memória da thread primeiro; sem ela (painel reiniciado), o disco: index.html mais novo que o
    corte.json = pronta, mais velho = desatualizada, ausente = ausente."""
    idx = d / "projeto" / "index.html"
    mem = previas.situacao(id, c.indice)
    url = f"{_url(id, c.indice)}/previa/index.html?v={int(idx.stat().st_mtime * 1000)}" if idx.exists() else None
    if mem is not None and mem.situacao != "pronta":
        return {"situacao": mem.situacao, "erro": mem.erro, "url": None}
    if mem is not None and url is not None:   # a thread acabou de montar: vale mais que o mtime
        return {"situacao": "pronta", "erro": None, "url": url}
    if url is None:
        return {"situacao": "ausente", "erro": None, "url": None}
    novo = idx.stat().st_mtime >= (d / ARQUIVO).stat().st_mtime
    return {"situacao": "pronta" if novo else "desatualizada", "erro": None, "url": url}


def _versoes(id: str, d: Path, n: int) -> list[dict[str, Any]]:
    vs = sorted(int(m.group(1)) for a in d.glob("short-v*.mp4") if (m := _VERSAO.search(a.name)))
    return [{"versao": v, "url": f"{_url(id, n)}/video?versao={v}"} for v in vs]


def editavel(previas: Previas, id: str, c: Corte) -> bool:
    return c.status not in ("na_fila", "renderizando") and not previas.preparando(id, c.indice)


def estado_editor(pasta: Path, n: int, previas: Previas) -> dict[str, Any]:
    id, c = pasta.name, corte_de(pasta, n)
    d = pasta_corte(pasta, n)
    todas = palavras_do_episodio(pasta)
    i0, i1 = indices_do_corte(todas, c.inicio, c.fim)
    meta = ler_json(pasta / "meta.json") if (pasta / "meta.json").exists() else {}
    abertura = " ".join(p.texto for p in todas[i0:i0 + PALAVRAS_AVISO])
    return {"corte": asdict(c), "episodio": {"id": id, "titulo": meta.get("titulo")},
            "palavras": _palavras_json(todas, c), "inicio_palavra": i0, "fim_palavra": i1,
            "aviso_inicio": comeca_no_meio(abertura), "planos": _planos_json(id, d, c),
            "previa": situacao_previa(previas, d, id, c), "versoes": _versoes(id, d, n),
            "formatos": list(FORMATOS), "editavel": editavel(previas, id, c)}


def montar(app: FastAPI, pasta_de: Any, previas: Previas, rodar: Rodar) -> None:
    _rotas_leitura(app, pasta_de, previas, rodar)


def _rotas_leitura(app: FastAPI, pasta_de: Any, previas: Previas, rodar: Rodar) -> None:
    @app.get("/api/episodios/{id}/cortes/{n}/editor")
    def api_editor(id: str, n: int) -> Any:
        return estado_editor(pasta_de(id), n, previas)

    @app.get("/api/episodios/{id}/cortes/{n}/previa/{arquivo:path}")
    def api_previa(id: str, n: int, arquivo: str) -> Response:
        proj = pasta_corte(pasta_de(id), n) / "projeto"
        if arquivo == "index.html" and (proj / "index.html").exists():
            return HTMLResponse(com_runtime((proj / "index.html").read_text(encoding="utf-8")), headers=SEM_CACHE)
        if arquivo == "assets/trecho.mp4" and (proj / arquivo).exists():
            return FileResponse(proj / arquivo, media_type="video/mp4", headers=SEM_CACHE)
        raise ErroProducao(f"arquivo da prévia indisponível: {arquivo!r}")

    @app.get("/api/episodios/{id}/cortes/{n}/planos/{k}/pessoas/{j}")
    def api_miniatura(id: str, n: int, k: int, j: int) -> FileResponse:
        d = pasta_corte(pasta_de(id), n)
        rp = rosto_do_corte(d)
        if rp is None:
            raise ErroProducao(f"corte {n} ainda sem rosto medido")
        r, pls = rp
        if not 0 <= k < len(pls) or not 0 <= j < len(pls[k].pessoas):
            raise ErroProducao(f"plano {k} / pessoa {j} não existe")
        arq = d / "miniaturas" / f"p{k}-{j}.jpg"
        if not arq.exists():
            gerar_miniatura(d / "projeto" / "assets" / "trecho.mp4", arq, pls[k], j, r.largura, r.altura, rodar)
        return FileResponse(arq, media_type="image/jpeg")
```

Tipo de `pasta_de`: use `Callable[[str], Path]` (import de `collections.abc`) no lugar de `Any`. O `Any` acima é só para encurtar.

Nota sobre o `index.html?v=`: o `v` em milissegundos de mtime só serve para furar o cache do navegador quando a prévia é refeita.

- [ ] **Step 3: Ligações**

- `rotas_cortes.py`:
  - `api_video_corte` ganha `versao: int | None = None`. Com versão, serve `short-v{versao}.mp4` se o arquivo existir; senão, `ErroProducao(f"versão {versao} do corte {indice} não existe")`. O nome do download usa a versão servida.
  - `montar(app, pasta_de, fila, escrita, previas)`.
  - `pedir_render` recebe `preparando: bool` e recusa com `ErroProducao("a prévia deste corte está sendo preparada; espere terminar para renderizar")`. A rota passa `previas.preparando(id, indice)`.
- `rotas.py`: `montar(app, raiz, fila, escrita, agora, previas, rodar)` chama `rotas_cortes.montar(..., previas)` e `rotas_editor.montar(app, lambda id: _pasta(raiz, id), previas, rodar)`.
- `servidor.py`:
  - `criar_app(..., fila=None, previas: Previas | None = None, rodar: Rodar = rodar_processo)`.
  - Monte **um** `DepRender(cfg.py_visao, cfg.modelo_rosto, npx, rodar=rodar)`. `_fila_real` passa a recebê-lo pronto em vez de montar o seu.
  - `previas = previas if previas is not None else Previas(cfg.raiz, lambda pasta, c: montar_projeto(pasta, c, cfg.raiz, dep))`.
  - No `ciclo`, depois de `fila.iniciar()`: `previas.iniciar()`.
  - Handler novo: `@app.exception_handler(ErroRender)` → 422 com `{"detail": str(e)}` (rosto.json inválido, miniatura que falhou).
  - Passe `previas, rodar` a `rotas_producao.montar`. Confira que `servidor.py` continua abaixo de 400 linhas; se passar, reporte.

- [ ] **Step 4: Check, testes deste arquivo e os de `rotas_cortes`/servidor; commit**

```bash
git add src/cortes tests/test_producao_rotas_editor.py
git commit -m "feat: API do editor — estado, prévia com runtime, miniaturas e versões"
```

---

### Task 9: API do editor — editar e pedir prévia

**Files:**
- Modify: `src/cortes/producao/rotas_editor.py`
- Test: `tests/test_producao_rotas_editor.py`

- [ ] **Step 1: Testes** (acrescente)

```python
def test_editar_inicio_pede_previa_e_marca_alterado(cfg: Config) -> None:
    a = Ambiente(cfg)
    d = a.c.post(f"{EP}/cortes/0/editar", json={"inicio_palavra": 2}).json()
    assert d["corte"]["inicio"] == 2.0 and d["corte"]["alterado"] is True
    assert d["previa"]["situacao"] == "preparando" and d["editavel"] is False
    assert "preparada" in a.c.post(f"{EP}/cortes/0/renderizar", json={}).json()["detail"]
    a.previas.processar("abcdefghijk", 0)
    assert a.montados[0].inicio == 2.0
    assert a.c.get(f"{EP}/cortes/0/editor").json()["previa"]["situacao"] == "pronta"


def test_editar_legenda_e_palavroes(cfg: Config) -> None:
    a = Ambiente(cfg)
    d = a.c.post(f"{EP}/cortes/0/editar", json={"legenda": {"5": "10"}, "mascarar_palavroes": True}).json()
    textos = {p["i"]: p["texto"] for p in d["palavras"]}
    assert textos[5] == "10" and textos[4] == "p*rra,"


def test_escolher_pessoa(cfg: Config) -> None:
    a = Ambiente(cfg)
    d = a.c.post(f"{EP}/cortes/0/editar", json={"rosto": [1, 1]}).json()
    assert d["planos"][1]["escolha"] == 1
    a.previas.processar("abcdefghijk", 0)   # a edição pediu prévia; sem isso a próxima é recusada
    assert "pessoa 3" in a.c.post(f"{EP}/cortes/0/editar", json={"rosto": [1, 3]}).json()["detail"]


def test_edicao_recusada_com_o_corte_na_fila(cfg: Config) -> None:
    a = Ambiente(cfg)
    a.c.post(f"{EP}/cortes/0/renderizar", json={})
    assert "fila" in a.c.post(f"{EP}/cortes/0/editar", json={"titulo": "Novo"}).json()["detail"]


def test_pedir_previa(cfg: Config) -> None:
    a = Ambiente(cfg)
    assert a.c.post(f"{EP}/cortes/0/previa").json()["previa"]["situacao"] == "preparando"
```

- [ ] **Step 2: Implementar** (em `rotas_editor.py`)

```python
from pydantic import BaseModel
from cortes.render.corte import gravar_corte
from cortes.render.edicao import Edicao, aplicar


class PedidoEdicao(BaseModel):
    inicio_palavra: int | None = None
    fim_palavra: int | None = None
    titulo: str | None = None
    formato: str | None = None
    legenda: dict[int, str | None] = {}
    mascarar: dict[int, bool] = {}
    mascarar_palavroes: bool = False
    rosto: tuple[int, int] | None = None

    def edicao(self) -> Edicao:
        return Edicao(self.inicio_palavra, self.fim_palavra, self.titulo, self.formato, dict(self.legenda),
                      dict(self.mascarar), self.mascarar_palavroes, self.rosto)


def _exigir_editavel(previas: Previas, id: str, c: Corte) -> None:
    if c.status in ("na_fila", "renderizando"):
        raise ErroProducao(f"corte {c.indice} está na fila do render; espere terminar para editar")
    if previas.preparando(id, c.indice):
        raise ErroProducao(f"a prévia do corte {c.indice} está sendo preparada; espere terminar")


def editar(pasta: Path, n: int, pedido: PedidoEdicao, previas: Previas) -> None:
    c = corte_de(pasta, n)
    _exigir_editavel(previas, pasta.name, c)
    rp = rosto_do_corte(pasta_corte(pasta, n))
    pessoas_por_plano = [len(p.pessoas) for p in rp[1]] if rp else []
    novo = aplicar(c, pedido.edicao(), palavras_do_episodio(pasta), pessoas_por_plano)
    if novo != c:
        gravar_corte(pasta_corte(pasta, n), novo)
        previas.pedir(pasta.name, n)
```

Na `montar`, acrescente `_rotas_edicao(app, pasta_de, previas, escrita)`. `escrita` é a mesma trava do servidor; passe-a pela `montar` de `rotas_editor`, que passa a ser `montar(app, pasta_de, previas, rodar, escrita)`. Ajuste a chamada em `rotas.py`.

```python
def _rotas_edicao(app: FastAPI, pasta_de: Callable[[str], Path], previas: Previas,
                  escrita: threading.Lock) -> None:
    @app.post("/api/episodios/{id}/cortes/{n}/editar")
    def api_editar(id: str, n: int, pedido: PedidoEdicao) -> Any:
        pasta = pasta_de(id)
        with escrita:
            editar(pasta, n, pedido, previas)
        return estado_editor(pasta, n, previas)

    @app.post("/api/episodios/{id}/cortes/{n}/previa")
    def api_pedir_previa(id: str, n: int) -> Any:
        pasta = pasta_de(id)
        with escrita:
            c = corte_de(pasta, n)
            _exigir_editavel(previas, id, c)
            previas.pedir(id, n)
        return estado_editor(pasta, n, previas)
```

Corrida com a rota de renderizar: as duas usam a trava `escrita`. Renderizar recusa com a prévia em preparo, e editar recusa com o corte na fila.

- [ ] **Step 3: Check e commit**

```bash
git add src/cortes/producao/rotas_editor.py src/cortes/producao/rotas.py tests/test_producao_rotas_editor.py
git commit -m "feat: editar o corte e pedir a prévia pela API do editor"
```

---

### Task 10: Tela do editor — rota, layout, prévia e ajustes

**Files:**
- Create: `web/static/js/editor.js`
- Modify: `web/static/js/inicio.js`, `web/static/js/episodio.js`, `web/static/index.html`, `web/static/painel.css`

- [ ] **Step 1: Roteamento com parâmetros** — em `inicio.js` `desenhar`:

```js
  const [pedido, ...args] = location.hash.slice(1).split("/");
  const nome = TELAS[pedido] ? pedido : "episodios";
  const noTrilho = nome === "editor" ? "episodios" : nome;   // o editor mora dentro de Episódios
  $$("[data-tela]").forEach(a => a.classList.toggle("ativo", a.dataset.tela === noTrilho));
  try {
    await TELAS[nome](meu, ...args.map(decodeURIComponent));
```

(Atualize o comentário do topo: telas podem receber parâmetros por `#tela/a/b`.)

- [ ] **Step 2: `index.html`**: depois de `js/episodio.js`, carregue `js/transcricao.js`, `js/planos.js` e `js/editor.js`, nesta ordem. Antes de todos os scripts do painel, carregue o player:

```html
<!-- prévia do editor: mesma versão do HyperFrames do render (render/hyperframes.py HYPERFRAMES) -->
<script src="https://cdn.jsdelivr.net/npm/@hyperframes/player@0.8.104/dist/hyperframes-player.global.js"></script>
```

- [ ] **Step 3: `web/static/js/editor.js`**

```js
"use strict";
// Editor do Short (plano C, spec produção §5 "Editor"): três colunas — prévia 9:16 tocando o
// próprio projeto HyperFrames no navegador (<hyperframes-player>), transcrição palavra a palavra
// (transcricao.js) e ajustes: título, formato, quem aparece (planos.js), renderizar e versões.
// Toda edição vai por POST .../editar, que devolve o estado novo; a prévia é refeita fora da fila
// do render e a tela acompanha até ela ficar pronta.
let ED = null;   // /api/episodios/{id}/cortes/{n}/editor + {id, n}
const urlCorte = (id, n) => `/api/episodios/${encodeURIComponent(id)}/cortes/${n}`;
const NOMES_PREVIA = { preparando: "preparando a prévia…", erro: "a prévia falhou",
  desatualizada: "atualizando a prévia…", ausente: "gerando a prévia…" };

function htmlPrevia(ed) {
  const p = ed.previa;
  if (p.situacao === "pronta") return `<hyperframes-player class="previa" src="${esc(p.url)}" controls></hyperframes-player>`;
  const erro = p.situacao === "erro"
    ? `<p class="erro-txt">${esc(p.erro)}</p><button class="botao mini" id="refazer-previa">tentar de novo</button>` : "";
  return `<div class="previa vazia"><span>${esc(NOMES_PREVIA[p.situacao])}</span>${erro}</div>`;
}

function htmlVersoes(ed) {
  if (!ed.versoes.length) return `<p class="sub">Nenhuma versão renderizada ainda.</p>`;
  return `<ul class="versoes">${ed.versoes.slice().reverse().map(v => `<li>
    <a href="${esc(v.url)}" target="_blank" rel="noopener">v${v.versao}</a>
    <a class="botao mini" href="${esc(v.url)}&baixar=true">baixar</a></li>`).join("")}</ul>`;
}

function htmlAjustes(ed) {
  const c = ed.corte;
  const dis = ed.editavel ? "" : "disabled";
  const formatos = ed.formatos.map(f => `<option value="${esc(f)}" ${f === c.formato ? "selected" : ""}>${esc(f)} · ${esc(nomeFormato(f))}</option>`).join("");
  const situacao = c.alterado ? "edições ainda não renderizadas" : c.versao ? `v${c.versao} renderizada` : "ainda não renderizado";
  return `<label>Título<input id="ed-titulo" maxlength="100" value="${esc(c.titulo)}" ${dis}></label>
    <label>Formato<select id="ed-formato" ${dis}>${formatos}</select></label>
    <div class="ed-render"><button class="botao primario" id="ed-renderizar" ${dis}>Renderizar</button>
      <span class="num">${esc(NOMES_CORTE[c.status] ?? c.status)} · ${esc(situacao)}</span></div>
    ${c.erro ? `<p class="erro-txt">${esc(c.erro)}</p>` : ""}
    <h3>Quem aparece</h3>${htmlPlanos(ed)}
    <h3>Versões</h3>${htmlVersoes(ed)}`;
}

function htmlEditor(ed) {
  return `<header><div><a class="voltar" href="#episodios">← Episódios</a>
      <h1>Editor <em>— ${esc(ed.corte.titulo)}</em></h1>
      <p class="sub">${esc(ed.episodio.titulo ?? ed.episodio.id)} · candidato ${ed.corte.indice}</p></div></header>
    <div class="editor">
      <div class="col-previa" id="ed-previa">${htmlPrevia(ed)}</div>
      <div class="col-transcricao" id="ed-transcricao">${htmlTranscricao(ed)}</div>
      <div class="col-ajustes" id="ed-ajustes">${htmlAjustes(ed)}</div>
    </div>`;
}

async function editar(pedido) {
  const ed = ED, meu = desenhar.n;
  try {
    const novo = await post(`${urlCorte(ed.id, ed.n)}/editar`, pedido);
    if (meu === desenhar.n && ED === ed) aplicarEstado(novo);
  } catch (e) { avisar(e.message); }
}

async function pedirPrevia() {
  const ed = ED, meu = desenhar.n;
  try {
    const novo = await post(`${urlCorte(ed.id, ed.n)}/previa`);
    if (meu === desenhar.n && ED === ed) aplicarEstado(novo);
  } catch (e) { avisar(e.message); }
}

async function renderizarDoEditor(b) {
  const ed = ED, meu = desenhar.n;
  b.disabled = true;
  try {
    await post(`${urlCorte(ed.id, ed.n)}/renderizar`, {});
    atualizarProducao();   // religa o polling da fila
    const novo = await api(`${urlCorte(ed.id, ed.n)}/editor`);
    if (meu === desenhar.n && ED === ed) aplicarEstado(novo);
  } catch (e) { avisar(e.message); b.disabled = false; }
}

// Transcrição e ajustes são redesenhados sempre; a prévia só quando a URL (que leva a versão do
// arquivo) ou a situação mudou — recriar o player à toa reiniciaria o vídeo que Davi está vendo.
function aplicarEstado(novo) {
  const antes = ED;
  ED = { ...novo, id: antes.id, n: antes.n };
  const rolagem = $("#ed-transcricao .palavras")?.scrollTop ?? 0;
  $("#ed-transcricao").innerHTML = htmlTranscricao(ED);
  const box = $("#ed-transcricao .palavras");
  if (box) box.scrollTop = rolagem;
  $("#ed-ajustes").innerHTML = htmlAjustes(ED);
  if (antes.previa.url !== ED.previa.url || antes.previa.situacao !== ED.previa.situacao) {
    $("#ed-previa").innerHTML = htmlPrevia(ED);
  }
  ligarEditor();
  acompanhar();
}

// Enquanto a prévia prepara ou o corte está no render, relê o estado a cada 2 s.
function acompanhar() {
  clearTimeout(acompanhar.t);
  if (!ED) return;
  const ocupado = ED.previa.situacao === "preparando" || ["na_fila", "renderizando"].includes(ED.corte.status);
  if (!ocupado) return;
  const ed = ED, meu = desenhar.n;
  acompanhar.t = setTimeout(async () => {
    try {
      const novo = await api(`${urlCorte(ed.id, ed.n)}/editor`);
      if (meu === desenhar.n && ED === ed) aplicarEstado(novo);
    } catch (e) { avisar(e.message); }
  }, 2000);
}

function ligarEditor() {
  ligarTranscricao();
  ligarPlanos();
  const t = $("#ed-titulo");
  if (t) t.onchange = () => { const v = t.value.trim(); if (v && v !== ED.corte.titulo) editar({ titulo: v }); };
  const f = $("#ed-formato");
  if (f) f.onchange = () => editar({ formato: f.value });
  const r = $("#ed-renderizar");
  if (r) r.onclick = () => renderizarDoEditor(r);
  const refazer = $("#refazer-previa");
  if (refazer) refazer.onclick = pedirPrevia;
}

async function telaEditor(meu, id, n) {
  if (!id || n === undefined) { location.hash = "#episodios"; return; }
  if (!E) await carregar();
  const novo = await api(`${urlCorte(id, n)}/editor`);
  if (meu !== desenhar.n) return;
  ED = { ...novo, id, n: Number(n) };
  palSel = null;
  $("#tela").innerHTML = htmlEditor(ED);
  ligarEditor();
  rolarParaInicio();
  if (["ausente", "desatualizada"].includes(ED.previa.situacao) && ED.editavel) pedirPrevia();
  else acompanhar();
}
TELAS.editor = telaEditor;
```

- [ ] **Step 4: Botão "Editar"** — em `episodio.js`, no painel do candidato com corte (`corteDe(D, c.indice)` existe e `status` não é `na_fila`/`renderizando`): `<a class="botao mini" href="#editor/${encodeURIComponent(D.id)}/${c.indice}">Editar</a>`. Ele fica junto de "Baixar MP4"/"Copiar título" quando há Short e junto de "tentar de novo" quando o corte está em erro.

- [ ] **Step 5: CSS** (`painel.css`, com os tokens existentes)

```css
/* Editor (plano C): prévia | transcrição | ajustes; abaixo de 1100 px vira uma coluna só. */
.editor { display: grid; grid-template-columns: minmax(240px, 320px) minmax(0, 1fr) minmax(240px, 300px);
  gap: 18px; align-items: start; margin-top: 16px; }
@media (max-width: 1100px) { .editor { grid-template-columns: minmax(0, 1fr); } }
hyperframes-player.previa, .previa.vazia { display: block; width: 100%; max-width: 360px; margin: 0 auto;
  aspect-ratio: 9/16; border-radius: 12px; overflow: hidden; background: #000; }
.previa.vazia { display: grid; place-content: center; gap: 8px; text-align: center; font: 12px var(--mono); color: var(--faint); padding: 16px; }
.col-transcricao, .col-ajustes { background: var(--surface); border: 1px solid var(--line-soft); border-radius: 14px; padding: 16px; min-width: 0; }
.col-ajustes label { display: grid; gap: 6px; margin-bottom: 12px; font: 500 10.5px var(--mono); text-transform: uppercase; color: var(--faint); }
.col-ajustes h3 { font: 400 18px var(--serif); margin: 18px 0 8px; }
.ed-render { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.voltar { font: 12px var(--mono); color: var(--faint); }
.versoes { list-style: none; display: grid; gap: 6px; }
.versoes li { display: flex; gap: 10px; align-items: center; }
```

- [ ] **Step 6: `node --check` nos JS, check Python, commit**

```bash
git add web/static
git commit -m "feat: tela do editor com prévia HyperFrames no navegador e ajustes"
```

(Até as Tasks 11 e 12, `htmlTranscricao`/`ligarTranscricao`/`rolarParaInicio`/`palSel`/`htmlPlanos`/`ligarPlanos` não existem. Faça as Tasks 10, 11 e 12 em sequência antes de abrir a tela; o `node --check` passa porque ele não resolve nomes.)

---

### Task 11: Coluna de transcrição

**Files:**
- Create: `web/static/js/transcricao.js`
- Modify: `web/static/painel.css`

- [ ] **Step 1: `web/static/js/transcricao.js`**

```js
"use strict";
// Coluna de transcrição do editor: palavras em volta do corte (as de fora apagadas); clique
// seleciona e a barra de ações move início/fim para a palavra (sempre por palavra — spec §5),
// corrige o texto da legenda ou mascara (p*rra, só na legenda). Aviso quando o início depende de
// contexto (cortes.regra_inicio, pesquisa R1: erro nº 1 dos fracassos).
let palSel = null;   // índice global (palavras.json) da palavra selecionada — só local

function htmlPalavra(ed, p) {
  const cls = ["pal", p.dentro ? "dentro" : "fora", p.i === palSel ? "sel" : "", p.mascarada ? "masc" : "",
    p.editada ? "edit" : "", p.i === ed.inicio_palavra ? "ini" : "", p.i === ed.fim_palavra ? "fim" : ""]
    .filter(Boolean).join(" ");
  const dica = `${tempo(p.inicio)}${p.editada ? ` · original: ${p.original}` : ""}`;
  return `<span class="${cls}" data-i="${p.i}" tabindex="0" role="button" title="${esc(dica)}">${esc(p.texto || "∅")}</span>`;
}

function htmlAcoesPalavra(ed) {
  const p = ed.palavras.find(x => x.i === palSel);
  if (!p) return `<p class="sub">Clique numa palavra para mover o início/fim, corrigir o texto ou mascarar.</p>`;
  const dis = ed.editavel ? "" : "disabled";
  return `<div class="acoes-pal">
    <button class="botao mini" data-acao="inicio" ${dis}>Começa aqui</button>
    <button class="botao mini" data-acao="fim" ${dis}>Termina aqui</button>
    <button class="botao mini" data-acao="mascarar" ${dis}>${p.mascarada ? "Desmascarar" : "Mascarar"}</button>
    <input id="pal-texto" value="${esc(ed.corte.edicoes.legenda[p.i] ?? p.original)}" aria-label="Texto da palavra na legenda" ${dis}>
    <button class="botao mini" data-acao="texto" ${dis}>Salvar texto</button>
    ${p.editada ? `<button class="botao mini" data-acao="original" ${dis}>Original</button>` : ""}</div>`;
}

function htmlTranscricao(ed) {
  const aviso = ed.aviso_inicio
    ? `<p class="aviso-inicio">O início parece depender de contexto (abre com conectivo). Tente começar uma frase antes ou depois.</p>` : "";
  return `<div class="secao"><h2>Transcrição</h2>
      <button class="botao mini" id="mascarar-palavroes" ${ed.editavel ? "" : "disabled"}>Mascarar palavrões</button></div>
    ${aviso}${htmlAcoesPalavra(ed)}
    <div class="palavras">${ed.palavras.map(p => htmlPalavra(ed, p)).join(" ")}</div>`;
}

function acaoPalavra(acao) {
  const p = ED.palavras.find(x => x.i === palSel);
  if (!p) return;
  const pedidos = {
    inicio: () => ({ inicio_palavra: p.i }),
    fim: () => ({ fim_palavra: p.i }),
    mascarar: () => ({ mascarar: { [p.i]: !p.mascarada } }),
    texto: () => ({ legenda: { [p.i]: $("#pal-texto").value } }),
    original: () => ({ legenda: { [p.i]: null } }),
  };
  editar(pedidos[acao]());
}

// A seleção é só local: redesenha a coluna mantendo rolagem e foco, sem ir ao servidor.
function redesenharTranscricao() {
  const col = $("#ed-transcricao");
  const rolagem = $(".palavras", col)?.scrollTop ?? 0;
  col.innerHTML = htmlTranscricao(ED);
  $(".palavras", col).scrollTop = rolagem;
  ligarTranscricao();
  $(`.pal[data-i="${palSel}"]`, col)?.focus({ preventScroll: true });
}

function ligarTranscricao() {
  const col = $("#ed-transcricao");
  $$(".pal", col).forEach(el => {
    const selecionar = () => { palSel = Number(el.dataset.i); redesenharTranscricao(); };
    el.onclick = selecionar;
    el.onkeydown = ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); selecionar(); } };
  });
  const mp = $("#mascarar-palavroes", col);
  if (mp) mp.onclick = () => editar({ mascarar_palavroes: true });
  $$("[data-acao]", col).forEach(b => { b.onclick = () => acaoPalavra(b.dataset.acao); });
  const inp = $("#pal-texto", col);
  if (inp) inp.onkeydown = ev => { if (ev.key === "Enter") acaoPalavra("texto"); };
}

// Ao abrir, a primeira palavra do corte fica a um terço da altura da caixa (sem rolar a página).
function rolarParaInicio() {
  const box = $("#ed-transcricao .palavras");
  const el = box && $(".pal.ini", box);
  if (el) box.scrollTop = el.offsetTop - box.offsetTop - box.clientHeight / 3;
}
```

(`ed.corte.edicoes.legenda` chega com chaves em texto: `legenda["12"]` funciona com `p.i` numérico, porque o JS converte a chave.)

- [ ] **Step 2: CSS**

```css
.palavras { max-height: 62vh; overflow: auto; line-height: 2; font-size: 14px; margin-top: 10px; }
.pal { padding: 1px 3px; border-radius: 4px; cursor: pointer; }
.pal.fora { color: var(--faint); }
.pal.sel { background: var(--raised); outline: 1px solid var(--up); }
.pal.ini { box-shadow: inset 2px 0 0 var(--up); }
.pal.fim { box-shadow: inset -2px 0 0 var(--up); }
.pal.edit { color: var(--up); }
.pal.masc { font-style: italic; }
.pal:focus-visible { outline: 1px solid var(--up); }
.acoes-pal { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 10px; }
.acoes-pal input { flex: 1 1 120px; min-width: 0; }
.aviso-inicio { font-size: 12.5px; color: var(--warn); border-left: 2px solid var(--warn); padding: 4px 0 4px 10px; margin-top: 10px; }
```

- [ ] **Step 3: `node --check` e commit**

```bash
git add web/static
git commit -m "feat: transcrição do editor — início/fim por palavra, texto da legenda, mascarar"
```

---

### Task 12: Quem aparece

**Files:**
- Create: `web/static/js/planos.js`
- Modify: `web/static/painel.css`

- [ ] **Step 1: `web/static/js/planos.js`**

```js
"use strict";
// Quem aparece (plano C): um bloco por plano de câmera do trecho com a miniatura de cada pessoa
// detectada; clicar escolhe quem fica na tela naquele plano (padrão: o rosto mais confiável).
// Plano sem rosto segue o enquadramento do anterior (render/rosto.py trilha_fixa).
function htmlPessoas(ed, p) {
  if (!p.pessoas.length) return `<span class="sub">sem rosto — segue o plano anterior</span>`;
  const dis = ed.editavel ? "" : "disabled";
  return p.pessoas.map(s => `<button class="pessoa ${s.j === p.escolha ? "sel" : ""}" data-plano="${p.k}"
      data-pessoa="${s.j}" aria-pressed="${s.j === p.escolha}" title="${s.n} detecções${s.j === p.padrao ? " · padrão" : ""}" ${dis}>
      <img src="${esc(s.miniatura)}" alt="pessoa ${s.j + 1} no plano ${p.k + 1}" loading="lazy"></button>`).join("");
}

function htmlPlanos(ed) {
  if (!ed.planos.length) return `<p class="sub">Os planos aparecem quando a prévia ficar pronta.</p>`;
  return `<div class="planos">${ed.planos.map(p => `<div class="plano">
      <span class="num">${tempo(p.ini)}–${tempo(p.fim)}</span>
      <div class="pessoas">${htmlPessoas(ed, p)}</div></div>`).join("")}</div>`;
}

function ligarPlanos() {
  $$("#ed-ajustes .pessoa").forEach(b => {
    b.onclick = () => {
      if (b.getAttribute("aria-pressed") === "true") return;
      editar({ rosto: [Number(b.dataset.plano), Number(b.dataset.pessoa)] });
    };
  });
}
```

- [ ] **Step 2: CSS**

```css
.planos { display: grid; gap: 10px; }
.plano { display: grid; gap: 6px; }
.pessoas { display: flex; gap: 8px; flex-wrap: wrap; }
.pessoa { padding: 0; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; background: #000; cursor: pointer; }
.pessoa img { display: block; width: 64px; height: 64px; object-fit: cover; }
.pessoa.sel { box-shadow: 0 0 0 2px var(--up); border-color: var(--up); }
.pessoa:disabled { cursor: default; opacity: .6; }
```

- [ ] **Step 3: `node --check` e commit**

```bash
git add web/static
git commit -m "feat: quem aparece no editor — miniatura por pessoa e escolha por plano"
```

---

### Task 13: Conferência real e spec

**Files:**
- Modify: `tests/test_render_lento.py`, `docs/superpowers/specs/2026-10-02-producao-design.md`

- [ ] **Step 1: Lento com vários rostos.** No teste lento do plano B, depois do render, confira:
  - `ler_rosto(.../rosto.json)` é formato 2 e `planos(r)` não está vazio;
  - para cada pessoa de cada plano, chame `gerar_miniatura` com o `rodar_processo` real e confira que o arquivo existe;
  - copie as miniaturas e o MP4 para o scratchpad indicado pelo controlador, para o Davi ver.

  Rode com `CORTES_EP_REF` como no plano B:

  ```bash
  CORTES_EP_REF="C:/Users/User/Documents/Vibe Code/Cortes/episodios/c5xqNNWFT9w" PYTHONPATH=src $PY -m pytest -m lento tests/test_render_lento.py -q -s
  ```

- [ ] **Step 2: Navegador** (feito pelo controlador, não pelo subagente): painel de teste com raiz isolada (como na conferência do plano B). Abrir `#editor/<id>/<n>` e conferir:
  - a prévia toca;
  - mover o início muda a prévia depois do "preparando";
  - editar o texto de uma palavra aparece na legenda da prévia;
  - "Mascarar palavrões" funciona;
  - escolher outra pessoa num plano muda o enquadramento;
  - nada estoura em 375 px;
  - o console fica sem erro.

- [ ] **Step 3: Spec.** Em §5 "Editor", registre o que foi feito e as decisões deste plano:
  - edição por palavra, sem quebra manual de grupo;
  - prévia por `<hyperframes-player>` com o runtime injetado;
  - thread de prévias fora da fila;
  - escolhas de rosto zeradas quando início ou fim mudam;
  - "Editar" só para corte existente;
  - `alterado` no `corte.json`.

  Em §4.3, registre `edicoes`, `alterado`, `miniaturas/` e o `rosto.json` formato 2.

- [ ] **Step 4: Check e commit**

```bash
git add tests/test_render_lento.py docs
git commit -m "test: render real com vários rostos e miniaturas; spec do editor atualizada"
```
