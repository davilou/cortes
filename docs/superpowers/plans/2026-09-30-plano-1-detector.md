# Plano 1 — Fundação + Detector de Momentos

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `cortes detectar <URL> --nicho financas` baixa o episódio, transcreve na GPU, mede energia do áudio e devolve os candidatos a corte ranqueados (`candidatos.json`) com nota, justificativa e título — usando a assinatura do Claude Code via `claude -p`.

**Architecture:** Pacote Python `src/cortes/` com um módulo por etapa; cada etapa grava seu arquivo em `episodios/<id>/` e o CLI pula o que já existe (retomável). Toda lógica de decisão é função pura testada; I/O pesado (yt-dlp, ffmpeg, Whisper, `claude`) fica em funções finas com o executor injetável nos testes.

**Tech Stack:** Python 3.13 · openai-whisper (large-v3, CUDA) · torch cu130 · numpy · PyYAML · jsonschema · yt-dlp · ffmpeg (já instalado) · Claude Code CLI 2.1.x · pytest · ruff · mypy --strict

**Spec:** `docs/superpowers/specs/2026-09-30-app-cortes-design.md` (§6.1–6.4, §7). Evidência: `pesquisa/02-*.md`, `pesquisa/03-*.md`.

## Roteiro dos planos (cada um entrega software funcionando)

1. **Este plano — Detector:** URL → candidatos ranqueados. Já dá para julgar a qualidade dos momentos.
2. **Curadoria web:** aprovar/ajustar/rejeitar candidatos; gera `exemplos/*.jsonl`.
3. **Visão + falantes:** diarização, trilha de rostos, falante ativo, planos de reação.
4. **Montador + Render (Remotion):** plano de corte → primeiro Short MP4.
5. **Buscador de cenas:** deixas visuais, busca, conferência, escolha na curadoria.
6. **Retorno:** métricas dos Shorts postados → propostas de ajuste; modo automático.

## Fatos verificados que este plano usa

- `claude -p --output-format json --json-schema <schema>` devolve o JSON validado em `structured_output` e `is_error`; roda pela assinatura (testado em 2026-09-30).
- **Não existe flag documentada que impeça o CLAUDE.md global de entrar** numa chamada com OAuth. A combinação `--system-prompt … --setting-sources project --strict-mcp-config --tools ""` reduz o custo fixo de ~19,5 mil para ~3,7 mil tokens por chamada (medido). O system prompt manda ignorar instruções de perfil/vault.
- `--bare` **não** serve: pula a leitura do login OAuth.
- `claude.exe` está no PATH e é chamável por `subprocess` sem shell.
- openai-whisper com `word_timestamps=True` funciona na RTX 3090 (usado na pesquisa com `medium`).
- yt-dlp às vezes só oferece miniaturas; o cliente `android_vr` destrava, mas só em 360p.

## Estrutura de arquivos

```
Cortes/
  pyproject.toml            # deps, ruff, mypy strict, pytest, script `cortes`
  .gitignore
  CLAUDE.md                 # comando de check do projeto
  nichos/financas/
    perfil.yaml             # rubrica, bônus, penalidades, duração
    exemplos/bons.jsonl     # vazio no início; cresce com a curadoria (plano 2)
    exemplos/ruins.jsonl
  src/cortes/
    __init__.py
    tipos.py                # Palavra, Frase, Candidato
    episodio.py             # id do vídeo, pasta do episódio, JSON atômico
    llm.py                  # chamada ao `claude -p` com schema; falha alto
    ingestao.py             # yt-dlp + ffmpeg → video.mp4, audio.wav, meta.json
    transcricao.py          # Whisper → lista de Palavra
    sinais.py               # energia RMS por janela de 0,5 s
    segmentacao.py          # palavras → frases (pontuação + pausa)
    regra_inicio.py         # rejeita frase que começa com conectivo de continuação
    perfil.py               # carrega e valida perfil.yaml
    detector/
      __init__.py           # detectar(): orquestra prompt → llm → pontuação
      prompt.py             # SISTEMA, schema, texto do prompt
      pontuacao.py          # nota final e filtros (puro)
    cli.py                  # `cortes detectar URL --nicho X`
  tests/
    test_episodio.py  test_llm.py  test_ingestao.py  test_transcricao.py
    test_sinais.py    test_segmentacao.py  test_regra_inicio.py  test_perfil.py
    test_prompt.py    test_pontuacao.py    test_detector.py
```

Commits terminam com a linha:
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

---

### Task 1: Repositório, ambiente e check

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `CLAUDE.md`, `src/cortes/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Inicializar git e venv**

```bash
cd "/c/Users/User/Documents/Vibe Code/Cortes"
git init
/c/Python313/python.exe -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
```

- [ ] **Step 2: Instalar torch com CUDA ANTES do whisper** (senão o pip puxa torch CPU)

```bash
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cu130
.venv/Scripts/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```
Expected: versão `+cu130` e `True`. Se `False`, pare e investigue — o resto do plano depende da GPU.

- [ ] **Step 3: Criar `pyproject.toml`**

```toml
[project]
name = "cortes"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
  "openai-whisper",   # transcrição com tempo por palavra (testado na pesquisa)
  "numpy",            # energia do áudio
  "pyyaml",           # perfil de nicho
  "jsonschema",       # valida a saída do LLM
  "yt-dlp",           # download do episódio
]

[project.optional-dependencies]
dev = ["pytest", "ruff", "mypy", "types-PyYAML", "types-jsonschema"]

[project.scripts]
cortes = "cortes.cli:main"

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 110

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
strict = true
mypy_path = "src"

[[tool.mypy.overrides]]
module = ["whisper"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: Criar `.gitignore`**

```gitignore
.venv/
__pycache__/
*.egg-info/
.mypy_cache/
.pytest_cache/
.ruff_cache/
episodios/
pesquisa/corpus*/videos/
pesquisa/corpus*/folhas/
pesquisa/corpus*/cego/
pesquisa/corpus*/corrompidos/
pesquisa/exemplo/*.mp4
pesquisa/descoberta/
```

- [ ] **Step 5: Criar `CLAUDE.md`**

```markdown
# Cortes

App local que transforma episódios de podcast em Shorts. Spec em
`docs/superpowers/specs/2026-09-30-app-cortes-design.md`; planos em `docs/superpowers/plans/`.

## Check (rodar depois de cada mudança)

    .venv/Scripts/python -m ruff check src tests
    .venv/Scripts/python -m mypy src
    .venv/Scripts/python -m pytest -q

## Regras do projeto

- Toda decisão é função pura com teste; I/O pesado fica em funções finas com executor injetável.
- Nada de default silencioso: erro de download, LLM ou schema para o episódio com mensagem clara.
- Chamadas ao LLM usam a assinatura (`claude -p`), nunca API paga — ver `src/cortes/llm.py`.
- Regras de corte e edição citam a fonte na pesquisa (`pesquisa/0*.md`).
```

- [ ] **Step 6: Criar pacotes vazios e instalar em modo editável**

`src/cortes/__init__.py` e `tests/__init__.py` com conteúdo vazio.

```bash
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -c "import whisper, torch; print('ok', torch.cuda.is_available())"
```
Expected: `ok True`.

- [ ] **Step 7: Rodar o check vazio**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
```
Expected: ruff e mypy sem erros; pytest "no tests ran" (código 5 é aceitável aqui).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .gitignore CLAUDE.md src tests docs pesquisa/*.md pesquisa/*.py
git commit -m "chore: estrutura do projeto, check e pesquisa

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Tipos e pasta do episódio

**Files:**
- Create: `src/cortes/tipos.py`, `src/cortes/episodio.py`
- Test: `tests/test_episodio.py`

- [ ] **Step 1: Escrever o teste**

```python
# tests/test_episodio.py
from pathlib import Path

import pytest

from cortes.episodio import id_do_video, ler_json, pasta, salvar_json


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=idiB5Far8eA",
    "https://youtu.be/idiB5Far8eA",
    "https://www.youtube.com/shorts/idiB5Far8eA",
    "https://www.youtube.com/live/idiB5Far8eA?si=x",
    "https://www.youtube.com/watch?v=idiB5Far8eA&t=120s",
])
def test_id_do_video_aceita_formatos(url: str) -> None:
    assert id_do_video(url) == "idiB5Far8eA"


def test_id_do_video_rejeita_url_sem_id() -> None:
    with pytest.raises(ValueError, match="sem id"):
        id_do_video("https://www.youtube.com/@canal")


def test_pasta_cria_diretorio(tmp_path: Path) -> None:
    p = pasta("abc", raiz=tmp_path)
    assert p == tmp_path / "abc" and p.is_dir()


def test_salvar_e_ler_json_ida_e_volta(tmp_path: Path) -> None:
    alvo = tmp_path / "x.json"
    salvar_json(alvo, {"á": [1, 2]})
    assert ler_json(alvo) == {"á": [1, 2]}
    assert not (tmp_path / "x.json.tmp").exists()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_episodio.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cortes.episodio'`

- [ ] **Step 3: Implementar `tipos.py`**

```python
# src/cortes/tipos.py
"""Tipos compartilhados entre as etapas do pipeline."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Palavra:
    texto: str
    inicio: float
    fim: float


@dataclass(frozen=True)
class Frase:
    indice: int
    texto: str
    inicio: float
    fim: float


@dataclass(frozen=True)
class Candidato:
    frase_inicio: int
    frase_fim: int
    inicio: float
    fim: float
    notas: dict[str, int]
    bonus: list[str]
    penalidades: list[str]
    justificativa: str
    titulo: str
    nota_final: float
```

- [ ] **Step 4: Implementar `episodio.py`**

```python
# src/cortes/episodio.py
"""Identidade e pasta de trabalho de um episódio; gravação atômica de JSON."""
import json
import re
from pathlib import Path
from typing import Any

RAIZ_EPISODIOS = Path("episodios")
_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|live/)([A-Za-z0-9_-]{11})")


def id_do_video(url: str) -> str:
    m = _ID.search(url)
    if not m:
        raise ValueError(f"URL sem id de vídeo do YouTube: {url}")
    return m.group(1)


def pasta(ep_id: str, raiz: Path = RAIZ_EPISODIOS) -> Path:
    p = raiz / ep_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def salvar_json(caminho: Path, dados: Any) -> None:
    """Grava em .tmp e renomeia: um arquivo nunca fica pela metade se o processo cair."""
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(caminho)


def ler_json(caminho: Path) -> Any:
    return json.loads(caminho.read_text(encoding="utf-8"))
```

- [ ] **Step 5: Rodar e ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_episodio.py -q`
Expected: 8 passed

- [ ] **Step 6: Check + commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src
git add src/cortes/tipos.py src/cortes/episodio.py tests/test_episodio.py
git commit -m "feat: tipos do pipeline e pasta do episódio

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Chamada ao LLM pela assinatura

**Files:**
- Create: `src/cortes/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: Escrever o teste**

```python
# tests/test_llm.py
import json
from typing import Any

import pytest

from cortes.llm import ErroLLM, chamar, montar_comando

SCHEMA: dict[str, Any] = {
    "type": "object", "required": ["nota"], "additionalProperties": False,
    "properties": {"nota": {"type": "integer", "minimum": 1, "maximum": 5}},
}


def executor_que_devolve(resposta: dict[str, Any]):  # type: ignore[no-untyped-def]
    chamadas: list[tuple[list[str], str]] = []

    def executar(args: list[str], entrada: str) -> str:
        chamadas.append((args, entrada))
        return json.dumps(resposta)

    executar.chamadas = chamadas  # type: ignore[attr-defined]
    return executar


def test_devolve_structured_output_valido() -> None:
    ex = executor_que_devolve({"is_error": False, "structured_output": {"nota": 4}})
    assert chamar("prompt", SCHEMA, "sistema", executar=ex) == {"nota": 4}
    args, entrada = ex.chamadas[0]
    assert entrada == "prompt"
    assert args[:2] == ["claude", "-p"]


def test_is_error_levanta() -> None:
    ex = executor_que_devolve({"is_error": True, "result": "limite de uso atingido"})
    with pytest.raises(ErroLLM, match="limite de uso"):
        chamar("p", SCHEMA, "s", executar=ex)


def test_sem_structured_output_levanta() -> None:
    ex = executor_que_devolve({"is_error": False, "result": "texto solto"})
    with pytest.raises(ErroLLM, match="structured_output"):
        chamar("p", SCHEMA, "s", executar=ex)


def test_fora_do_schema_levanta() -> None:
    ex = executor_que_devolve({"is_error": False, "structured_output": {"nota": 9}})
    with pytest.raises(ErroLLM, match="fora do schema"):
        chamar("p", SCHEMA, "s", executar=ex)


def test_saida_nao_json_levanta() -> None:
    with pytest.raises(ErroLLM, match="não é JSON"):
        chamar("p", SCHEMA, "s", executar=lambda a, e: "Error: not logged in")


def test_comando_isola_contexto_e_nao_usa_bare() -> None:
    cmd = montar_comando("sis", SCHEMA, "sonnet")
    assert "--bare" not in cmd
    for flag in ["--system-prompt", "--setting-sources", "--strict-mcp-config",
                 "--no-session-persistence", "--json-schema"]:
        assert flag in cmd
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--setting-sources") + 1] == "project"
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == SCHEMA
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_llm.py -q`
Expected: FAIL — `No module named 'cortes.llm'`

- [ ] **Step 3: Implementar**

```python
# src/cortes/llm.py
"""Chamada ao Claude pela assinatura do Claude Code (`claude -p`), com saída validada por schema.

Não usa --bare: esse modo pula a leitura do login OAuth. Não há flag que impeça o CLAUDE.md
global de entrar; --setting-sources project + --strict-mcp-config + --system-prompt reduzem o
custo fixo para ~3,7 mil tokens por chamada (medido em 2026-09-30).
"""
import json
import subprocess
from collections.abc import Callable
from typing import Any

import jsonschema

Executor = Callable[[list[str], str], str]
TIMEOUT_S = 900


class ErroLLM(RuntimeError):
    pass


def montar_comando(sistema: str, schema: dict[str, Any], modelo: str) -> list[str]:
    return [
        "claude", "-p",
        "--output-format", "json",
        "--json-schema", json.dumps(schema, ensure_ascii=False),
        "--system-prompt", sistema,
        "--setting-sources", "project",
        "--strict-mcp-config",
        "--tools", "",
        "--no-session-persistence",
        "--model", modelo,
    ]


def _executar(args: list[str], entrada: str) -> str:
    r = subprocess.run(args, input=entrada, capture_output=True, text=True,
                       encoding="utf-8", timeout=TIMEOUT_S)
    if r.returncode != 0 and not r.stdout.strip():
        raise ErroLLM(f"claude saiu com código {r.returncode}: {r.stderr[-500:]}")
    return r.stdout


def chamar(prompt: str, schema: dict[str, Any], sistema: str, modelo: str = "sonnet",
           executar: Executor = _executar) -> dict[str, Any]:
    saida = executar(montar_comando(sistema, schema, modelo), prompt)
    try:
        resposta = json.loads(saida)
    except json.JSONDecodeError as e:
        raise ErroLLM(f"saída do CLI não é JSON: {saida[:300]}") from e
    if resposta.get("is_error"):
        raise ErroLLM(f"CLI reportou erro: {str(resposta.get('result', ''))[:500]}")
    dados = resposta.get("structured_output")
    if not isinstance(dados, dict):
        raise ErroLLM("resposta sem structured_output")
    try:
        jsonschema.validate(dados, schema)
    except jsonschema.ValidationError as e:
        raise ErroLLM(f"structured_output fora do schema: {e.message}") from e
    return dados
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_llm.py -q`
Expected: 6 passed

- [ ] **Step 5: Teste real rápido (1 chamada, gasta cota mínima)**

```bash
.venv/Scripts/python -c "
from cortes.llm import chamar
s={'type':'object','required':['nota'],'properties':{'nota':{'type':'integer','minimum':1,'maximum':5}}}
print(chamar('Dê nota 1-5 para o gancho: Nenhuma força aérea do mundo luta contra os EUA.', s, 'Você avalia ganchos de Shorts. Responda só no schema.', 'haiku'))"
```
Expected: `{'nota': <1-5>}`. Se falhar com erro de login, rode `claude` interativo uma vez para logar.

- [ ] **Step 6: Check + commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src
git add src/cortes/llm.py tests/test_llm.py
git commit -m "feat: chamada ao Claude pela assinatura com schema obrigatório

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Ingestão (download + áudio + meta)

**Files:**
- Create: `src/cortes/ingestao.py`
- Test: `tests/test_ingestao.py`

- [ ] **Step 1: Escrever o teste** (só as decisões puras; o download real é verificado na Task 12)

```python
# tests/test_ingestao.py
import sys
from pathlib import Path

import pytest

from cortes.ingestao import ALTURA_MINIMA, ErroIngestao, comando_download, extrair_meta, \
    precisa_cliente_alternativo, validar_altura


def test_comando_padrao_pede_1080_e_info_json(tmp_path: Path) -> None:
    cmd = comando_download("https://youtu.be/x", tmp_path, cliente=None)
    assert cmd[:3] == [sys.executable, "-m", "yt_dlp"]
    assert "--write-info-json" in cmd and "--extractor-args" not in cmd
    assert "height<=1080" in cmd[cmd.index("-f") + 1]
    assert cmd[-1] == "https://youtu.be/x"


def test_comando_com_cliente_alternativo(tmp_path: Path) -> None:
    cmd = comando_download("u", tmp_path, cliente="android_vr")
    assert cmd[cmd.index("--extractor-args") + 1] == "youtube:player_client=android_vr"


@pytest.mark.parametrize("stderr,esperado", [
    ("ERROR: [youtube] abc: Requested format is not available. Use --list-formats", True),
    ("WARNING: Only images are available for download", True),
    ("ERROR: Sign in to confirm you're not a bot", False),
    ("", False),
])
def test_precisa_cliente_alternativo(stderr: str, esperado: bool) -> None:
    assert precisa_cliente_alternativo(stderr) is esperado


def test_validar_altura_recusa_baixa_resolucao() -> None:
    validar_altura(ALTURA_MINIMA)
    with pytest.raises(ErroIngestao, match="360"):
        validar_altura(360)


def test_extrair_meta() -> None:
    info = {"title": "Ep 1", "channel": "Podcast", "duration": 3600, "upload_date": "20260901",
            "id": "abc", "outros": "ignorado"}
    assert extrair_meta(info) == {"titulo": "Ep 1", "canal": "Podcast", "duracao_s": 3600,
                                  "data": "20260901", "id": "abc"}
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_ingestao.py -q`
Expected: FAIL — `No module named 'cortes.ingestao'`

- [ ] **Step 3: Implementar**

```python
# src/cortes/ingestao.py
"""Baixa o episódio (yt-dlp), extrai o áudio (ffmpeg) e grava meta.json.

O YouTube às vezes só entrega miniaturas ao cliente padrão; o cliente android_vr destrava,
mas pode vir em baixa resolução — por isso a altura final é validada (qualidade > economia).
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from cortes.episodio import salvar_json

FORMATO = "bv*[height<=1080]+ba/b[height<=1080]"
ALTURA_MINIMA = 720
CLIENTE_ALTERNATIVO = "android_vr"


class ErroIngestao(RuntimeError):
    pass


def comando_download(url: str, destino: Path, cliente: str | None) -> list[str]:
    args = [sys.executable, "-m", "yt_dlp", "-f", FORMATO, "--merge-output-format", "mp4",
            "--write-info-json", "--no-progress", "--sleep-requests", "1.5",
            "-o", str(destino / "video.%(ext)s")]
    if cliente:
        args += ["--extractor-args", f"youtube:player_client={cliente}"]
    return args + [url]


def precisa_cliente_alternativo(stderr: str) -> bool:
    return "Requested format is not available" in stderr or "Only images are available" in stderr


def validar_altura(altura: int) -> None:
    if altura < ALTURA_MINIMA:
        raise ErroIngestao(f"só há vídeo em {altura}p (mínimo {ALTURA_MINIMA}p); tente mais tarde")


def extrair_meta(info: dict[str, Any]) -> dict[str, Any]:
    return {"titulo": info["title"], "canal": info["channel"], "duracao_s": info["duration"],
            "data": info["upload_date"], "id": info["id"]}


def _rodar(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _altura(video: Path) -> int:
    r = _rodar(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                "stream=height", "-of", "csv=p=0", str(video)])
    if r.returncode != 0:
        raise ErroIngestao(f"ffprobe falhou em {video}: {r.stderr[-300:]}")
    return int(r.stdout.strip())


def baixar(url: str, destino: Path) -> None:
    r = _rodar(comando_download(url, destino, cliente=None))
    if r.returncode != 0 and precisa_cliente_alternativo(r.stderr):
        r = _rodar(comando_download(url, destino, cliente=CLIENTE_ALTERNATIVO))
    if r.returncode != 0:
        raise ErroIngestao(f"yt-dlp falhou: {r.stderr[-500:]}")
    video = destino / "video.mp4"
    validar_altura(_altura(video))
    info = json.loads((destino / "video.info.json").read_text(encoding="utf-8"))
    salvar_json(destino / "meta.json", extrair_meta(info))


def extrair_audio(destino: Path) -> None:
    r = _rodar(["ffmpeg", "-y", "-v", "error", "-i", str(destino / "video.mp4"),
                "-ac", "1", "-ar", "16000", str(destino / "audio.wav")])
    if r.returncode != 0:
        raise ErroIngestao(f"ffmpeg falhou ao extrair áudio: {r.stderr[-300:]}")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_ingestao.py -q`
Expected: 8 passed

- [ ] **Step 5: Check + commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src
git add src/cortes/ingestao.py tests/test_ingestao.py
git commit -m "feat: ingestão com fallback de cliente e validação de resolução

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Transcrição

**Files:**
- Create: `src/cortes/transcricao.py`
- Test: `tests/test_transcricao.py`

- [ ] **Step 1: Escrever o teste**

```python
# tests/test_transcricao.py
import pytest

from cortes.tipos import Palavra
from cortes.transcricao import palavras_de_segmentos


def test_achata_segmentos_e_limpa_espacos() -> None:
    segs = [
        {"words": [{"word": " Eu", "start": 0.0, "end": 0.2}, {"word": " avisei,", "start": 0.2, "end": 0.61234}]},
        {"words": [{"word": " tiozão.", "start": 0.7, "end": 1.1}]},
    ]
    assert palavras_de_segmentos(segs) == [
        Palavra("Eu", 0.0, 0.2), Palavra("avisei,", 0.2, 0.612), Palavra("tiozão.", 0.7, 1.1)]


def test_descarta_palavra_vazia() -> None:
    segs = [{"words": [{"word": "  ", "start": 0.0, "end": 0.1}, {"word": "oi", "start": 0.1, "end": 0.2}]}]
    assert palavras_de_segmentos(segs) == [Palavra("oi", 0.1, 0.2)]


def test_sem_palavras_levanta() -> None:
    with pytest.raises(ValueError, match="sem palavras"):
        palavras_de_segmentos([{"words": []}])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_transcricao.py -q`
Expected: FAIL — `No module named 'cortes.transcricao'`

- [ ] **Step 3: Implementar**

```python
# src/cortes/transcricao.py
"""Whisper large-v3 na GPU, com tempo por palavra."""
from pathlib import Path
from typing import Any

from cortes.tipos import Palavra

MODELO = "large-v3"


def palavras_de_segmentos(segmentos: list[dict[str, Any]]) -> list[Palavra]:
    palavras = [
        Palavra(w["word"].strip(), round(float(w["start"]), 3), round(float(w["end"]), 3))
        for seg in segmentos for w in seg.get("words", []) if w["word"].strip()
    ]
    if not palavras:
        raise ValueError("transcrição sem palavras")
    return palavras


def transcrever(audio: Path, modelo: str = MODELO) -> list[Palavra]:
    import whisper  # import tardio: só carrega torch quando a etapa roda

    m = whisper.load_model(modelo, device="cuda")
    r = m.transcribe(str(audio), language="pt", word_timestamps=True, fp16=True)
    return palavras_de_segmentos(r["segments"])
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_transcricao.py -q`
Expected: 3 passed

- [ ] **Step 5: Check + commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src
git add src/cortes/transcricao.py tests/test_transcricao.py
git commit -m "feat: transcrição com tempo por palavra

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Sinais de áudio (energia)

**Files:**
- Create: `src/cortes/sinais.py`
- Test: `tests/test_sinais.py`

- [ ] **Step 1: Escrever o teste**

```python
# tests/test_sinais.py
import numpy as np
import pytest

from cortes.sinais import energia_por_janela


def test_energia_rms_por_janela() -> None:
    taxa = 100  # janela de 0,5 s = 50 amostras
    silencio = np.zeros(50, dtype=np.float32)
    alto = np.full(50, 0.5, dtype=np.float32)
    sobra = np.ones(10, dtype=np.float32)  # incompleta: descartada
    e = energia_por_janela(np.concatenate([silencio, alto, sobra]), taxa=taxa)
    assert e == [0.0, 0.5]


def test_audio_curto_demais_levanta() -> None:
    with pytest.raises(ValueError, match="mais curto"):
        energia_por_janela(np.zeros(10, dtype=np.float32), taxa=100)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_sinais.py -q`
Expected: FAIL — `No module named 'cortes.sinais'`

- [ ] **Step 3: Implementar**

```python
# src/cortes/sinais.py
"""Energia RMS do áudio por janela de 0,5 s (spec §6.3). Risada entra no nicho de humor."""
import subprocess
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

JANELA_S = 0.5
TAXA = 16000


def ler_wav_mono(audio: Path, taxa: int = TAXA) -> NDArray[np.float32]:
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-f", "f32le", "-ac", "1",
                        "-ar", str(taxa), "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def energia_por_janela(amostras: NDArray[np.float32], taxa: int = TAXA,
                       janela_s: float = JANELA_S) -> list[float]:
    n = int(taxa * janela_s)
    k = len(amostras) // n
    if k == 0:
        raise ValueError("áudio mais curto que uma janela")
    blocos = amostras[: k * n].astype(np.float64).reshape(k, n)
    return [round(float(x), 5) for x in np.sqrt((blocos ** 2).mean(axis=1))]
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_sinais.py -q`
Expected: 2 passed

- [ ] **Step 5: Check + commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src
git add src/cortes/sinais.py tests/test_sinais.py
git commit -m "feat: energia do áudio por janela

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Segmentação em frases

**Files:**
- Create: `src/cortes/segmentacao.py`
- Test: `tests/test_segmentacao.py`

- [ ] **Step 1: Escrever o teste**

```python
# tests/test_segmentacao.py
from cortes.segmentacao import frases
from cortes.tipos import Frase, Palavra


def p(t: str, i: float, f: float) -> Palavra:
    return Palavra(t, i, f)


def test_corta_na_pontuacao_final() -> None:
    ws = [p("Eu", 0, .2), p("avisei.", .2, .5), p("Ele", .6, .8), p("bateu?", .8, 1.0)]
    assert frases(ws) == [Frase(0, "Eu avisei.", 0, .5), Frase(1, "Ele bateu?", .6, 1.0)]


def test_corta_na_pausa_longa_sem_pontuacao() -> None:
    ws = [p("tanto", 0, .3), p("de", .3, .4), p("carro", 1.5, 1.8)]
    assert [f.texto for f in frases(ws, pausa_s=0.8)] == ["tanto de", "carro"]


def test_virgula_nao_corta() -> None:
    ws = [p("Eu", 0, .1), p("avisei,", .1, .3), p("tiozão.", .35, .6)]
    assert len(frases(ws)) == 1


def test_ultima_frase_sem_pontuacao_fecha() -> None:
    assert frases([p("fim", 0, .2)]) == [Frase(0, "fim", 0, .2)]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_segmentacao.py -q`
Expected: FAIL — `No module named 'cortes.segmentacao'`

- [ ] **Step 3: Implementar**

```python
# src/cortes/segmentacao.py
"""Agrupa palavras em frases: fecha na pontuação final ou numa pausa longa (spec §6.4.1)."""
from cortes.tipos import Frase, Palavra

FIM_DE_FRASE = (".", "?", "!", "…")
PAUSA_S = 0.8


def frases(palavras: list[Palavra], pausa_s: float = PAUSA_S) -> list[Frase]:
    saida: list[Frase] = []
    atual: list[Palavra] = []
    for i, w in enumerate(palavras):
        atual.append(w)
        prox = palavras[i + 1] if i + 1 < len(palavras) else None
        if prox is None or w.texto.endswith(FIM_DE_FRASE) or prox.inicio - w.fim >= pausa_s:
            saida.append(Frase(len(saida), " ".join(x.texto for x in atual), atual[0].inicio, atual[-1].fim))
            atual = []
    return saida
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_segmentacao.py -q`
Expected: 4 passed

- [ ] **Step 5: Check + commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src
git add src/cortes/segmentacao.py tests/test_segmentacao.py
git commit -m "feat: segmentação de palavras em frases

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Regra de início (não começar no meio)

A pesquisa achou "começa no meio da frase" como o erro nº 1 dos fracassos (R1: 12 × 4). Aqui fica a
parte que código resolve com segurança: frase que abre com **conectivo de continuação**. Pronome sem
referente e contexto implícito ficam para o LLM (nota `autocontido`). "Então" fica de fora de propósito:
em PT-BR falado ele abre história com frequência ("Então, eu vendi a casa").

**Files:**
- Create: `src/cortes/regra_inicio.py`
- Test: `tests/test_regra_inicio.py`

- [ ] **Step 1: Escrever o teste** (casos reais do corpus da pesquisa)

```python
# tests/test_regra_inicio.py
import pytest

from cortes.regra_inicio import comeca_no_meio


@pytest.mark.parametrize("texto", [
    "Também seguindo aquela... é quase um",          # R1, fundo, 491 views
    "Mas como é que foi família",                     # R1, fundo, 14 views
    "Até chegar na digital.",                          # R1, fundo
    "E o carro do vizinho também.",
    "Só que ninguém fala disso.",
    "Porque o juro lá é outro.",
    "Aí ele pegou e vendeu.",
    "— Mas não é bem assim.",
])
def test_detecta_continuacao(texto: str) -> None:
    assert comeca_no_meio(texto) is True


@pytest.mark.parametrize("texto", [
    "Nenhuma força aérea do mundo tem capacidade",     # R2, top 1,3 mi
    "Cara, não sei se eu deveria falar",               # R1, top 696 mil
    "Eu avisei, tiozão, não faz isso não",             # exemplo Hype Automotivo
    "Sabe como é que é o financiamento na Europa?",    # R1, top 762 mil
    "Mais de um milhão de pessoas perderam",           # "mais" ≠ "mas"
    "Maria vendeu tudo.",                              # "Ma..." não é "mas"
    "Então, eu vendi a minha casa.",                   # "então" abre história
    "Empresário que quebra duas vezes",                # "E..." dentro da palavra
])
def test_aceita_inicio_autonomo(texto: str) -> None:
    assert comeca_no_meio(texto) is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_regra_inicio.py -q`
Expected: FAIL — `No module named 'cortes.regra_inicio'`

- [ ] **Step 3: Implementar**

```python
# src/cortes/regra_inicio.py
"""Rejeita candidato que abre com conectivo de continuação (pesquisa R1: erro nº 1 dos fracassos)."""
import re

_CONECTIVO = re.compile(
    r"^(mas|também|e aí|aí|daí|e|só que|porque|até|ou seja|inclusive|pois)\b", re.IGNORECASE)
_LIXO_INICIAL = "-—–…\"'“” "


def comeca_no_meio(texto: str) -> bool:
    return bool(_CONECTIVO.match(texto.lstrip(_LIXO_INICIAL)))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_regra_inicio.py -q`
Expected: 16 passed

- [ ] **Step 5: Check + commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src
git add src/cortes/regra_inicio.py tests/test_regra_inicio.py
git commit -m "feat: regra dura de início com casos do corpus

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Perfil de nicho

**Files:**
- Create: `src/cortes/perfil.py`, `nichos/financas/perfil.yaml`, `nichos/financas/exemplos/bons.jsonl` (vazio), `nichos/financas/exemplos/ruins.jsonl` (vazio)
- Test: `tests/test_perfil.py`

- [ ] **Step 1: Escrever o teste**

```python
# tests/test_perfil.py
from pathlib import Path

import pytest

from cortes.perfil import carregar_perfil

YAML_OK = """
nicho: teste
filtro_tema: "É sobre dinheiro."
rubrica: {gancho_3s: 0.3, autocontido: 0.25, espanto: 0.2, historia_ou_virada: 0.1, fechamento: 0.15}
bonus: [numero_ou_dado]
penalidade: [palestra_ou_palco]
duracao_s: {min: 20, max: 90}
"""


def criar(tmp: Path, yaml: str, bons: str = "", ruins: str = "") -> Path:
    (tmp / "exemplos").mkdir()
    (tmp / "perfil.yaml").write_text(yaml, encoding="utf-8")
    (tmp / "exemplos" / "bons.jsonl").write_text(bons, encoding="utf-8")
    (tmp / "exemplos" / "ruins.jsonl").write_text(ruins, encoding="utf-8")
    return tmp


def test_carrega_perfil_valido(tmp_path: Path) -> None:
    p = carregar_perfil(criar(tmp_path, YAML_OK, bons='{"texto": "a", "motivo": "b"}\n'))
    assert p.nicho == "teste" and p.duracao_min == 20 and p.duracao_max == 90
    assert p.rubrica["gancho_3s"] == 0.3
    assert p.exemplos_bons == [{"texto": "a", "motivo": "b"}] and p.exemplos_ruins == []


def test_pesos_que_nao_somam_1_levantam(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="somam"):
        carregar_perfil(criar(tmp_path, YAML_OK.replace("0.15}", "0.5}")))


def test_criterio_desconhecido_levanta(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="critérios"):
        carregar_perfil(criar(tmp_path, YAML_OK.replace("fechamento", "outro")))


def test_sem_arquivo_de_exemplos_levanta(tmp_path: Path) -> None:
    (tmp_path / "perfil.yaml").write_text(YAML_OK, encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        carregar_perfil(tmp_path)


def test_perfil_financas_do_repo_e_valido() -> None:
    p = carregar_perfil(Path("nichos/financas"))
    assert p.nicho == "financas"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_perfil.py -q`
Expected: FAIL — `No module named 'cortes.perfil'`

- [ ] **Step 3: Implementar `perfil.py`**

```python
# src/cortes/perfil.py
"""Perfil de nicho: o que cortar (spec §4.1)."""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CRITERIOS = ("gancho_3s", "autocontido", "espanto", "historia_ou_virada", "fechamento")


@dataclass(frozen=True)
class Perfil:
    nicho: str
    filtro_tema: str
    rubrica: dict[str, float]
    bonus: list[str]
    penalidade: list[str]
    duracao_min: float
    duracao_max: float
    exemplos_bons: list[dict[str, Any]]
    exemplos_ruins: list[dict[str, Any]]


def _jsonl(caminho: Path) -> list[dict[str, Any]]:
    linhas = caminho.read_text(encoding="utf-8").splitlines()  # ausente → FileNotFoundError
    return [json.loads(l) for l in linhas if l.strip()]


def carregar_perfil(pasta_nicho: Path) -> Perfil:
    d = yaml.safe_load((pasta_nicho / "perfil.yaml").read_text(encoding="utf-8"))
    rubrica = {k: float(v) for k, v in d["rubrica"].items()}
    if set(rubrica) != set(CRITERIOS):
        raise ValueError(f"critérios da rubrica devem ser {CRITERIOS}, vieram {sorted(rubrica)}")
    if abs(sum(rubrica.values()) - 1.0) > 1e-6:
        raise ValueError(f"pesos da rubrica somam {sum(rubrica.values())}, deveriam somar 1")
    dur = d["duracao_s"]
    if not 0 < dur["min"] < dur["max"]:
        raise ValueError(f"duração inválida: {dur}")
    return Perfil(
        nicho=d["nicho"], filtro_tema=d["filtro_tema"], rubrica=rubrica,
        bonus=list(d["bonus"]), penalidade=list(d["penalidade"]),
        duracao_min=float(dur["min"]), duracao_max=float(dur["max"]),
        exemplos_bons=_jsonl(pasta_nicho / "exemplos" / "bons.jsonl"),
        exemplos_ruins=_jsonl(pasta_nicho / "exemplos" / "ruins.jsonl"),
    )
```

- [ ] **Step 4: Criar `nichos/financas/perfil.yaml`**

```yaml
# Perfil de nicho: finanças PT-BR. Fontes: pesquisa/02-corpus-financas.md (R1) e 03 (R2).
nicho: financas
filtro_tema: >-
  O trecho é sobre dinheiro: ganhar, perder, gastar, investir, salário, preço, patrimônio,
  negócio, economia ou quanto alguém ganha. Vale em podcast de qualquer assunto.
rubrica:                 # R1 6/6 e R2 8×4 (gancho, autocontido); espanto R1 9×0; fechamento R2 8×2
  gancho_3s: 0.30
  autocontido: 0.25
  espanto: 0.20
  historia_ou_virada: 0.10
  fechamento: 0.15
bonus:                   # R1/R2: número no gancho 15·7·2%; humor 18·8%; famoso 6×3 canais
  - numero_ou_dado
  - dinheiro_alheio_quanto_ganha
  - humor
  - personagem_famoso_citado
  - conversa_de_estudio
penalidade:              # R1: utilidade 8×14; R2: motivacional 13·25%, palestra 5·11·12%
  - utilidade_sem_surpresa
  - motivacional_sem_espanto
  - palestra_ou_palco
duracao_s: {min: 20, max: 90}   # 01-pesquisa-documental: YouTube diz que não há duração mágica
```

Criar `nichos/financas/exemplos/bons.jsonl` e `ruins.jsonl` vazios.

- [ ] **Step 5: Rodar e ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_perfil.py -q`
Expected: 5 passed

- [ ] **Step 6: Check + commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src
git add src/cortes/perfil.py tests/test_perfil.py nichos
git commit -m "feat: perfil de nicho de finanças com fontes da pesquisa

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Prompt e schema do detector

**Files:**
- Create: `src/cortes/detector/__init__.py` (vazio por enquanto), `src/cortes/detector/prompt.py`
- Test: `tests/test_prompt.py`

- [ ] **Step 1: Escrever o teste**

```python
# tests/test_prompt.py
import jsonschema
import pytest

from cortes.detector.prompt import formatar_transcricao, montar_prompt, schema_candidatos
from cortes.perfil import CRITERIOS, Perfil
from cortes.tipos import Frase

PERFIL = Perfil("financas", "É sobre dinheiro.", dict.fromkeys(CRITERIOS, 0.2), ["humor"],
                ["palestra_ou_palco"], 20, 90, [{"texto": "bom", "motivo": "espanto"}], [])
FRASES = [Frase(0, "Eu avisei.", 0.0, 1.2), Frase(1, "Ele bateu o carro.", 65.5, 67.0)]


def test_formatar_transcricao_numera_e_marca_tempo() -> None:
    assert formatar_transcricao(FRASES) == "[F0 00:00] Eu avisei.\n[F1 01:05] Ele bateu o carro."


def test_prompt_traz_tema_criterios_bonus_exemplos_e_transcricao() -> None:
    txt = montar_prompt(FRASES, PERFIL)
    for trecho in ["É sobre dinheiro.", "gancho_3s", "humor", "palestra_ou_palco", "bom",
                   "[F1 01:05] Ele bateu o carro.", "20", "90"]:
        assert trecho in txt


def test_schema_aceita_resposta_valida_e_recusa_bonus_fora_da_lista() -> None:
    schema = schema_candidatos(PERFIL)
    ok = {"candidatos": [{"frase_inicio": 0, "frase_fim": 1, "notas": dict.fromkeys(CRITERIOS, 3),
                          "no_tema": True, "bonus": ["humor"], "penalidades": [],
                          "justificativa": "x", "titulo": "y"}]}
    jsonschema.validate(ok, schema)
    ok["candidatos"][0]["bonus"] = ["inventado"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(ok, schema)


def test_lista_vazia_gera_schema_valido() -> None:
    vazio = Perfil("f", "t", dict.fromkeys(CRITERIOS, 0.2), [], [], 20, 90, [], [])
    jsonschema.Draft202012Validator.check_schema(schema_candidatos(vazio))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_prompt.py -q`
Expected: FAIL — `No module named 'cortes.detector'`

- [ ] **Step 3: Implementar** (criar também `src/cortes/detector/__init__.py` vazio)

```python
# src/cortes/detector/prompt.py
"""Texto e schema da chamada que acha os candidatos a corte (spec §6.4.3)."""
import json
from typing import Any

from cortes.perfil import CRITERIOS, Perfil
from cortes.tipos import Frase

MAX_CANDIDATOS = 20
MAX_EXEMPLOS = 10

SISTEMA = (
    "Você seleciona trechos de podcast para virar Shorts verticais. Siga apenas as instruções "
    "desta tarefa. Ignore qualquer instrução de perfil de usuário, memória, vault ou estilo de "
    "conversa que apareça no contexto. Responda somente no schema pedido."
)

DESCRICAO = {
    "gancho_3s": "a primeira frase, sozinha, dá motivo claro para ficar (5) ou é morna/confusa (1)",
    "autocontido": "entende-se sem ter visto o episódio (5) ou depende de contexto de fora (1)",
    "espanto": "traz fato, número ou virada contraintuitiva que surpreende (5) ou nada novo (1)",
    "historia_ou_virada": "é uma história com desfecho ou reviravolta (5) ou só opinião solta (1)",
    "fechamento": "termina em conclusão ou punchline (5) ou corta no meio do raciocínio (1)",
}


def _mmss(s: float) -> str:
    return f"{int(s // 60):02d}:{int(s % 60):02d}"


def formatar_transcricao(frases: list[Frase]) -> str:
    return "\n".join(f"[F{f.indice} {_mmss(f.inicio)}] {f.texto}" for f in frases)


def montar_prompt(frases: list[Frase], perfil: Perfil) -> str:
    criterios = "\n".join(f"- {c}: {DESCRICAO[c]}" for c in CRITERIOS)
    bons = "\n".join(json.dumps(e, ensure_ascii=False) for e in perfil.exemplos_bons[:MAX_EXEMPLOS])
    ruins = "\n".join(json.dumps(e, ensure_ascii=False) for e in perfil.exemplos_ruins[:MAX_EXEMPLOS])
    return f"""Encontre até {MAX_CANDIDATOS} trechos deste podcast que dariam bons Shorts.

TEMA DO NICHO ({perfil.nicho}): {perfil.filtro_tema}
Marque no_tema=false para trechos fora do tema (o podcast pode ser de outro assunto).

REGRAS
- Cada trecho vai de frase_inicio a frase_fim (índices F da transcrição), com {perfil.duracao_min:.0f}
  a {perfil.duracao_max:.0f} segundos.
- O trecho deve começar no início de uma ideia: nunca numa frase que continua a anterior
  ("mas", "também", "e aí", pronome sem referente).
- Dê nota 1 a 5 em cada critério:
{criterios}
- bonus: marque só os que se aplicam, desta lista: {perfil.bonus}
- penalidades: marque só as que se aplicam, desta lista: {perfil.penalidade}
- justificativa: uma frase dizendo por que o trecho segura quem está rolando o feed.
- titulo: título curto para a capa do Short.

EXEMPLOS APROVADOS ANTES (se houver):
{bons or "(nenhum ainda)"}

EXEMPLOS REJEITADOS ANTES, COM MOTIVO (se houver):
{ruins or "(nenhum ainda)"}

TRANSCRIÇÃO:
{formatar_transcricao(frases)}
"""


def _lista_fechada(opcoes: list[str]) -> dict[str, Any]:
    """Array cujos itens só podem vir da lista; lista vazia → array vazio (enum [] é schema inválido)."""
    if not opcoes:
        return {"type": "array", "maxItems": 0}
    return {"type": "array", "items": {"enum": opcoes}}


def schema_candidatos(perfil: Perfil) -> dict[str, Any]:
    nota = {"type": "integer", "minimum": 1, "maximum": 5}
    item = {
        "type": "object", "additionalProperties": False,
        "required": ["frase_inicio", "frase_fim", "notas", "no_tema", "bonus", "penalidades",
                     "justificativa", "titulo"],
        "properties": {
            "frase_inicio": {"type": "integer", "minimum": 0},
            "frase_fim": {"type": "integer", "minimum": 0},
            "notas": {"type": "object", "additionalProperties": False, "required": list(CRITERIOS),
                      "properties": {c: nota for c in CRITERIOS}},
            "no_tema": {"type": "boolean"},
            "bonus": _lista_fechada(perfil.bonus),
            "penalidades": _lista_fechada(perfil.penalidade),
            "justificativa": {"type": "string"},
            "titulo": {"type": "string"},
        },
    }
    return {"type": "object", "additionalProperties": False, "required": ["candidatos"],
            "properties": {"candidatos": {"type": "array", "maxItems": MAX_CANDIDATOS, "items": item}}}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_prompt.py -q`
Expected: 4 passed

- [ ] **Step 5: Check + commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src
git add src/cortes/detector tests/test_prompt.py
git commit -m "feat: prompt e schema do detector

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Pontuação e filtros do detector

**Files:**
- Create: `src/cortes/detector/pontuacao.py`
- Modify: `src/cortes/detector/__init__.py`
- Test: `tests/test_pontuacao.py`, `tests/test_detector.py`

- [ ] **Step 1: Escrever o teste da pontuação**

```python
# tests/test_pontuacao.py
from cortes.detector.pontuacao import abertura_energetica, converter, nota_ponderada, percentil
from cortes.perfil import CRITERIOS, Perfil
from cortes.tipos import Frase

PERFIL = Perfil("f", "t", {"gancho_3s": .3, "autocontido": .25, "espanto": .2,
                           "historia_ou_virada": .1, "fechamento": .15},
                ["humor"], ["palestra_ou_palco"], 20, 90, [], [])
FRASES = [Frase(0, "Nenhuma força aérea luta contra eles.", 0, 10),
          Frase(1, "Mas isso é outra conversa.", 10, 25),
          Frase(2, "E acabou.", 25, 40),
          Frase(3, "Juro de 0,7% na Europa.", 100, 130)]


def bruto(ini: int, fim: int, notas: int = 4, no_tema: bool = True,
          bonus: list[str] | None = None, pen: list[str] | None = None) -> dict:  # type: ignore[type-arg]
    return {"frase_inicio": ini, "frase_fim": fim, "notas": dict.fromkeys(CRITERIOS, notas),
            "no_tema": no_tema, "bonus": bonus or [], "penalidades": pen or [],
            "justificativa": "j", "titulo": "t"}


def test_nota_ponderada_vai_de_0_a_100() -> None:
    assert nota_ponderada(dict.fromkeys(CRITERIOS, 1), PERFIL.rubrica) == 0.0
    assert nota_ponderada(dict.fromkeys(CRITERIOS, 5), PERFIL.rubrica) == 100.0
    assert nota_ponderada(dict.fromkeys(CRITERIOS, 3), PERFIL.rubrica) == 50.0


def test_percentil() -> None:
    assert percentil([1, 2, 3, 4], 0.75) == 4


def test_abertura_energetica_olha_os_3_primeiros_segundos() -> None:
    energia = [0.1] * 10 + [0.9] * 6 + [0.1] * 10   # janelas de 0,5 s; pico entre 5 s e 8 s
    assert abertura_energetica(5.0, energia, limiar=0.5) is True
    assert abertura_energetica(0.0, energia, limiar=0.5) is False


def test_converter_aceita_ordena_e_aplica_bonus_penalidade() -> None:
    energia = [0.1] * 400   # constante: toda abertura atinge o limiar e ganha +3; a ordem não muda
    aceitos, descartes = converter(
        {"candidatos": [bruto(0, 2), bruto(3, 3, bonus=["humor"]), bruto(0, 0, pen=["palestra_ou_palco"])]},
        FRASES, PERFIL, energia)
    assert [c.frase_inicio for c in aceitos] == [3, 0]           # 75+5+3 antes de 75+3
    assert aceitos[0].nota_final == 83.0 and aceitos[0].inicio == 100 and aceitos[0].fim == 130
    assert descartes == [{"frase_inicio": 0, "frase_fim": 0, "motivo": "duração 10s fora de 20-90s"}]


def test_converter_descarta_com_motivo_visivel() -> None:
    aceitos, descartes = converter({"candidatos": [
        bruto(1, 2),                 # começa com "Mas"
        bruto(0, 2, no_tema=False),  # fora do tema
        bruto(2, 9),                 # índice inexistente
        bruto(2, 1),                 # fim antes do início
    ]}, FRASES, PERFIL, [0.1] * 400)
    assert aceitos == []
    assert [d["motivo"] for d in descartes] == [
        "começa no meio: 'Mas isso é outra conversa.'", "fora do tema",
        "índices inválidos 2-9", "índices inválidos 2-1"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_pontuacao.py -q`
Expected: FAIL — `No module named 'cortes.detector.pontuacao'`

- [ ] **Step 3: Implementar `pontuacao.py`**

```python
# src/cortes/detector/pontuacao.py
"""Transforma a resposta do LLM em candidatos pontuados; descartes ficam registrados com motivo."""
from typing import Any

from cortes.perfil import Perfil
from cortes.regra_inicio import comeca_no_meio
from cortes.sinais import JANELA_S
from cortes.tipos import Candidato, Frase

PONTOS_BONUS = 5.0
PONTOS_PENALIDADE = 5.0
PONTOS_ENERGIA = 3.0
PERCENTIL_ENERGIA = 0.75
ABERTURA_S = 3.0


def nota_ponderada(notas: dict[str, int], rubrica: dict[str, float]) -> float:
    """Notas 1-5 → 0-100, pesadas pela rubrica."""
    return round(sum(peso * (notas[c] - 1) / 4 for c, peso in rubrica.items()) * 100, 1)


def percentil(valores: list[float], p: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(int(len(ordenados) * p), len(ordenados) - 1)]


def abertura_energetica(inicio: float, energia: list[float], limiar: float) -> bool:
    i0 = int(inicio / JANELA_S)
    trecho = energia[i0: i0 + int(ABERTURA_S / JANELA_S)]
    return bool(trecho) and sum(trecho) / len(trecho) >= limiar


def _motivo_descarte(b: dict[str, Any], frases: list[Frase], perfil: Perfil) -> str | None:
    ini, fim = b["frase_inicio"], b["frase_fim"]
    if not 0 <= ini <= fim < len(frases):
        return f"índices inválidos {ini}-{fim}"
    if not b["no_tema"]:
        return "fora do tema"
    if comeca_no_meio(frases[ini].texto):
        return f"começa no meio: '{frases[ini].texto}'"
    dur = frases[fim].fim - frases[ini].inicio
    if not perfil.duracao_min <= dur <= perfil.duracao_max:
        return f"duração {dur:.0f}s fora de {perfil.duracao_min:.0f}-{perfil.duracao_max:.0f}s"
    return None


def converter(bruto: dict[str, Any], frases: list[Frase], perfil: Perfil,
              energia: list[float]) -> tuple[list[Candidato], list[dict[str, Any]]]:
    limiar = percentil(energia, PERCENTIL_ENERGIA)
    aceitos: list[Candidato] = []
    descartes: list[dict[str, Any]] = []
    for b in bruto["candidatos"]:
        motivo = _motivo_descarte(b, frases, perfil)
        if motivo:
            descartes.append({"frase_inicio": b["frase_inicio"], "frase_fim": b["frase_fim"], "motivo": motivo})
            continue
        inicio, fim = frases[b["frase_inicio"]].inicio, frases[b["frase_fim"]].fim
        nota = (nota_ponderada(b["notas"], perfil.rubrica)
                + PONTOS_BONUS * len(b["bonus"]) - PONTOS_PENALIDADE * len(b["penalidades"])
                + (PONTOS_ENERGIA if abertura_energetica(inicio, energia, limiar) else 0.0))
        aceitos.append(Candidato(b["frase_inicio"], b["frase_fim"], inicio, fim, b["notas"], b["bonus"],
                                 b["penalidades"], b["justificativa"], b["titulo"], round(nota, 1)))
    aceitos.sort(key=lambda c: -c.nota_final)
    return aceitos, descartes
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_pontuacao.py -q`
Expected: 5 passed

- [ ] **Step 5: Escrever o teste do orquestrador**

```python
# tests/test_detector.py
from typing import Any

from cortes.detector import detectar
from cortes.perfil import CRITERIOS, Perfil
from cortes.tipos import Frase

PERFIL = Perfil("f", "dinheiro", dict.fromkeys(CRITERIOS, 0.2), [], [], 20, 90, [], [])
FRASES = [Frase(0, "Quanto ganha um jogador?", 0, 15), Frase(1, "Dez milhões por mês.", 15, 30)]


def test_detectar_passa_prompt_e_schema_ao_llm_e_converte() -> None:
    recebido: dict[str, Any] = {}

    def llm_falso(prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
        recebido.update(prompt=prompt, schema=schema, sistema=sistema, modelo=modelo)
        return {"candidatos": [{"frase_inicio": 0, "frase_fim": 1, "notas": dict.fromkeys(CRITERIOS, 5),
                                "no_tema": True, "bonus": [], "penalidades": [],
                                "justificativa": "j", "titulo": "t"}]}

    aceitos, descartes = detectar(FRASES, [0.1] * 100, PERFIL, modelo="opus", chamar_llm=llm_falso)
    assert "[F1 00:15] Dez milhões por mês." in recebido["prompt"]
    assert recebido["modelo"] == "opus" and "Ignore" in recebido["sistema"]
    assert len(aceitos) == 1 and aceitos[0].fim == 30 and descartes == []
```

- [ ] **Step 6: Implementar `detector/__init__.py`**

```python
# src/cortes/detector/__init__.py
"""Detector de momentos: prompt → LLM (assinatura) → candidatos pontuados (spec §6.4)."""
from collections.abc import Callable
from typing import Any

from cortes import llm
from cortes.detector.pontuacao import converter
from cortes.detector.prompt import SISTEMA, montar_prompt, schema_candidatos
from cortes.perfil import Perfil
from cortes.tipos import Candidato, Frase

ChamarLLM = Callable[[str, dict[str, Any], str, str], dict[str, Any]]


def _chamar_real(prompt: str, schema: dict[str, Any], sistema: str, modelo: str) -> dict[str, Any]:
    return llm.chamar(prompt, schema, sistema, modelo)


def detectar(frases: list[Frase], energia: list[float], perfil: Perfil, modelo: str = "sonnet",
             chamar_llm: ChamarLLM = _chamar_real) -> tuple[list[Candidato], list[dict[str, Any]]]:
    bruto = chamar_llm(montar_prompt(frases, perfil), schema_candidatos(perfil), SISTEMA, modelo)
    return converter(bruto, frases, perfil, energia)
```

- [ ] **Step 7: Rodar e ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_pontuacao.py tests/test_detector.py -q`
Expected: 6 passed

- [ ] **Step 8: Check + commit**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
git add src/cortes/detector tests/test_pontuacao.py tests/test_detector.py
git commit -m "feat: pontuação e filtros do detector com descartes registrados

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: CLI retomável e teste real

**Files:**
- Create: `src/cortes/cli.py`

- [ ] **Step 1: Implementar**

```python
# src/cortes/cli.py
"""`cortes detectar URL --nicho financas`: cada etapa grava seu arquivo e é pulada se já existe."""
import argparse
from dataclasses import asdict
from pathlib import Path

from cortes import ingestao, sinais, transcricao
from cortes.detector import detectar
from cortes.episodio import id_do_video, ler_json, pasta, salvar_json
from cortes.perfil import carregar_perfil
from cortes.segmentacao import frases
from cortes.tipos import Palavra


def _etapa(nome: str, pronto: bool) -> bool:
    print(f"[{'pula' if pronto else 'roda'}] {nome}", flush=True)
    return not pronto


def rodar_detectar(url: str, nicho: str, modelo: str) -> Path:
    d = pasta(id_do_video(url))
    perfil = carregar_perfil(Path("nichos") / nicho)
    if _etapa("download", (d / "video.mp4").exists()):
        ingestao.baixar(url, d)
    if _etapa("áudio", (d / "audio.wav").exists()):
        ingestao.extrair_audio(d)
    if _etapa("transcrição", (d / "palavras.json").exists()):
        salvar_json(d / "palavras.json", [asdict(p) for p in transcricao.transcrever(d / "audio.wav")])
    if _etapa("sinais", (d / "sinais.json").exists()):
        salvar_json(d / "sinais.json", {"janela_s": sinais.JANELA_S,
                                        "energia": sinais.energia_por_janela(sinais.ler_wav_mono(d / "audio.wav"))})
    palavras = [Palavra(**p) for p in ler_json(d / "palavras.json")]
    fs = frases(palavras)
    salvar_json(d / "frases.json", [asdict(f) for f in fs])
    _etapa("detector", False)
    aceitos, descartes = detectar(fs, ler_json(d / "sinais.json")["energia"], perfil, modelo)
    salvar_json(d / "candidatos.json", [asdict(c) for c in aceitos])
    salvar_json(d / "descartados.json", descartes)
    for c in aceitos:
        print(f"{c.nota_final:6.1f}  {c.inicio / 60:5.1f}min  {c.fim - c.inicio:4.0f}s  {c.titulo}")
    print(f"{len(aceitos)} candidatos, {len(descartes)} descartados → {d}")
    return d


def main() -> None:
    ap = argparse.ArgumentParser(prog="cortes")
    sub = ap.add_subparsers(dest="comando", required=True)
    det = sub.add_parser("detectar", help="baixa, transcreve e acha candidatos a corte")
    det.add_argument("url")
    det.add_argument("--nicho", default="financas")
    det.add_argument("--modelo", default="sonnet", help="modelo do claude -p (sonnet, opus, haiku)")
    args = ap.parse_args()
    if args.comando == "detectar":
        rodar_detectar(args.url, args.nicho, args.modelo)
```

- [ ] **Step 2: Check completo**

```bash
.venv/Scripts/python -m ruff check src tests && .venv/Scripts/python -m mypy src && .venv/Scripts/python -m pytest -q
```
Expected: sem erros; todos os testes passam.

- [ ] **Step 3: Teste real num episódio de finanças** (Davi escolhe a URL; sugestão: um episódio de 1 h do PrimoCast ou Os Economistas)

```bash
.venv/Scripts/cortes detectar "<URL do episódio>" --nicho financas
```
Expected: linhas `[roda] download`, `[roda] áudio`, `[roda] transcrição`, `[roda] sinais`, `[roda] detector`,
depois a tabela de candidatos ordenada por nota e o resumo `N candidatos, M descartados`.
Verificar à mão: abrir `episodios/<id>/candidatos.json`, conferir 3 candidatos tocando o vídeo no tempo
indicado; abrir `descartados.json` e ver se os motivos fazem sentido.

- [ ] **Step 4: Rodar de novo e confirmar retomada**

```bash
.venv/Scripts/cortes detectar "<mesma URL>" --nicho financas
```
Expected: `[pula]` em download, áudio, transcrição e sinais; só o detector roda.

- [ ] **Step 5: Commit**

```bash
git add src/cortes/cli.py
git commit -m "feat: CLI detectar com etapas retomáveis

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Critério de pronto do Plano 1

- `cortes detectar <URL>` roda de ponta a ponta num episódio real e grava `candidatos.json` e `descartados.json`.
- Check do projeto (`ruff`, `mypy --strict`, `pytest`) limpo.
- Davi olhou os 5 primeiros candidatos e disse se o ranking faz sentido — essa opinião é a entrada do Plano 2 (curadoria).
