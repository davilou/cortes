# Painel de Contas — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `cortes painel` sobe em `127.0.0.1` um painel que coleta os números de várias contas do YouTube (export do Studio), liga cada Short ao corte que o gerou e compara o que funciona por formato, conta, tema e podcast.

**Architecture:** Funções puras em `src/cortes/painel/` (CSV → retrato, views aos 7 dias, relativo à conta, grupos, matriz, sugestão de corte), I/O fino com executor injetável (`coleta.py` roda a skill `youtube-analytics` por subprocesso), FastAPI com rotas JSON finas, e uma página estática em HTML/CSS/JS puro, um arquivo JS por tela.

**Tech Stack:** Python 3.13 · FastAPI · uvicorn · httpx (só para o TestClient) · PyYAML · pytest · ruff · mypy --strict · HTML/CSS/JS sem framework · Node (já usado pela skill)

**Spec:** `docs/superpowers/specs/2026-10-01-painel-contas-design.md` · Mockup: `docs/superpowers/specs/2026-10-01-painel-contas-mockup.html`

## Fatos verificados que este plano usa

- A skill fica em `~/.claude/skills/youtube-analytics/scripts/`. O export é
  `node src/cli.mjs numeros --perfil <p> --dias 0 --metricas <a,b> --destino <pasta>` (rodado
  com `cwd` na pasta da skill) e termina imprimindo `[hh:mm:ss] pronto: <caminho do zip>` no stdout.
  O login é `node src/cli.mjs login --perfil <p>` (abre o Chrome; a pessoa entra na janela).
- Tokens de métrica aceitos: `views, duracao_media, pct_media, inscritos` (entre outros).
- O zip traz `Dados da tabela.csv` (UTF-8 com BOM). Cabeçalho real (export de 2026-08):
  `Conteúdo,Título do vídeo,Horário de publicação do vídeo,Duração,Visualizações,Impressões,Taxa de cliques de impressões (%),Duração média da visualização,Porcentagem visualizada média (%),Tempo de exibição (horas),Inscritos`.
  A primeira linha de dados é `Total`. A data vem em inglês: `"Aug 11, 2026"`. Decimal com ponto.
  Duração média `0:00:25`. `Duração` começa igual a `Duração média…`, então esse casamento tem de
  ser exato.
- `cortes.episodio.id_do_video(url)` já extrai o id de `/shorts/`, `youtu.be/`, `watch?v=`, `live/`
  e levanta `ValueError("URL sem id…")`; está testado em `tests/test_episodio.py`.
- `cortes.episodio.salvar_json` grava atômico (`.tmp` + replace); `ler_json` lê.
- `cortes.perfil.carregar_perfil(pasta_nicho)` devolve `Perfil` com `bonus` e `penalidade`
  (`dict[tag, descrição]`) e exige `exemplos/bons.jsonl` e `exemplos/ruins.jsonl`.
- `testes/<pasta>/meta.json` é metadado do HyperFrames (sem título, podcast nem tema).
  `episodios/<id>/meta.json` tem `canal` (ex.: `"PrimoCast"`).
- FastAPI serializa dataclasses, `date` e `datetime` via `jsonable_encoder`.

## Estrutura de arquivos

```
contas/
  contas.yaml               # no git — contas (começa vazia)
  formatos.yaml             # no git — vocabulário de formatos (f1…f8 de testes/TEMPLATES.md)
  publicados.jsonl          # fora do git
  retratos/<conta>/<dia>.json  # fora do git
src/cortes/painel/
  __init__.py
  dados.py        # ErroPainel, Conta, Formato, Vocabulario; carregar contas/formatos/temas
  publicados.py   # Etiquetas, Publicado; ler/validar/ligar/gravar publicados.jsonl
  retratos.py     # VideoRetrato, Retrato; salvar/ler retratos
  studio.py       # puro: CSV do Studio → list[VideoRetrato]; texto_do_zip
  metodo.py       # puro: Medida, views_7d, Linha, montar_linhas (relativo à conta)
  comparacao.py   # puro: Grupo, Celula, Confusao; grupos, matriz, confusoes, dimensao
  ligacao.py      # puro: CorteConhecido; listar_cortes, sugerir
  coleta.py       # subprocesso da skill (executor injetável); coletar_todas; abrir_login
  servidor.py     # Config, criar_app (FastAPI)
src/cortes/cli.py # + subcomando `painel`
web/static/
  index.html  painel.css
  js/base.js  js/comparar.js  js/shorts.js  js/contas.js  js/inicio.js
tests/
  test_painel_dados.py  test_painel_publicados.py  test_painel_retratos.py
  test_painel_studio.py test_painel_metodo.py      test_painel_comparacao.py
  test_painel_ligacao.py test_painel_coleta.py     test_painel_servidor.py
```

Comando de check (do `CLAUDE.md` do repo), rodar ao fim de cada tarefa:

```
.venv/Scripts/python -m ruff check src tests
.venv/Scripts/python -m mypy src
.venv/Scripts/python -m pytest -q
```

---

### Task 1: Dependências e esqueleto

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Create: `contas/contas.yaml`, `contas/formatos.yaml`, `src/cortes/painel/__init__.py`

- [ ] **Step 1: Acrescentar dependências no `pyproject.toml`**

Em `dependencies`, depois de `"yt-dlp",`:

```toml
  "fastapi",          # servidor local do painel (spec painel §7; mesmo servidor da curadoria)
  "uvicorn",          # roda o FastAPI
```

Em `[project.optional-dependencies]`, trocar a linha `dev` por:

```toml
dev = ["pytest", "ruff", "mypy", "types-PyYAML", "types-jsonschema", "httpx"]  # httpx: TestClient do FastAPI
```

- [ ] **Step 2: Instalar**

Run: `.venv/Scripts/python -m pip install -e ".[dev]"`
Expected: termina com `Successfully installed ... fastapi ... uvicorn ... httpx ...`

- [ ] **Step 3: `.gitignore`** — acrescentar ao final:

```
contas/publicados.jsonl
contas/retratos/
```

- [ ] **Step 4: Criar `contas/contas.yaml`**

```yaml
# Uma entrada por canal. perfil_studio = nome do perfil de login da skill youtube-analytics.
# Exemplo:
#   - {id: grana, nome: Grana Cortes, handle: "@grana.cortes", nicho: financas, perfil_studio: grana}
contas: []
```

- [ ] **Step 5: Criar `contas/formatos.yaml`** (de `testes/TEMPLATES.md`)

```yaml
formatos:
  f1: {nome: Falante puro, obs: controle}
  f2: {nome: Motion fixo, obs: sem dado direto}
  f3: {nome: Motion dinâmico, obs: troca de imagem por fala}
  f4: {nome: B-roll real, obs: risco alto de Content ID}
  f5: {nome: Gameplay embaixo, obs: R2 sem efeito em finanças}
  f6: {nome: Estilo Hormozi, obs: contraprova R1+R2}
  f7: {nome: Conversa com reações, obs: sinal mais forte da R2}
  f8: {nome: 16:9 desfocado, obs: anti-controle}
```

- [ ] **Step 6: Criar `src/cortes/painel/__init__.py`**

```python
"""Painel de contas: números dos Shorts publicados por conta, formato, tema e podcast."""
```

- [ ] **Step 7: Check e commit**

Run: o comando de check. Expected: tudo passa (nada novo testado ainda).

```bash
git add pyproject.toml .gitignore contas/contas.yaml contas/formatos.yaml src/cortes/painel/__init__.py
git commit -m "chore: dependências e esqueleto do painel de contas"
```

---

### Task 2: Configuração — contas, formatos e temas

**Files:**
- Create: `src/cortes/painel/dados.py`
- Test: `tests/test_painel_dados.py`

- [ ] **Step 1: Escrever os testes**

```python
from pathlib import Path

import pytest

from cortes.painel.dados import (
    ErroPainel,
    carregar_contas,
    carregar_formatos,
    carregar_temas,
    carregar_vocabulario,
)

PERFIL = """nicho: financas
filtro_tema: "É sobre dinheiro."
rubrica: {gancho_3s: 0.3, autocontido: 0.25, espanto: 0.2, historia_ou_virada: 0.1, fechamento: 0.15}
bonus: {humor: "faz rir", numero_na_primeira_frase: "traz número"}
penalidade: {palestra: "gravado em palco"}
duracao_s: {min: 20, max: 90}
"""
CONTA = '  - {id: grana, nome: Grana, handle: "@grana", nicho: financas, perfil_studio: grana}\n'


def criar_nicho(nichos: Path, nome: str, texto: str = PERFIL) -> None:
    pasta = nichos / nome
    (pasta / "exemplos").mkdir(parents=True)
    (pasta / "perfil.yaml").write_text(texto, encoding="utf-8")
    for arq in ("bons.jsonl", "ruins.jsonl"):
        (pasta / "exemplos" / arq).write_text("", encoding="utf-8")


def escrever(tmp: Path, nome: str, texto: str) -> Path:
    arq = tmp / nome
    arq.write_text(texto, encoding="utf-8")
    return arq


def test_carrega_contas(tmp_path: Path) -> None:
    criar_nicho(tmp_path / "nichos", "financas")
    contas = carregar_contas(escrever(tmp_path, "c.yaml", "contas:\n" + CONTA), tmp_path / "nichos")
    assert contas["grana"].handle == "@grana" and contas["grana"].perfil_studio == "grana"


def test_lista_vazia_e_valida(tmp_path: Path) -> None:
    assert carregar_contas(escrever(tmp_path, "c.yaml", "contas: []\n"), tmp_path) == {}


def test_nicho_inexistente(tmp_path: Path) -> None:
    (tmp_path / "nichos").mkdir()
    with pytest.raises(ErroPainel, match="nicho 'financas'"):
        carregar_contas(escrever(tmp_path, "c.yaml", "contas:\n" + CONTA), tmp_path / "nichos")


def test_campo_faltando(tmp_path: Path) -> None:
    texto = "contas:\n  - {id: grana, nome: G, handle: '@g', nicho: financas}\n"
    with pytest.raises(ErroPainel, match="perfil_studio"):
        carregar_contas(escrever(tmp_path, "c.yaml", texto), tmp_path)


def test_id_repetido(tmp_path: Path) -> None:
    criar_nicho(tmp_path / "nichos", "financas")
    with pytest.raises(ErroPainel, match="repetido"):
        carregar_contas(escrever(tmp_path, "c.yaml", "contas:\n" + CONTA + CONTA), tmp_path / "nichos")


def test_id_fora_do_padrao(tmp_path: Path) -> None:
    criar_nicho(tmp_path / "nichos", "financas")
    texto = "contas:\n" + CONTA.replace("id: grana", "id: Grana!")
    with pytest.raises(ErroPainel, match="padrão"):
        carregar_contas(escrever(tmp_path, "c.yaml", texto), tmp_path / "nichos")


def test_formatos(tmp_path: Path) -> None:
    f = carregar_formatos(escrever(tmp_path, "f.yaml", "formatos:\n  f1: {nome: Falante}\n"))
    assert f["f1"].nome == "Falante" and f["f1"].obs == ""


def test_formato_repetido(tmp_path: Path) -> None:
    texto = "formatos:\n  f1: {nome: Falante}\n  f1: {nome: Outro}\n"
    with pytest.raises(ErroPainel, match="repetida"):
        carregar_formatos(escrever(tmp_path, "f.yaml", texto))


def test_formato_sem_nome(tmp_path: Path) -> None:
    with pytest.raises(ErroPainel, match="'f1' sem 'nome'"):
        carregar_formatos(escrever(tmp_path, "f.yaml", "formatos:\n  f1: {obs: x}\n"))


def test_temas_unem_bonus_e_penalidade_dos_nichos(tmp_path: Path) -> None:
    criar_nicho(tmp_path, "financas")
    criar_nicho(tmp_path, "humor", PERFIL.replace('humor: "faz rir"', 'trocadilho: "jogo de palavras"'))
    assert carregar_temas(tmp_path) == {"humor", "numero_na_primeira_frase", "palestra", "trocadilho"}


def test_vocabulario_da_raiz(tmp_path: Path) -> None:
    criar_nicho(tmp_path / "nichos", "financas")
    (tmp_path / "contas").mkdir()
    escrever(tmp_path / "contas", "contas.yaml", "contas:\n" + CONTA)
    escrever(tmp_path / "contas", "formatos.yaml", "formatos:\n  f7: {nome: Conversa}\n")
    voc = carregar_vocabulario(tmp_path)
    assert set(voc.contas) == {"grana"} and set(voc.formatos) == {"f7"} and "humor" in voc.temas
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_painel_dados.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cortes.painel.dados'`

- [ ] **Step 3: Implementar `src/cortes/painel/dados.py`**

```python
"""Configuração do painel: contas, formatos e o vocabulário de temas (spec painel §3)."""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from cortes.perfil import carregar_perfil

_ID_CONTA = re.compile(r"^[a-z0-9-]+$")
CAMPOS_CONTA = ("id", "nome", "handle", "nicho", "perfil_studio")


class ErroPainel(ValueError):
    """Configuração ou dado inválido. A mensagem diz o arquivo e o campo."""


@dataclass(frozen=True)
class Conta:
    id: str
    nome: str
    handle: str
    nicho: str
    perfil_studio: str


@dataclass(frozen=True)
class Formato:
    id: str
    nome: str
    obs: str


@dataclass(frozen=True)
class Vocabulario:
    contas: dict[str, Conta]
    formatos: dict[str, Formato]
    temas: frozenset[str]


class _SemRepetidas(yaml.SafeLoader):
    """O SafeLoader aceita chave repetida e fica com a última, em silêncio. Este recusa."""


def _mapa(loader: yaml.SafeLoader, node: yaml.Node, deep: bool = False) -> dict[Any, Any]:
    assert isinstance(node, yaml.MappingNode)
    chaves = [loader.construct_object(k, deep=True) for k, _ in node.value]
    if repetidas := sorted({str(k) for k in chaves if chaves.count(k) > 1}):
        raise ErroPainel(f"chave repetida: {repetidas}")
    return loader.construct_mapping(node, deep=deep)


_SemRepetidas.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapa)


def _ler_yaml(arquivo: Path, chave: str) -> Any:
    try:
        dados = yaml.load(arquivo.read_text(encoding="utf-8"), Loader=_SemRepetidas)
    except ErroPainel as e:
        raise ErroPainel(f"{arquivo}: {e}") from e
    if not isinstance(dados, dict) or chave not in dados:
        raise ErroPainel(f"{arquivo}: falta a chave '{chave}'")
    return dados[chave]


def _conta(arquivo: Path, i: int, c: Any, pasta_nichos: Path) -> Conta:
    if not isinstance(c, dict):
        raise ErroPainel(f"{arquivo}: conta #{i} não é um mapa")
    for campo in CAMPOS_CONTA:
        if not isinstance(c.get(campo), str) or not c[campo].strip():
            raise ErroPainel(f"{arquivo}: conta #{i} sem o campo '{campo}'")
    if not _ID_CONTA.match(c["id"]):
        raise ErroPainel(f"{arquivo}: id '{c['id']}' fora do padrão [a-z0-9-]+")
    if not (pasta_nichos / c["nicho"] / "perfil.yaml").exists():
        raise ErroPainel(f"{arquivo}: conta '{c['id']}' usa o nicho '{c['nicho']}', que não existe "
                         f"em {pasta_nichos}")
    return Conta(*(c[campo] for campo in CAMPOS_CONTA))


def carregar_contas(arquivo: Path, pasta_nichos: Path) -> dict[str, Conta]:
    lista = _ler_yaml(arquivo, "contas")
    if not isinstance(lista, list):
        raise ErroPainel(f"{arquivo}: 'contas' deve ser uma lista")
    contas: dict[str, Conta] = {}
    for i, bruto in enumerate(lista, 1):
        conta = _conta(arquivo, i, bruto, pasta_nichos)
        if conta.id in contas:
            raise ErroPainel(f"{arquivo}: id '{conta.id}' repetido")
        contas[conta.id] = conta
    return contas


def carregar_formatos(arquivo: Path) -> dict[str, Formato]:
    mapa = _ler_yaml(arquivo, "formatos")
    if not isinstance(mapa, dict):
        raise ErroPainel(f"{arquivo}: 'formatos' deve ser um mapa {{id: {{nome, obs}}}}")
    formatos: dict[str, Formato] = {}
    for fid, f in mapa.items():
        if not isinstance(f, dict) or not isinstance(f.get("nome"), str):
            raise ErroPainel(f"{arquivo}: formato '{fid}' sem 'nome'")
        formatos[str(fid)] = Formato(str(fid), f["nome"], str(f.get("obs", "")))
    return formatos


def carregar_temas(pasta_nichos: Path) -> frozenset[str]:
    """Temas = tags de bônus e penalidade de todos os perfis: o mesmo vocabulário do detector."""
    temas: set[str] = set()
    for arq in sorted(pasta_nichos.glob("*/perfil.yaml")):
        perfil = carregar_perfil(arq.parent)
        temas |= set(perfil.bonus) | set(perfil.penalidade)
    return frozenset(temas)


def carregar_vocabulario(raiz: Path) -> Vocabulario:
    return Vocabulario(
        contas=carregar_contas(raiz / "contas" / "contas.yaml", raiz / "nichos"),
        formatos=carregar_formatos(raiz / "contas" / "formatos.yaml"),
        temas=carregar_temas(raiz / "nichos"),
    )
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_painel_dados.py -q`
Expected: `11 passed`

- [ ] **Step 5: Check e commit**

Run: o comando de check. Se o mypy reclamar da assinatura de `_mapa` em `add_constructor`, troque
o tipo do parâmetro `loader` para `yaml.Loader | yaml.SafeLoader` e rode de novo — não use `# type: ignore`.

```bash
git add src/cortes/painel/dados.py tests/test_painel_dados.py
git commit -m "feat: configuração do painel com contas, formatos e temas validados"
```

---

### Task 3: Publicados — a ligação Short → corte

**Files:**
- Create: `src/cortes/painel/publicados.py`
- Test: `tests/test_painel_publicados.py`

- [ ] **Step 1: Escrever os testes**

```python
from datetime import date
from pathlib import Path

import pytest

from cortes.painel.dados import Conta, ErroPainel, Formato, Vocabulario
from cortes.painel.publicados import Etiquetas, Publicado, gravar_publicados, ler_publicados, ligar

VOC = Vocabulario(
    contas={"grana": Conta("grana", "Grana", "@grana", "financas", "grana")},
    formatos={"f7": Formato("f7", "Conversa", "")},
    temas=frozenset({"humor", "dinheiro_alheio_quanto_ganha"}),
)


def pub(video_id: str = "abcdefghijk", formato: str = "f7", temas: tuple[str, ...] = ("humor",)) -> Publicado:
    return Publicado(video_id, "grana", date(2026, 10, 3), "testes/f7-conversa-comediante",
                     Etiquetas(formato, temas, "PrimoCast"))


def test_ida_e_volta(tmp_path: Path) -> None:
    arq = tmp_path / "publicados.jsonl"
    gravar_publicados(arq, [pub()])
    assert ler_publicados(arq, VOC) == [pub()]


def test_arquivo_ausente_e_lista_vazia(tmp_path: Path) -> None:
    assert ler_publicados(tmp_path / "nao_existe.jsonl", VOC) == []


def test_formato_fora_do_vocabulario() -> None:
    with pytest.raises(ErroPainel, match="formato 'f9'"):
        ligar([], pub(formato="f9"), VOC)


def test_tema_fora_do_vocabulario() -> None:
    with pytest.raises(ErroPainel, match="temas fora"):
        ligar([], pub(temas=("inventado",)), VOC)


def test_ligar_substitui_mesmo_video() -> None:
    novo = pub(temas=("dinheiro_alheio_quanto_ganha",))
    assert ligar([pub(), pub("zzzzzzzzzzz")], novo, VOC) == [pub("zzzzzzzzzzz"), novo]


def test_video_repetido_no_arquivo(tmp_path: Path) -> None:
    arq = tmp_path / "publicados.jsonl"
    gravar_publicados(arq, [pub()])
    arq.write_text(arq.read_text(encoding="utf-8") * 2, encoding="utf-8")
    with pytest.raises(ErroPainel, match="repetido"):
        ler_publicados(arq, VOC)


def test_linha_quebrada_diz_o_numero(tmp_path: Path) -> None:
    arq = tmp_path / "publicados.jsonl"
    arq.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ErroPainel, match=":1:"):
        ler_publicados(arq, VOC)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_painel_publicados.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cortes.painel.publicados'`

- [ ] **Step 3: Implementar `src/cortes/painel/publicados.py`**

```python
"""publicados.jsonl: liga cada Short no YouTube ao corte que o gerou (spec painel §3.3)."""
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from cortes.painel.dados import ErroPainel, Vocabulario


@dataclass(frozen=True)
class Etiquetas:
    formato: str
    temas: tuple[str, ...]
    podcast: str


@dataclass(frozen=True)
class Publicado:
    video_id: str
    conta: str
    publicado_em: date
    corte: str
    etiquetas: Etiquetas


def validar(p: Publicado, voc: Vocabulario) -> None:
    if p.conta not in voc.contas:
        raise ErroPainel(f"conta '{p.conta}' não existe em contas.yaml")
    if p.etiquetas.formato not in voc.formatos:
        raise ErroPainel(f"formato '{p.etiquetas.formato}' não existe em formatos.yaml")
    if fora := sorted(set(p.etiquetas.temas) - voc.temas):
        raise ErroPainel(f"temas fora do vocabulário dos perfis de nicho: {fora}")
    if not p.etiquetas.podcast.strip():
        raise ErroPainel("podcast vazio")
    if not p.corte.strip():
        raise ErroPainel("corte vazio")


def _para_dict(p: Publicado) -> dict[str, Any]:
    e = p.etiquetas
    return {"video_id": p.video_id, "conta": p.conta, "publicado_em": p.publicado_em.isoformat(),
            "corte": p.corte, "etiquetas": {"formato": e.formato, "temas": list(e.temas), "podcast": e.podcast}}


def _de_dict(d: Any) -> Publicado:
    try:
        e = d["etiquetas"]
        return Publicado(str(d["video_id"]), str(d["conta"]), date.fromisoformat(d["publicado_em"]),
                         str(d["corte"]),
                         Etiquetas(str(e["formato"]), tuple(str(t) for t in e["temas"]), str(e["podcast"])))
    except (KeyError, TypeError, ValueError) as ex:
        raise ErroPainel(f"linha inválida ({ex!r})") from ex


def ler_publicados(arquivo: Path, voc: Vocabulario) -> list[Publicado]:
    if not arquivo.exists():
        return []  # nenhum Short ligado ainda: o arquivo nasce na primeira ligação
    lista: list[Publicado] = []
    vistos: set[str] = set()
    for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
        if not linha.strip():
            continue
        try:
            p = _de_dict(json.loads(linha))
            validar(p, voc)
        except (json.JSONDecodeError, ErroPainel) as e:
            raise ErroPainel(f"{arquivo}:{n}: {e}") from e
        if p.video_id in vistos:
            raise ErroPainel(f"{arquivo}:{n}: video_id '{p.video_id}' repetido")
        vistos.add(p.video_id)
        lista.append(p)
    return lista


def ligar(lista: list[Publicado], novo: Publicado, voc: Vocabulario) -> list[Publicado]:
    """Religar o mesmo vídeo substitui a ligação anterior."""
    validar(novo, voc)
    return [p for p in lista if p.video_id != novo.video_id] + [novo]


def gravar_publicados(arquivo: Path, lista: list[Publicado]) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    tmp = arquivo.with_suffix(arquivo.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(_para_dict(p), ensure_ascii=False) + "\n" for p in lista),
                   encoding="utf-8")
    tmp.replace(arquivo)
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_painel_publicados.py -q`
Expected: `7 passed`

- [ ] **Step 5: Check e commit**

```bash
git add src/cortes/painel/publicados.py tests/test_painel_publicados.py
git commit -m "feat: ligação de Short a corte com vocabulário fechado de etiquetas"
```

---

### Task 4: Retratos — gravar e ler

**Files:**
- Create: `src/cortes/painel/retratos.py`
- Test: `tests/test_painel_retratos.py`

- [ ] **Step 1: Escrever os testes**

```python
from datetime import date, datetime
from pathlib import Path

import pytest

from cortes.painel.dados import ErroPainel
from cortes.painel.retratos import Retrato, VideoRetrato, ler_retratos, salvar_retrato


def video(views: int) -> VideoRetrato:
    return VideoRetrato("abcdefghijk", "Título", date(2026, 10, 3), 26.0, views, 87.4, 22.7, 3)


def test_ida_e_volta(tmp_path: Path) -> None:
    r = Retrato("grana", datetime(2026, 10, 10, 9, 12), (video(1830),))
    destino = salvar_retrato(tmp_path, r)
    assert destino == tmp_path / "grana" / "2026-10-10.json"
    assert ler_retratos(tmp_path) == {"grana": [r]}


def test_ordena_por_data_e_mesmo_dia_sobrescreve(tmp_path: Path) -> None:
    salvar_retrato(tmp_path, Retrato("grana", datetime(2026, 10, 12, 8), (video(300),)))
    salvar_retrato(tmp_path, Retrato("grana", datetime(2026, 10, 10, 8), (video(100),)))
    salvar_retrato(tmp_path, Retrato("grana", datetime(2026, 10, 10, 20), (video(150),)))
    rs = ler_retratos(tmp_path)["grana"]
    assert [r.videos[0].views for r in rs] == [150, 300]


def test_pasta_ausente_e_vazio(tmp_path: Path) -> None:
    assert ler_retratos(tmp_path / "nada") == {}


def test_retrato_quebrado(tmp_path: Path) -> None:
    (tmp_path / "grana").mkdir()
    (tmp_path / "grana" / "2026-10-10.json").write_text('{"conta": "grana"}', encoding="utf-8")
    with pytest.raises(ErroPainel, match="retrato inválido"):
        ler_retratos(tmp_path)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_painel_retratos.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implementar `src/cortes/painel/retratos.py`**

```python
"""Retrato = export do Studio de uma conta num dia, com o total acumulado de cada vídeo (spec painel §3.4)."""
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from cortes.episodio import ler_json, salvar_json
from cortes.painel.dados import ErroPainel


@dataclass(frozen=True)
class VideoRetrato:
    video_id: str
    titulo: str
    publicado_em: date
    duracao_s: float
    views: int
    pct_media: float
    duracao_media_s: float
    inscritos: int


@dataclass(frozen=True)
class Retrato:
    conta: str
    coletado_em: datetime
    videos: tuple[VideoRetrato, ...]

    @property
    def dia(self) -> date:
        return self.coletado_em.date()


def salvar_retrato(pasta: Path, r: Retrato) -> Path:
    """Um retrato por conta por dia: atualizar de novo no mesmo dia sobrescreve."""
    destino = pasta / r.conta / f"{r.dia.isoformat()}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    salvar_json(destino, {
        "conta": r.conta,
        "coletado_em": r.coletado_em.isoformat(timespec="seconds"),
        "videos": [{**asdict(v), "publicado_em": v.publicado_em.isoformat()} for v in r.videos],
    })
    return destino


def _ler(arquivo: Path) -> Retrato:
    d = ler_json(arquivo)
    try:
        videos = tuple(VideoRetrato(**{**v, "publicado_em": date.fromisoformat(v["publicado_em"])})
                       for v in d["videos"])
        return Retrato(str(d["conta"]), datetime.fromisoformat(d["coletado_em"]), videos)
    except (KeyError, TypeError, ValueError) as e:
        raise ErroPainel(f"{arquivo}: retrato inválido ({e!r})") from e


def ler_retratos(pasta: Path) -> dict[str, list[Retrato]]:
    """Retratos por conta, do mais antigo ao mais novo."""
    por_conta: dict[str, list[Retrato]] = {}
    for arquivo in sorted(pasta.glob("*/*.json")):
        r = _ler(arquivo)
        por_conta.setdefault(r.conta, []).append(r)
    for lista in por_conta.values():
        lista.sort(key=lambda r: r.coletado_em)
    return por_conta
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_painel_retratos.py -q`
Expected: `4 passed`

- [ ] **Step 5: Check e commit**

```bash
git add src/cortes/painel/retratos.py tests/test_painel_retratos.py
git commit -m "feat: retratos diários por conta"
```

---

### Task 5: Leitura do CSV do Studio

**Files:**
- Create: `src/cortes/painel/studio.py`
- Test: `tests/test_painel_studio.py`

- [ ] **Step 1: Escrever os testes** (cabeçalho e linhas no formato real conferido)

```python
import zipfile
from datetime import date
from pathlib import Path

import pytest

from cortes.painel.dados import ErroPainel
from cortes.painel.studio import ler_tabela, texto_do_zip

CABECALHO = ("Conteúdo,Título do vídeo,Horário de publicação do vídeo,Duração,Visualizações,Impressões,"
             "Taxa de cliques de impressões (%),Duração média da visualização,"
             "Porcentagem visualizada média (%),Tempo de exibição (horas),Inscritos\n")
CSV_REAL = (CABECALHO
            + "Total,,,,2640,5119,2.97,0:00:46,40.39,15.5082,9\n"
            + 'J-QjHWdb7gQ,Pagava R$ 30 por mês #noticias,"Aug 11, 2026",40,1174,22,0,0:00:25,64.59,4.3204,2\n'
            + 'xV9KDhdKFfw,"O que o banco não pode, te cobrar","Aug 12, 2026",44,309,19,5.26,0:01:02,60.68,0.9,-1\n')


def test_le_videos_e_pula_total() -> None:
    vs = ler_tabela(CSV_REAL)
    assert [v.video_id for v in vs] == ["J-QjHWdb7gQ", "xV9KDhdKFfw"]
    a, b = vs
    assert a.publicado_em == date(2026, 8, 11) and a.duracao_s == 40 and a.views == 1174
    assert a.pct_media == 64.59 and a.duracao_media_s == 25 and a.inscritos == 2
    assert b.titulo == "O que o banco não pode, te cobrar" and b.duracao_media_s == 62 and b.inscritos == -1


def test_coluna_faltando_diz_qual() -> None:
    sem_inscritos = "\n".join(linha.rsplit(",", 1)[0] for linha in CSV_REAL.splitlines())
    with pytest.raises(ErroPainel, match="Inscritos"):
        ler_tabela(sem_inscritos)


def test_data_em_formato_desconhecido() -> None:
    with pytest.raises(ErroPainel, match="11/08/2026"):
        ler_tabela(CSV_REAL.replace('"Aug 11, 2026"', "11/08/2026"))


def test_celula_vazia_com_zero_views_vira_zero() -> None:
    texto = CABECALHO + 'novovideo00,Novo,"Oct 1, 2026",30,0,0,,,,0,\n'
    v = ler_tabela(texto)[0]
    assert v.views == 0 and v.pct_media == 0 and v.inscritos == 0


def test_celula_vazia_com_views_e_erro() -> None:
    texto = CABECALHO + 'novovideo00,Novo,"Oct 1, 2026",30,50,0,,0:00:10,,0,1\n'
    with pytest.raises(ErroPainel, match="pct_media"):
        ler_tabela(texto)


def test_texto_do_zip(tmp_path: Path) -> None:
    arq = tmp_path / "export.zip"
    with zipfile.ZipFile(arq, "w") as z:
        z.writestr("Dados da tabela.csv", CSV_REAL.encode("utf-8-sig"))
        z.writestr("Total.csv", "x")
    assert texto_do_zip(arq) == CSV_REAL


def test_zip_sem_tabela(tmp_path: Path) -> None:
    arq = tmp_path / "export.zip"
    with zipfile.ZipFile(arq, "w") as z:
        z.writestr("Total.csv", "x")
    with pytest.raises(ErroPainel, match="sem a tabela"):
        texto_do_zip(arq)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_painel_studio.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implementar `src/cortes/painel/studio.py`**

```python
"""CSV do export do Studio (modo avançado, dimensão VIDEO) → vídeos do retrato.

O cabeçalho vem no idioma da conta; a data de publicação vem em inglês ("Aug 11, 2026") mesmo
com cabeçalho em português (conferido em export real de 2026-08).
"""
import csv
import io
import zipfile
from datetime import date
from pathlib import Path

from cortes.painel.dados import ErroPainel
from cortes.painel.retratos import VideoRetrato

# (campo, nomes aceitos, casamento exato?). "Duração" é exato: "Duração média…" começa igual.
COLUNAS: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    ("video_id", ("Conteúdo", "Content"), True),
    ("titulo", ("Título do vídeo", "Video title"), True),
    ("publicado_em", ("Horário de publicação", "Video publish time"), False),
    ("duracao_s", ("Duração", "Duration"), True),
    ("views", ("Visualizações", "Views"), True),
    ("duracao_media_s", ("Duração média da visualização", "Average view duration"), False),
    ("pct_media", ("Porcentagem visualizada média", "Average percentage viewed"), False),
    ("inscritos", ("Inscritos", "Subscribers"), True),
)
_MESES = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def _indices(cabecalho: list[str]) -> dict[str, int]:
    idx: dict[str, int] = {}
    for campo, nomes, exato in COLUNAS:
        achados = [i for i, c in enumerate(cabecalho) if (c in nomes if exato else c.startswith(nomes))]
        if not achados:
            raise ErroPainel(f"export do Studio sem a coluna '{nomes[0]}' (colunas: {cabecalho})")
        idx[campo] = achados[0]
    return idx


def _data(texto: str) -> date:
    try:
        mes, dia, ano = texto.replace(",", "").split()
        return date(int(ano), _MESES[mes[:3]], int(dia))
    except (ValueError, KeyError) as e:
        raise ErroPainel(f"data de publicação em formato desconhecido: '{texto}'") from e


def _segundos(texto: str) -> float:
    total = 0.0
    for parte in texto.split(":"):
        total = total * 60 + float(parte)
    return total


def _video(cel: dict[str, str]) -> VideoRetrato:
    if not cel["views"]:
        raise ErroPainel(f"vídeo {cel['video_id']}: views vazio")
    views = int(float(cel["views"]))

    def valor(campo: str) -> str:
        if cel[campo]:
            return cel[campo]
        if views == 0:
            return "0"  # vídeo sem view nenhuma: o Studio deixa as médias em branco
        raise ErroPainel(f"vídeo {cel['video_id']}: '{campo}' vazio com {views} views")

    return VideoRetrato(
        video_id=cel["video_id"], titulo=cel["titulo"], publicado_em=_data(cel["publicado_em"]),
        duracao_s=float(valor("duracao_s")), views=views, pct_media=float(valor("pct_media")),
        duracao_media_s=_segundos(valor("duracao_media_s")), inscritos=int(float(valor("inscritos"))),
    )


def ler_tabela(texto: str) -> list[VideoRetrato]:
    linhas = list(csv.reader(io.StringIO(texto)))
    if not linhas:
        raise ErroPainel("export do Studio vazio")
    idx = _indices(linhas[0])
    videos: list[VideoRetrato] = []
    for linha in linhas[1:]:
        if not linha or linha[0].strip() in ("", "Total", "Totals"):
            continue
        videos.append(_video({campo: linha[i].strip() for campo, i in idx.items()}))
    return videos


def texto_do_zip(caminho: Path) -> str:
    with zipfile.ZipFile(caminho) as z:
        nome = next((n for n in z.namelist() if n.startswith(("Dados da tabela", "Table data"))), None)
        if nome is None:
            raise ErroPainel(f"{caminho}: zip sem a tabela por vídeo ({z.namelist()})")
        return z.read(nome).decode("utf-8-sig")
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_painel_studio.py -q`
Expected: `7 passed`

- [ ] **Step 5: Check e commit**

```bash
git add src/cortes/painel/studio.py tests/test_painel_studio.py
git commit -m "feat: leitura do CSV do export do Studio"
```

---

### Task 6: Views aos 7 dias

**Files:**
- Create: `src/cortes/painel/metodo.py`
- Test: `tests/test_painel_metodo.py`

- [ ] **Step 1: Escrever os testes**

```python
from datetime import date

import pytest

from cortes.painel.metodo import Medida, views_7d

PUB = date(2026, 10, 1)   # dia 7 = 2026-10-08


def d(dia: int) -> date:
    return date(2026, 10, dia)


def test_interpola_entre_retratos() -> None:
    assert views_7d(PUB, [(d(5), 100), (d(9), 300)]) == Medida("medido", 250.0)


def test_retrato_no_proprio_dia_7() -> None:
    assert views_7d(PUB, [(d(5), 100), (d(8), 420), (d(20), 900)]) == Medida("medido", 420.0)


def test_parte_de_zero_na_publicacao() -> None:
    assert views_7d(PUB, [(d(11), 1000)]) == Medida("medido", pytest.approx(700.0))


def test_lacuna_maior_que_3_dias_e_estimado() -> None:
    assert views_7d(PUB, [(d(12), 1100)]) == Medida("estimado", pytest.approx(700.0))


def test_sem_retrato_depois_do_dia_7_esta_maturando() -> None:
    assert views_7d(PUB, [(d(5), 100)]) == Medida("maturando", None)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_painel_metodo.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implementar `src/cortes/painel/metodo.py`** (primeira parte)

```python
"""Método do painel (spec painel §5): views aos 7 dias e relativo à mediana da conta. Puro."""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

Estado = Literal["medido", "estimado", "maturando"]
DIA_ALVO = 7
FOLGA_DIAS = 3   # retrato depois do dia 7 a mais que isto → valor "estimado"


@dataclass(frozen=True)
class Medida:
    estado: Estado
    views_7d: float | None


def views_7d(publicado_em: date, pontos: list[tuple[date, int]]) -> Medida:
    """Interpola as views no dia 7 a partir dos retratos (total acumulado em cada dia)."""
    alvo = publicado_em + timedelta(days=DIA_ALVO)
    serie = sorted([(publicado_em, 0), *((dia, v) for dia, v in pontos if dia >= publicado_em)])
    depois = [p for p in serie if p[0] >= alvo]
    if not depois:
        return Medida("maturando", None)
    d1, v1 = depois[0]
    d0, v0 = [p for p in serie if p[0] <= alvo][-1]
    valor = float(v1) if d1 == d0 else v0 + (v1 - v0) * (alvo - d0).days / (d1 - d0).days
    return Medida("estimado" if (d1 - alvo).days > FOLGA_DIAS else "medido", valor)
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_painel_metodo.py -q`
Expected: `5 passed`

- [ ] **Step 5: Check e commit**

```bash
git add src/cortes/painel/metodo.py tests/test_painel_metodo.py
git commit -m "feat: views aos 7 dias por interpolação dos retratos"
```

---

### Task 7: Linhas e relativo à conta

**Files:**
- Modify: `src/cortes/painel/metodo.py`
- Test: `tests/test_painel_metodo.py` (acrescentar)

- [ ] **Step 1: Ampliar `tests/test_painel_metodo.py`**

Trocar o bloco de imports do topo por:

```python
from datetime import date, datetime

import pytest

from cortes.painel.metodo import Medida, montar_linhas, views_7d
from cortes.painel.publicados import Etiquetas, Publicado
from cortes.painel.retratos import Retrato, VideoRetrato
```

E acrescentar ao final do arquivo:

```python
def retrato(conta: str, dia: int, videos: list[tuple[str, int, int]]) -> Retrato:
    """videos = (id, dia de publicação em outubro, views acumuladas)."""
    return Retrato(conta, datetime(2026, 10, dia, 9), tuple(
        VideoRetrato(vid, f"T {vid}", d(pub), 30.0, views, 80.0, 24.0, 1) for vid, pub, views in videos))


def test_relativo_e_views_7d_sobre_a_mediana_da_conta() -> None:
    rs = {"grana": [retrato("grana", 20, [("a", 1, 100), ("b", 1, 200), ("c", 1, 400)])]}
    linhas = {l.video_id: l for l in montar_linhas(rs, [])}
    assert linhas["c"].rel == pytest.approx(2.0) and linhas["a"].rel == pytest.approx(0.5)


def test_conta_com_menos_de_3_medidos_fica_sem_base() -> None:
    rs = {"grana": [retrato("grana", 20, [("a", 1, 100), ("b", 1, 200), ("m", 18, 50)])]}
    linhas = {l.video_id: l for l in montar_linhas(rs, [])}
    assert linhas["a"].rel is None and linhas["m"].medida.estado == "maturando"


def test_ligado_traz_etiquetas_e_sem_ligacao_vem_vazio() -> None:
    rs = {"grana": [retrato("grana", 20, [("a", 1, 100), ("b", 1, 200), ("c", 1, 400)])]}
    p = Publicado("a", "grana", d(1), "testes/f7-x", Etiquetas("f7", ("humor",), "PrimoCast"))
    linhas = {l.video_id: l for l in montar_linhas(rs, [p])}
    assert linhas["a"].etiquetas == p.etiquetas and linhas["a"].corte == "testes/f7-x"
    assert linhas["b"].etiquetas is None and linhas["b"].corte is None


def test_usa_o_ultimo_retrato_para_totais() -> None:
    rs = {"grana": [retrato("grana", 5, [("a", 1, 100)]), retrato("grana", 9, [("a", 1, 300)])]}
    (linha,) = montar_linhas(rs, [])
    assert linha.views == 300 and linha.medida == Medida("medido", 250.0)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_painel_metodo.py -q`
Expected: FAIL — `ImportError: cannot import name 'montar_linhas'`

- [ ] **Step 3: Acrescentar a `src/cortes/painel/metodo.py`**

Trocar o bloco de imports do topo por:

```python
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import Literal

from cortes.painel.publicados import Etiquetas, Publicado
from cortes.painel.retratos import Retrato, VideoRetrato
```

Logo abaixo de `FOLGA_DIAS = 3 ...`, acrescentar:

```python
BASE_MIN = 3     # Shorts medidos para a conta ter mediana de referência
```

E ao final do arquivo:

```python
@dataclass(frozen=True)
class Linha:
    """Um Short como a tela o mostra: totais do último retrato + medida + ligação."""
    video_id: str
    conta: str
    titulo: str
    publicado_em: date
    etiquetas: Etiquetas | None   # None = ainda sem ligação
    corte: str | None
    medida: Medida
    rel: float | None             # views_7d ÷ mediana da conta; None sem base ou maturando
    views: int
    pct_media: float
    inscritos: int


def _base(valores: list[float]) -> float | None:
    if len(valores) < BASE_MIN:
        return None
    m = median(valores)
    return m if m > 0 else None


def _linhas_da_conta(conta: str, rs: list[Retrato], pub: dict[str, Publicado]) -> list[Linha]:
    ultimo: dict[str, VideoRetrato] = {}
    pontos: dict[str, list[tuple[date, int]]] = {}
    for r in rs:
        for v in r.videos:
            ultimo[v.video_id] = v
            pontos.setdefault(v.video_id, []).append((r.dia, v.views))
    medidas = {vid: views_7d(v.publicado_em, pontos[vid]) for vid, v in ultimo.items()}
    base = _base([m.views_7d for m in medidas.values() if m.views_7d is not None])
    linhas = []
    for vid, v in ultimo.items():
        m = medidas[vid]
        p = pub.get(vid) if vid in pub and pub[vid].conta == conta else None
        rel = m.views_7d / base if base is not None and m.views_7d is not None else None
        linhas.append(Linha(vid, conta, v.titulo, v.publicado_em, p.etiquetas if p else None,
                            p.corte if p else None, m, rel, v.views, v.pct_media, v.inscritos))
    return linhas


def montar_linhas(retratos: dict[str, list[Retrato]], publicados: list[Publicado]) -> list[Linha]:
    """Todos os Shorts dos retratos, do mais novo ao mais antigo. A base de cada conta usa todos
    os Shorts medidos dela, ligados ou não."""
    pub = {p.video_id: p for p in publicados}
    linhas = [linha for conta, rs in retratos.items() for linha in _linhas_da_conta(conta, rs, pub)]
    return sorted(linhas, key=lambda linha: linha.publicado_em, reverse=True)
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_painel_metodo.py -q`
Expected: `9 passed`

- [ ] **Step 5: Check e commit**

Run: o comando de check.

```bash
git add src/cortes/painel/metodo.py tests/test_painel_metodo.py
git commit -m "feat: linhas dos Shorts com relativo à mediana da conta"
```

---

### Task 8: Comparação — grupos, matriz e confusão

**Files:**
- Create: `src/cortes/painel/comparacao.py`
- Test: `tests/test_painel_comparacao.py`

- [ ] **Step 1: Escrever os testes**

```python
from datetime import date

import pytest

from cortes.painel.comparacao import Celula, Confusao, confusoes, dimensao, grupos, matriz
from cortes.painel.dados import ErroPainel
from cortes.painel.metodo import Linha, Medida
from cortes.painel.publicados import Etiquetas


def linha(vid: str, conta: str, formato: str | None, rel: float | None, temas: tuple[str, ...] = (),
          views: int = 1000, inscritos: int = 1) -> Linha:
    etq = Etiquetas(formato, temas, "PrimoCast") if formato else None
    return Linha(vid, conta, f"T {vid}", date(2026, 10, 1), etq, "testes/x" if etq else None,
                 Medida("medido", float(views)), rel, views, 80.0, inscritos)


LINHAS = [
    linha("a", "grana", "f7", 3.0, ("humor", "famoso")), linha("b", "grana", "f7", 1.0),
    linha("c", "riso", "f7", 2.0, ("humor",)), linha("d", "grana", "f4", 0.5),
    linha("e", "grana", None, 9.0),          # sem ligação: fora
    linha("f", "riso", "f4", None),          # sem rel: fora
]


def test_grupos_por_formato() -> None:
    f7, f4 = grupos(LINHAS, "formato")
    assert (f7.chave, f7.n, f7.rel_mediana, f7.pista) == ("f7", 3, 2.0, True)
    assert f7.rels == (1.0, 2.0, 3.0) and set(f7.video_ids) == {"a", "b", "c"}
    assert (f4.chave, f4.n) == ("f4", 1)


def test_inscritos_por_mil_views() -> None:
    (g,) = grupos([linha("a", "grana", "f7", 1.0, views=2000, inscritos=3)], "formato")
    assert g.insc_por_mil == pytest.approx(1.5)


def test_tema_multivalor_entra_em_todos_os_grupos() -> None:
    gs = {g.chave: g for g in grupos(LINHAS, "tema")}
    assert gs["humor"].n == 2 and gs["famoso"].n == 1


def test_pista_some_com_n_5() -> None:
    ls = [linha(str(i), "grana", "f7", 1.0) for i in range(5)]
    assert not grupos(ls, "formato")[0].pista


def test_matriz() -> None:
    cel = {(c.formato, c.conta): c for c in matriz(LINHAS)}
    assert cel[("f7", "grana")] == Celula("f7", "grana", 2, 2.0)
    assert ("f4", "riso") not in cel


def test_confusoes() -> None:
    # f4 só tem Short medido em grana; riso só tem f7 medido (o 'f' não tem relativo)
    assert confusoes(LINHAS) == [Confusao("formato", "f4", "grana"), Confusao("conta", "riso", "f7")]


def test_dimensao_invalida() -> None:
    assert dimensao("tema") == "tema"
    with pytest.raises(ErroPainel, match="dimensão 'cor'"):
        dimensao("cor")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_painel_comparacao.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implementar `src/cortes/painel/comparacao.py`**

```python
"""Comparação entre grupos de Shorts (spec painel §5.3–5.4). Puro.

Mediana, não média: views de Short têm cauda longa e um viral puxa a média do grupo inteiro.
"""
from dataclasses import dataclass
from statistics import median
from typing import Literal

from cortes.painel.dados import ErroPainel
from cortes.painel.metodo import Linha

Dimensao = Literal["formato", "conta", "tema", "podcast"]
DIMENSOES: tuple[Dimensao, ...] = ("formato", "conta", "tema", "podcast")
PISTA_N = 5


@dataclass(frozen=True)
class Grupo:
    chave: str
    n: int
    rel_mediana: float
    pct_mediana: float
    insc_por_mil: float | None
    pista: bool
    rels: tuple[float, ...]
    video_ids: tuple[str, ...]


@dataclass(frozen=True)
class Celula:
    formato: str
    conta: str
    n: int
    rel_mediana: float


@dataclass(frozen=True)
class Confusao:
    """Formato que só rodou numa conta (ou conta com um formato só): o número mistura os dois."""
    tipo: Literal["formato", "conta"]
    chave: str
    unico: str


def dimensao(texto: str) -> Dimensao:
    for d in DIMENSOES:
        if d == texto:
            return d
    raise ErroPainel(f"dimensão '{texto}' inválida; use uma de {DIMENSOES}")


def _comparaveis(linhas: list[Linha]) -> list[tuple[Linha, float]]:
    return [(linha, linha.rel) for linha in linhas if linha.etiquetas is not None and linha.rel is not None]


def comparaveis(linhas: list[Linha]) -> int:
    return len(_comparaveis(linhas))


def _chaves(linha: Linha, dim: Dimensao) -> list[str]:
    e = linha.etiquetas
    if e is None:
        return []
    return {"formato": [e.formato], "conta": [linha.conta], "tema": list(e.temas),
            "podcast": [e.podcast]}[dim]


def _grupo(chave: str, itens: list[tuple[Linha, float]]) -> Grupo:
    views = sum(linha.views for linha, _ in itens)
    inscritos = sum(linha.inscritos for linha, _ in itens)
    rels = sorted(rel for _, rel in itens)
    return Grupo(chave, len(itens), median(rels), median(linha.pct_media for linha, _ in itens),
                 inscritos / views * 1000 if views else None, len(itens) < PISTA_N,
                 tuple(rels), tuple(linha.video_id for linha, _ in itens))


def grupos(linhas: list[Linha], dim: Dimensao) -> list[Grupo]:
    """Só Shorts ligados e com relativo. Em 'tema', um Short entra em todos os seus temas."""
    por_chave: dict[str, list[tuple[Linha, float]]] = {}
    for linha, rel in _comparaveis(linhas):
        for chave in _chaves(linha, dim):
            por_chave.setdefault(chave, []).append((linha, rel))
    return sorted((_grupo(k, v) for k, v in por_chave.items()), key=lambda g: g.rel_mediana, reverse=True)


def matriz(linhas: list[Linha]) -> list[Celula]:
    por_celula: dict[tuple[str, str], list[float]] = {}
    for linha, rel in _comparaveis(linhas):
        assert linha.etiquetas is not None
        por_celula.setdefault((linha.etiquetas.formato, linha.conta), []).append(rel)
    return [Celula(f, c, len(rels), median(rels)) for (f, c), rels in sorted(por_celula.items())]


def confusoes(linhas: list[Linha]) -> list[Confusao]:
    contas_do_formato: dict[str, set[str]] = {}
    formatos_da_conta: dict[str, set[str]] = {}
    for cel in matriz(linhas):
        contas_do_formato.setdefault(cel.formato, set()).add(cel.conta)
        formatos_da_conta.setdefault(cel.conta, set()).add(cel.formato)
    return ([Confusao("formato", f, next(iter(cs))) for f, cs in sorted(contas_do_formato.items()) if len(cs) == 1]
            + [Confusao("conta", c, next(iter(fs))) for c, fs in sorted(formatos_da_conta.items()) if len(fs) == 1])
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_painel_comparacao.py -q`
Expected: `7 passed`

- [ ] **Step 5: Check e commit**

```bash
git add src/cortes/painel/comparacao.py tests/test_painel_comparacao.py
git commit -m "feat: grupos, matriz formato x conta e detecção de confusão"
```

---

### Task 9: Ligação — cortes conhecidos e sugestão por título

**Files:**
- Create: `src/cortes/painel/ligacao.py`
- Test: `tests/test_painel_ligacao.py`

- [ ] **Step 1: Escrever os testes**

```python
import json
from pathlib import Path

from cortes.painel.ligacao import CorteConhecido, listar_cortes, sugerir


def arvore(raiz: Path) -> None:
    for nome in ("comum", "_fontes", "f7-conversa-comediante", "f1-falante-95-carteiras",
                 "f9-sem-formato", "short-400mil"):
        (raiz / "testes" / nome).mkdir(parents=True)
    (raiz / "episodios" / "abc" / "cortes" / "1").mkdir(parents=True)
    (raiz / "episodios" / "abc" / "meta.json").write_text(json.dumps({"canal": "PrimoCast"}), encoding="utf-8")


def test_lista_cortes_de_testes_e_episodios(tmp_path: Path) -> None:
    arvore(tmp_path)
    cortes = {c.caminho: c for c in listar_cortes(tmp_path, {"f1", "f7"})}
    assert set(cortes) == {"testes/f1-falante-95-carteiras", "testes/f7-conversa-comediante",
                           "testes/f9-sem-formato", "testes/short-400mil", "episodios/abc/cortes/1"}
    assert cortes["testes/f7-conversa-comediante"].formato == "f7"
    assert cortes["testes/f9-sem-formato"].formato is None       # f9 não está nos formatos
    assert cortes["episodios/abc/cortes/1"].podcast == "PrimoCast"


def test_sem_pastas_lista_vazia(tmp_path: Path) -> None:
    assert listar_cortes(tmp_path, {"f7"}) == []


def test_sugere_pelo_titulo() -> None:
    cortes = [CorteConhecido("testes/f1-falante-95-carteiras", "f1-falante-95-carteiras", "f1", None),
              CorteConhecido("testes/f7-conversa-comediante", "f7-conversa-comediante", "f7", None)]
    assert sugerir("O COMEDIANTE que mais vende #shorts", cortes)[0].formato == "f7"
    assert sugerir("95% das carteiras estão erradas", cortes)[0].formato == "f1"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_painel_ligacao.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implementar `src/cortes/painel/ligacao.py`**

```python
"""Cortes conhecidos no disco e sugestão do corte pelo título do Short (spec painel §4.2)."""
import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from cortes.episodio import ler_json

_FORMATO = re.compile(r"^(f\d+)-")
_FORA_DE_TESTES = {"comum"}   # código compartilhado, não é corte


@dataclass(frozen=True)
class CorteConhecido:
    caminho: str           # relativo à raiz, com "/"
    nome: str
    formato: str | None    # pelo prefixo da pasta (f7-…), se existir em formatos.yaml
    podcast: str | None    # 'canal' do meta.json do episódio, quando o corte está em episodios/


def _corte(raiz: Path, pasta: Path, formatos: Collection[str], podcast: str | None) -> CorteConhecido:
    m = _FORMATO.match(pasta.name)
    formato = m.group(1) if m and m.group(1) in formatos else None
    return CorteConhecido(pasta.relative_to(raiz).as_posix(), pasta.name, formato, podcast)


def listar_cortes(raiz: Path, formatos: Collection[str]) -> list[CorteConhecido]:
    cortes: list[CorteConhecido] = []
    testes = raiz / "testes"
    if testes.is_dir():
        for p in sorted(testes.iterdir()):
            if p.is_dir() and not p.name.startswith(("_", ".")) and p.name not in _FORA_DE_TESTES:
                cortes.append(_corte(raiz, p, formatos, None))
    for p in sorted((raiz / "episodios").glob("*/cortes/*")):
        if p.is_dir():
            meta = p.parent.parent / "meta.json"
            podcast = str(ler_json(meta)["canal"]) if meta.exists() else None
            cortes.append(_corte(raiz, p, formatos, podcast))
    return cortes


def _palavras(texto: str) -> set[str]:
    texto = re.sub(r"#\w+", " ", texto.lower())
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return {w for w in re.split(r"[^a-z0-9]+", texto) if len(w) >= 3}


def sugerir(titulo: str, cortes: list[CorteConhecido], n: int = 5) -> list[CorteConhecido]:
    """Ordena pela fração das palavras do nome da pasta que aparecem no título; desempata por
    semelhança de texto. É só sugestão: a tela sempre pede confirmação."""
    alvo = _palavras(titulo)

    def nota(c: CorteConhecido) -> tuple[float, float]:
        ps = _palavras(c.nome)
        comum = len(alvo & ps) / len(ps) if ps else 0.0
        return comum, SequenceMatcher(None, " ".join(sorted(alvo)), " ".join(sorted(ps))).ratio()

    return sorted(cortes, key=nota, reverse=True)[:n]
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_painel_ligacao.py -q`
Expected: `3 passed`

- [ ] **Step 5: Check e commit**

```bash
git add src/cortes/painel/ligacao.py tests/test_painel_ligacao.py
git commit -m "feat: cortes conhecidos e sugestão de corte pelo título"
```

---

### Task 10: Coleta pela skill `youtube-analytics`

**Files:**
- Create: `src/cortes/painel/coleta.py`
- Test: `tests/test_painel_coleta.py`

- [ ] **Step 1: Escrever os testes**

```python
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from cortes.painel.coleta import (
    ErroColeta,
    Resultado,
    abrir_login,
    coletar_todas,
    comando_numeros,
    verificar_skill,
    zip_da_saida,
)
from cortes.painel.dados import Conta, ErroPainel
from cortes.painel.retratos import ler_retratos

CSV = ("Conteúdo,Título do vídeo,Horário de publicação do vídeo,Duração,Visualizações,"
       "Duração média da visualização,Porcentagem visualizada média (%),Inscritos\n"
       'abcdefghijk,Um Short,"Oct 1, 2026",30,500,0:00:20,70.5,2\n')
GRANA = Conta("grana", "Grana", "@grana", "financas", "grana")
RISO = Conta("riso", "Riso", "@riso", "humor", "riso")
AGORA = datetime(2026, 10, 10, 9, 12)


def executor_falso(falha_em: str | None = None):  # type: ignore[no-untyped-def]
    def executar(args: list[str], cwd: Path) -> str:
        perfil = args[args.index("--perfil") + 1]
        if perfil == falha_em:
            raise ErroColeta("login expirado")
        destino = Path(args[args.index("--destino") + 1])
        arq = destino / "Conteúdo.zip"
        with zipfile.ZipFile(arq, "w") as z:
            z.writestr("Dados da tabela.csv", CSV.encode("utf-8-sig"))
        return f"[09:12:00] canal UC123\n[09:12:30] pronto: {arq}\n"
    return executar


def test_comando_pede_desde_sempre_e_metricas() -> None:
    args = comando_numeros("grana", Path("/tmp/x"))
    assert args[:3] == ["node", "src/cli.mjs", "numeros"]
    assert args[args.index("--dias") + 1] == "0"
    assert args[args.index("--metricas") + 1] == "views,duracao_media,pct_media,inscritos"


def test_zip_da_saida() -> None:
    assert zip_da_saida("[1] x\n[2] pronto: C:/a b/Conteúdo.zip\n") == Path("C:/a b/Conteúdo.zip")
    with pytest.raises(ErroColeta, match="não informou"):
        zip_da_saida("[1] nada aqui")


def test_falha_numa_conta_nao_para_as_outras(tmp_path: Path) -> None:
    vistos: list[Resultado] = []
    res = coletar_todas([GRANA, RISO], tmp_path, tmp_path / "retratos", lambda: AGORA,
                        executor_falso(falha_em="grana"), vistos.append)
    assert res == vistos
    assert res[0] == Resultado("grana", False, "login expirado")
    assert res[1] == Resultado("riso", True, "1 vídeos")
    assert set(ler_retratos(tmp_path / "retratos")) == {"riso"}


def test_verificar_skill(tmp_path: Path) -> None:
    with pytest.raises(ErroPainel, match="cli.mjs"):
        verificar_skill(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "cli.mjs").write_text("", encoding="utf-8")
    with pytest.raises(ErroPainel, match="npm install"):
        verificar_skill(tmp_path)
    (tmp_path / "node_modules").mkdir()
    verificar_skill(tmp_path)


def test_abrir_login() -> None:
    abertos: list[tuple[list[str], Path]] = []
    abrir_login(GRANA, Path("skill"), lambda args, cwd: abertos.append((args, cwd)))
    assert abertos == [(["node", "src/cli.mjs", "login", "--perfil", "grana"], Path("skill"))]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_painel_coleta.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implementar `src/cortes/painel/coleta.py`**

```python
"""Coleta dos números pela skill youtube-analytics (export do Studio via Playwright).

Uma conta por vez; a falha de uma não interrompe as outras e volta com a causa.
O login é manual, na janela do Chrome que a skill abre: o app nunca vê senha.
"""
import re
import subprocess
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cortes.painel.dados import Conta, ErroPainel
from cortes.painel.retratos import Retrato, salvar_retrato
from cortes.painel.studio import ler_tabela, texto_do_zip

Executor = Callable[[list[str], Path], str]
Abridor = Callable[[list[str], Path], object]
TIMEOUT_S = 600
METRICAS = "views,duracao_media,pct_media,inscritos"
_PRONTO = re.compile(r"pronto: (.+\.zip)\s*$", re.MULTILINE)


class ErroColeta(RuntimeError):
    pass


@dataclass(frozen=True)
class Resultado:
    conta: str
    ok: bool
    mensagem: str


def verificar_skill(skill_dir: Path) -> None:
    if not (skill_dir / "src" / "cli.mjs").exists():
        raise ErroPainel(f"skill youtube-analytics não encontrada em {skill_dir} (falta src/cli.mjs); "
                         "passe o caminho certo com --skill")
    if not (skill_dir / "node_modules").is_dir():
        raise ErroPainel(f"{skill_dir}: dependências da skill ausentes; rode 'npm install' nessa pasta")


def comando_numeros(perfil: str, destino: Path) -> list[str]:
    return ["node", "src/cli.mjs", "numeros", "--perfil", perfil, "--dias", "0",
            "--metricas", METRICAS, "--destino", str(destino)]


def comando_login(perfil: str) -> list[str]:
    return ["node", "src/cli.mjs", "login", "--perfil", perfil]


def zip_da_saida(saida: str) -> Path:
    achados = _PRONTO.findall(saida)
    if not achados:
        raise ErroColeta(f"o export não informou o zip gerado: {saida[-300:]}")
    return Path(achados[-1].strip())


def _executar(args: list[str], cwd: Path) -> str:
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired as e:
        raise ErroColeta(f"o export não terminou em {TIMEOUT_S}s") from e
    if r.returncode != 0:
        raise ErroColeta((r.stderr or r.stdout).strip()[-500:] or f"saiu com código {r.returncode}")
    return r.stdout


def _abrir(args: list[str], cwd: Path) -> object:
    return subprocess.Popen(args, cwd=cwd)


def coletar_conta(conta: Conta, skill_dir: Path, pasta_retratos: Path, agora: datetime,
                  executar: Executor = _executar) -> Retrato:
    with tempfile.TemporaryDirectory() as tmp:
        texto = texto_do_zip(zip_da_saida(executar(comando_numeros(conta.perfil_studio, Path(tmp)), skill_dir)))
    try:
        videos = ler_tabela(texto)
    except ErroPainel as e:
        raise ErroPainel(f"conta '{conta.id}': {e}") from e
    retrato = Retrato(conta.id, agora, tuple(videos))
    salvar_retrato(pasta_retratos, retrato)
    return retrato


def coletar_todas(contas: Iterable[Conta], skill_dir: Path, pasta_retratos: Path,
                  agora: Callable[[], datetime], executar: Executor = _executar,
                  ao_terminar: Callable[[Resultado], None] | None = None) -> list[Resultado]:
    resultados: list[Resultado] = []
    for conta in contas:
        try:
            r = coletar_conta(conta, skill_dir, pasta_retratos, agora(), executar)
            res = Resultado(conta.id, True, f"{len(r.videos)} vídeos")
        except (ErroColeta, ErroPainel, OSError) as e:
            res = Resultado(conta.id, False, str(e))
        if ao_terminar is not None:
            ao_terminar(res)
        resultados.append(res)
    return resultados


def abrir_login(conta: Conta, skill_dir: Path, abrir: Abridor = _abrir) -> None:
    abrir(comando_login(conta.perfil_studio), skill_dir)
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_painel_coleta.py -q`
Expected: `5 passed`

- [ ] **Step 5: Check e commit**

```bash
git add src/cortes/painel/coleta.py tests/test_painel_coleta.py
git commit -m "feat: coleta por conta pela skill youtube-analytics com falha isolada"
```

---

### Task 11: Servidor FastAPI

**Files:**
- Create: `src/cortes/painel/servidor.py`
- Test: `tests/test_painel_servidor.py`

- [ ] **Step 1: Escrever os testes**

```python
import json
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cortes.painel.coleta import ErroColeta
from cortes.painel.dados import ErroPainel
from cortes.painel.retratos import Retrato, VideoRetrato, salvar_retrato
from cortes.painel.servidor import Config, criar_app

PERFIL = """nicho: financas
filtro_tema: "x"
rubrica: {gancho_3s: 0.3, autocontido: 0.25, espanto: 0.2, historia_ou_virada: 0.1, fechamento: 0.15}
bonus: {humor: "faz rir"}
penalidade: {}
duracao_s: {min: 20, max: 90}
"""
CONTAS = 'contas:\n  - {id: grana, nome: Grana, handle: "@grana", nicho: financas, perfil_studio: grana}\n'


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    nicho = tmp_path / "nichos" / "financas"
    (nicho / "exemplos").mkdir(parents=True)
    (nicho / "perfil.yaml").write_text(PERFIL, encoding="utf-8")
    for arq in ("bons.jsonl", "ruins.jsonl"):
        (nicho / "exemplos" / arq).write_text("", encoding="utf-8")
    (tmp_path / "contas").mkdir()
    (tmp_path / "contas" / "contas.yaml").write_text(CONTAS, encoding="utf-8")
    (tmp_path / "contas" / "formatos.yaml").write_text("formatos:\n  f7: {nome: Conversa}\n", encoding="utf-8")
    (tmp_path / "testes" / "f7-conversa-comediante").mkdir(parents=True)
    estatico = tmp_path / "web"
    estatico.mkdir()
    (estatico / "index.html").write_text("<h1>painel</h1>", encoding="utf-8")
    skill = tmp_path / "skill"
    (skill / "src").mkdir(parents=True)
    (skill / "src" / "cli.mjs").write_text("", encoding="utf-8")
    (skill / "node_modules").mkdir()
    c = Config(raiz=tmp_path, skill_dir=skill, estatico=estatico)
    videos = tuple(VideoRetrato(f"vid{i}xxxxxxx", f"O comediante {i}", date(2026, 10, 1), 30.0, 100 * i, 80.0, 24.0, 1)
                   for i in range(1, 4))
    salvar_retrato(c.retratos, Retrato("grana", datetime(2026, 10, 20, 9), videos))
    return c


def falhar(args: list[str], cwd: Path) -> str:
    raise ErroColeta("login expirado")


def cliente(cfg: Config) -> TestClient:
    return TestClient(criar_app(cfg, executar=falhar, abrir=lambda args, cwd: None))


LIGACAO = {"link": "https://youtube.com/shorts/vid1xxxxxxx", "conta": "grana",
           "corte": "testes/f7-conversa-comediante", "formato": "f7", "temas": ["humor"], "podcast": "PrimoCast"}


def test_estado(cfg: Config) -> None:
    e = cliente(cfg).get("/api/estado").json()
    assert e["contas"][0]["id"] == "grana" and e["contas"][0]["ultimo_retrato"] is not None
    assert e["formatos"]["f7"]["nome"] == "Conversa" and e["temas"] == ["humor"]
    assert e["nichos"] == ["financas"] and e["rodando"] is False


def test_ligar_e_comparar(cfg: Config) -> None:
    c = cliente(cfg)
    assert c.post("/api/ligar", json=LIGACAO).status_code == 200
    linhas = {l["video_id"]: l for l in c.get("/api/shorts").json()}
    assert linhas["vid1xxxxxxx"]["etiquetas"]["formato"] == "f7"
    assert linhas["vid2xxxxxxx"]["etiquetas"] is None
    comp = c.get("/api/comparar", params={"dim": "formato"}).json()
    assert comp["grupos"][0]["chave"] == "f7" and comp["medidos"] == 1


def test_ligar_video_fora_do_retrato(cfg: Config) -> None:
    r = cliente(cfg).post("/api/ligar", json={**LIGACAO, "link": "https://youtu.be/naoexiste00"})
    assert r.status_code == 422 and "último retrato" in r.json()["detail"]


def test_ligar_formato_invalido(cfg: Config) -> None:
    r = cliente(cfg).post("/api/ligar", json={**LIGACAO, "formato": "f9"})
    assert r.status_code == 422 and "formato 'f9'" in r.json()["detail"]


def test_sugestoes(cfg: Config) -> None:
    sug = cliente(cfg).get("/api/sugestoes/vid1xxxxxxx").json()
    assert sug[0]["caminho"] == "testes/f7-conversa-comediante" and sug[0]["formato"] == "f7"


def test_atualizar_registra_falha(cfg: Config) -> None:
    app = criar_app(cfg, executar=falhar, abrir=lambda args, cwd: None)
    c = TestClient(app)
    assert c.post("/api/atualizar", json={}).status_code == 202
    app.state.coleta.fio.join(timeout=5)
    conta = c.get("/api/estado").json()["contas"][0]
    assert conta["coleta"] == {"conta": "grana", "ok": False, "mensagem": "login expirado"}


def test_nova_conta_com_nicho_inexistente_nao_grava(cfg: Config) -> None:
    antes = (cfg.raiz / "contas" / "contas.yaml").read_text(encoding="utf-8")
    r = cliente(cfg).post("/api/contas", json={"id": "riso", "nome": "Riso", "handle": "@riso",
                                               "nicho": "humor", "perfil_studio": "riso"})
    assert r.status_code == 422 and "nicho 'humor'" in r.json()["detail"]
    assert (cfg.raiz / "contas" / "contas.yaml").read_text(encoding="utf-8") == antes


def test_nova_conta_valida(cfg: Config) -> None:
    r = cliente(cfg).post("/api/contas", json={"id": "bolso", "nome": "Bolso", "handle": "@bolso",
                                               "nicho": "financas", "perfil_studio": "bolso"})
    assert r.status_code == 201
    assert [c["id"] for c in cliente(cfg).get("/api/estado").json()["contas"]] == ["grana", "bolso"]


def test_dimensao_invalida(cfg: Config) -> None:
    assert cliente(cfg).get("/api/comparar", params={"dim": "cor"}).status_code == 422


def test_nao_sobe_sem_a_skill(cfg: Config) -> None:
    with pytest.raises(ErroPainel, match="cli.mjs"):
        criar_app(Config(cfg.raiz, cfg.raiz / "nada", cfg.estatico))


def test_publicados_gravado_em_disco(cfg: Config) -> None:
    cliente(cfg).post("/api/ligar", json=LIGACAO)
    linha = json.loads(cfg.publicados.read_text(encoding="utf-8").splitlines()[0])
    assert linha["publicado_em"] == "2026-10-01" and linha["etiquetas"]["podcast"] == "PrimoCast"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_painel_servidor.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cortes.painel.servidor'`

- [ ] **Step 3: Implementar `src/cortes/painel/servidor.py`**

```python
"""Servidor local do painel: rotas JSON finas sobre as funções puras + a página estática."""
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cortes.episodio import id_do_video
from cortes.painel import coleta
from cortes.painel.comparacao import comparaveis, confusoes, dimensao, grupos, matriz
from cortes.painel.dados import ErroPainel, carregar_contas, carregar_vocabulario
from cortes.painel.ligacao import listar_cortes, sugerir
from cortes.painel.metodo import montar_linhas
from cortes.painel.publicados import Etiquetas, Publicado, gravar_publicados, ler_publicados, ligar
from cortes.painel.retratos import ler_retratos


@dataclass(frozen=True)
class Config:
    raiz: Path        # onde ficam contas/, nichos/, testes/, episodios/
    skill_dir: Path   # scripts/ da skill youtube-analytics
    estatico: Path    # web/static

    @property
    def contas_yaml(self) -> Path:
        return self.raiz / "contas" / "contas.yaml"

    @property
    def publicados(self) -> Path:
        return self.raiz / "contas" / "publicados.jsonl"

    @property
    def retratos(self) -> Path:
        return self.raiz / "contas" / "retratos"


@dataclass
class EstadoColeta:
    trava: threading.Lock = field(default_factory=threading.Lock)
    rodando: bool = False
    resultados: dict[str, coleta.Resultado] = field(default_factory=dict)
    fio: threading.Thread | None = None


class NovaConta(BaseModel):
    id: str
    nome: str
    handle: str
    nicho: str
    perfil_studio: str


class Ligacao(BaseModel):
    link: str
    conta: str
    corte: str
    formato: str
    temas: list[str]
    podcast: str


class PedidoAtualizar(BaseModel):
    conta: str | None = None   # None = todas as contas


def criar_app(cfg: Config, executar: coleta.Executor = coleta._executar,
              abrir: coleta.Abridor = coleta._abrir,
              agora: Callable[[], datetime] = datetime.now) -> FastAPI:
    carregar_vocabulario(cfg.raiz)       # configuração inválida: não sobe
    coleta.verificar_skill(cfg.skill_dir)
    app = FastAPI(title="Painel de contas")
    estado = EstadoColeta()
    app.state.coleta = estado

    @app.exception_handler(ErroPainel)
    async def _erro(_: Request, e: ErroPainel) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(e)})

    _rotas_leitura(app, cfg, estado)
    _rotas_acao(app, cfg, estado, executar, abrir, agora)
    app.mount("/", StaticFiles(directory=cfg.estatico, html=True), name="web")
    return app


def _rotas_leitura(app: FastAPI, cfg: Config, estado: EstadoColeta) -> None:
    def linhas() -> Any:
        voc = carregar_vocabulario(cfg.raiz)
        return montar_linhas(ler_retratos(cfg.retratos), ler_publicados(cfg.publicados, voc))

    @app.get("/api/estado")
    def api_estado() -> Any:
        voc = carregar_vocabulario(cfg.raiz)
        retratos = ler_retratos(cfg.retratos)
        pubs = ler_publicados(cfg.publicados, voc)
        contas = [{**asdict(c), "ultimo_retrato": rs[-1].coletado_em if (rs := retratos.get(c.id)) else None,
                   "coleta": estado.resultados.get(c.id),
                   "ligados": sum(1 for p in pubs if p.conta == c.id)} for c in voc.contas.values()]
        nichos = sorted(p.parent.name for p in (cfg.raiz / "nichos").glob("*/perfil.yaml"))
        return jsonable_encoder({"contas": contas, "rodando": estado.rodando, "formatos": voc.formatos,
                                 "temas": sorted(voc.temas), "nichos": nichos,
                                 "podcasts": sorted({p.etiquetas.podcast for p in pubs})})

    @app.get("/api/shorts")
    def api_shorts() -> Any:
        return jsonable_encoder(linhas())

    @app.get("/api/cortes")
    def api_cortes() -> Any:
        return jsonable_encoder(listar_cortes(cfg.raiz, carregar_vocabulario(cfg.raiz).formatos))

    @app.get("/api/sugestoes/{video_id}")
    def api_sugestoes(video_id: str) -> Any:
        linha = next((x for x in linhas() if x.video_id == video_id), None)
        if linha is None:
            raise ErroPainel(f"vídeo '{video_id}' não está em nenhum retrato")
        cortes = listar_cortes(cfg.raiz, carregar_vocabulario(cfg.raiz).formatos)
        return jsonable_encoder(sugerir(linha.titulo, cortes))

    @app.get("/api/comparar")
    def api_comparar(dim: str = "formato") -> Any:
        d, ls = dimensao(dim), linhas()
        return jsonable_encoder({"grupos": grupos(ls, d), "matriz": matriz(ls), "confusoes": confusoes(ls),
                                 "medidos": comparaveis(ls),
                                 "maturando": sum(1 for x in ls if x.medida.estado == "maturando")})


def _rotas_acao(app: FastAPI, cfg: Config, estado: EstadoColeta, executar: coleta.Executor,
                abrir: coleta.Abridor, agora: Callable[[], datetime]) -> None:
    @app.post("/api/atualizar", status_code=202)
    def api_atualizar(pedido: PedidoAtualizar) -> dict[str, bool]:
        voc = carregar_vocabulario(cfg.raiz)
        if pedido.conta is not None and pedido.conta not in voc.contas:
            raise ErroPainel(f"conta '{pedido.conta}' não existe")
        alvo = [voc.contas[pedido.conta]] if pedido.conta else list(voc.contas.values())
        with estado.trava:
            if estado.rodando:
                raise HTTPException(409, "já existe uma atualização rodando")
            estado.rodando = True

        def rodar() -> None:
            try:
                coleta.coletar_todas(alvo, cfg.skill_dir, cfg.retratos, agora, executar,
                                     lambda r: estado.resultados.__setitem__(r.conta, r))
            finally:
                estado.rodando = False

        estado.fio = threading.Thread(target=rodar, daemon=True)
        estado.fio.start()
        return {"iniciado": True}

    @app.post("/api/login/{conta_id}", status_code=202)
    def api_login(conta_id: str) -> dict[str, bool]:
        voc = carregar_vocabulario(cfg.raiz)
        if conta_id not in voc.contas:
            raise ErroPainel(f"conta '{conta_id}' não existe")
        coleta.abrir_login(voc.contas[conta_id], cfg.skill_dir, abrir)
        return {"aberto": True}

    @app.post("/api/contas", status_code=201)
    def api_nova_conta(nova: NovaConta) -> dict[str, str]:
        _acrescentar_conta(cfg, nova)
        return {"id": nova.id}

    @app.post("/api/ligar")
    def api_ligar(lig: Ligacao) -> Any:
        return jsonable_encoder(_ligar(cfg, lig))


def _acrescentar_conta(cfg: Config, nova: NovaConta) -> None:
    """Grava num .tmp, valida o arquivo inteiro e só então substitui: conta inválida não entra."""
    bruto = yaml.safe_load(cfg.contas_yaml.read_text(encoding="utf-8"))
    bruto["contas"] = [*(bruto.get("contas") or []), nova.model_dump()]
    tmp = cfg.contas_yaml.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(bruto, allow_unicode=True, sort_keys=False), encoding="utf-8")
    try:
        carregar_contas(tmp, cfg.raiz / "nichos")
    except ErroPainel:
        tmp.unlink()
        raise
    tmp.replace(cfg.contas_yaml)


def _ligar(cfg: Config, lig: Ligacao) -> Publicado:
    voc = carregar_vocabulario(cfg.raiz)
    try:
        vid = id_do_video(lig.link)
    except ValueError as e:
        raise ErroPainel(str(e)) from e
    if not (cfg.raiz / lig.corte).is_dir():
        raise ErroPainel(f"corte '{lig.corte}' não existe")
    rs = ler_retratos(cfg.retratos).get(lig.conta)
    video = next((v for v in rs[-1].videos if v.video_id == vid), None) if rs else None
    if video is None:
        raise ErroPainel(f"o vídeo {vid} não está no último retrato de '{lig.conta}': "
                         "atualize a conta e tente de novo")
    novo = Publicado(vid, lig.conta, video.publicado_em, lig.corte,
                     Etiquetas(lig.formato, tuple(lig.temas), lig.podcast.strip()))
    gravar_publicados(cfg.publicados, ligar(ler_publicados(cfg.publicados, voc), novo, voc))
    return novo
```

Nota: `test_estado` espera `e["temas"] == ["humor"]` — o perfil da fixture tem `penalidade: {}`.

- [ ] **Step 4: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_painel_servidor.py -q`
Expected: `11 passed`

- [ ] **Step 5: Check e commit**

Run: o comando de check. O arquivo deve ficar abaixo de 250 linhas.

```bash
git add src/cortes/painel/servidor.py tests/test_painel_servidor.py
git commit -m "feat: servidor do painel com coleta em segundo plano e ligação validada"
```

---

### Task 12: Subcomando `cortes painel`

**Files:**
- Modify: `src/cortes/cli.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Acrescentar ao `src/cortes/cli.py`**

Nos imports, depois de `from cortes.perfil import carregar_perfil`:

```python
import uvicorn

from cortes.painel.servidor import Config, criar_app
```

(Respeite a ordem do ruff/isort: `import uvicorn` vai no bloco de terceiros, junto dos imports da
biblioteca padrão separados por linha em branco; rode `ruff check --fix` se acusar `I001`.)

Abaixo dos imports:

```python
ESTATICO = Path(__file__).resolve().parents[2] / "web" / "static"
SKILL_ANALYTICS = Path.home() / ".claude" / "skills" / "youtube-analytics" / "scripts"
```

Antes de `def main()`:

```python
def rodar_painel(porta: int, skill: Path, raiz: Path) -> None:
    app = criar_app(Config(raiz=raiz, skill_dir=skill, estatico=ESTATICO))
    print(f"painel em http://127.0.0.1:{porta}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=porta)
```

Em `main()`, depois do `det.add_argument("--modelo", ...)`:

```python
    pn = sub.add_parser("painel", help="sobe o painel de contas em 127.0.0.1")
    pn.add_argument("--porta", type=int, default=8765)
    pn.add_argument("--skill", type=Path, default=SKILL_ANALYTICS, help="pasta scripts/ da skill youtube-analytics")
    pn.add_argument("--raiz", type=Path, default=Path.cwd(), help="pasta com contas/, nichos/, testes/")
```

E ao final de `main()`:

```python
    elif args.comando == "painel":
        rodar_painel(args.porta, args.skill, args.raiz)
```

- [ ] **Step 2: Conferir que o comando existe**

Run: `.venv/Scripts/cortes painel --help`
Expected: ajuda listando `--porta`, `--skill`, `--raiz`.

- [ ] **Step 3: Registrar no `CLAUDE.md` do repo**, ao final:

```markdown
## Painel de contas

    .venv/Scripts/cortes painel          # http://127.0.0.1:8765

Spec em `docs/superpowers/specs/2026-10-01-painel-contas-design.md`. Usa a skill
`youtube-analytics` (export do Studio) por subprocesso; contas em `contas/contas.yaml`.
```

- [ ] **Step 4: Check e commit**

```bash
git add src/cortes/cli.py CLAUDE.md
git commit -m "feat: subcomando cortes painel"
```

---

### Task 13: Página — base, estilo e tela Comparar

Sem teste automatizado (JS puro, sem build): a verificação é visual na Task 16. Cada arquivo JS
registra sua tela em `TELAS`; scripts clássicos compartilham o escopo global.

**Files:**
- Create: `web/static/index.html`, `web/static/painel.css`, `web/static/js/base.js`,
  `web/static/js/comparar.js`, `web/static/js/inicio.js`

- [ ] **Step 1: Criar `web/static/index.html`**

```html
<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Painel de Contas</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="painel.css">
</head>
<body>
<div class="app">
  <nav>
    <div class="marca">cortes<b>.</b></div>
    <a href="#contas" data-tela="contas">Contas</a>
    <a href="#shorts" data-tela="shorts">Shorts <span class="cont" id="sem-ligacao" hidden></span></a>
    <a href="#comparar" data-tela="comparar">Comparar</a>
    <div class="contas" id="trilho-contas"></div>
    <button class="atualizar" id="atualizar-todas">↻ Atualizar todas</button>
  </nav>
  <main id="tela"></main>
</div>
<div class="aviso" id="aviso" role="alert" hidden></div>
<div id="camada"></div>
<script src="js/base.js"></script>
<script src="js/comparar.js"></script>
<script src="js/inicio.js"></script>
</body>
</html>
```

- [ ] **Step 2: Criar `web/static/painel.css`**

```css
:root {
  --bg: #0d0e10; --surface: #15171a; --raised: #1c1f23; --line: #262a30; --line-soft: #1e2126;
  --text: #ece7df; --muted: #8b9099; --faint: #5b6068;
  --up: #ff7a2f; --up-soft: rgba(255,122,47,.16); --down: #7d93b8; --warn: #e8c15a; --ok: #5fbf8a;
  --mono: "JetBrains Mono", ui-monospace, monospace; --sans: "Instrument Sans", system-ui, sans-serif;
  --serif: "Instrument Serif", Georgia, serif;
}
* { box-sizing: border-box; margin: 0; }
body { background: var(--bg); color: var(--text); font: 14px/1.45 var(--sans); }
button, input, select { font: inherit; color: inherit; }
.app { display: grid; grid-template-columns: 208px 1fr; min-height: 100vh; }
.up { color: var(--up); } .down { color: var(--down); } .muted { color: var(--muted); }

/* trilho */
nav { border-right: 1px solid var(--line-soft); padding: 22px 14px; display: flex; flex-direction: column; gap: 4px;
  position: sticky; top: 0; height: 100vh; }
.marca { font: italic 26px/1 var(--serif); padding: 0 10px 22px; letter-spacing: -.01em; }
.marca b { font-style: normal; color: var(--up); }
nav a { display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; border-radius: 7px;
  color: var(--muted); text-decoration: none; font-weight: 500; }
nav a:hover { color: var(--text); }
nav a.ativo { background: var(--raised); color: var(--text); }
.cont { font: 500 11px var(--mono); background: var(--up-soft); color: var(--up); padding: 1px 7px; border-radius: 99px; }
.contas { margin-top: auto; border-top: 1px solid var(--line-soft); padding-top: 14px; display: grid; gap: 9px; }
.conta { padding: 0 10px; font-size: 12.5px; display: grid; grid-template-columns: 8px 1fr auto; gap: 8px; align-items: center; }
.conta i, i.estado { width: 7px; height: 7px; border-radius: 50%; background: var(--ok); display: inline-block; }
.conta i.vencido, i.estado.vencido { background: var(--warn); }
.conta small { color: var(--faint); font: 11px var(--mono); }
.atualizar, .botao { padding: 8px 12px; border-radius: 7px; border: 1px solid var(--line); background: none;
  font-weight: 500; font-size: 12.5px; cursor: pointer; }
.atualizar { margin: 6px 10px 0; }
.atualizar:hover:not(:disabled), .botao:hover:not(:disabled) { border-color: var(--up); }
button:disabled { opacity: .5; cursor: default; }
.botao.primario { background: var(--up); border-color: var(--up); color: #1a0d05; }

/* cabeçalho */
main { padding: 28px 36px 60px; max-width: 1240px; min-width: 0; }
header { display: flex; justify-content: space-between; align-items: end; gap: 24px; margin-bottom: 26px; flex-wrap: wrap; }
h1 { font: 400 40px/1 var(--serif); letter-spacing: -.015em; }
h1 em { color: var(--muted); }
.sub { color: var(--muted); margin-top: 8px; font-size: 13px; }
.seg { display: inline-flex; background: var(--surface); border: 1px solid var(--line-soft); border-radius: 9px; padding: 3px; }
.seg button { border: 0; background: none; color: var(--muted); font-weight: 500; font-size: 13px; padding: 7px 14px;
  border-radius: 6px; cursor: pointer; }
.seg button.ativo { background: var(--raised); color: var(--text); }
.legenda { display: flex; gap: 18px; color: var(--muted); font-size: 12px; margin-bottom: 10px; align-items: center; flex-wrap: wrap; }
.legenda span { display: inline-flex; gap: 6px; align-items: center; }
.pt { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }

/* tabela de grupos */
.grupos { background: var(--surface); border: 1px solid var(--line-soft); border-radius: 12px; overflow: hidden; }
.linha { display: grid; grid-template-columns: 190px 44px 104px 1fr 76px 70px; gap: 18px; align-items: center;
  padding: 14px 20px; border-top: 1px solid var(--line-soft); cursor: pointer; transition: background .12s; }
.linha:first-child { border-top: 0; }
.cab { cursor: default; color: var(--faint); font: 500 11px var(--mono); text-transform: uppercase; letter-spacing: .06em; }
.linha.cab { padding: 11px 20px; }
.linha:not(.cab):hover { background: var(--raised); }
.linha.sel { background: var(--raised); box-shadow: inset 2px 0 0 var(--up); }
.nome { font-weight: 600; min-width: 0; }
.nome small { display: block; color: var(--faint); font: 400 11.5px var(--sans); margin-top: 1px; }
.num { font: 500 13px var(--mono); font-variant-numeric: tabular-nums; text-align: right; }
.rel { font: 400 30px/1 var(--serif); text-align: right; font-variant-numeric: tabular-nums; }
.selo { display: inline-block; margin-top: 4px; font: 500 10px var(--mono); text-transform: uppercase; letter-spacing: .06em;
  color: var(--warn); border: 1px solid rgba(232,193,90,.35); padding: 1px 6px; border-radius: 4px; }
svg.strip { width: 100%; height: 34px; overflow: visible; display: block; }
.strip .grade { stroke: var(--line-soft); } .strip .base { stroke: var(--muted); stroke-dasharray: 2 3; }
.strip circle.up { fill: var(--up); fill-opacity: .85; } .strip circle.down { fill: var(--down); fill-opacity: .85; }
.strip .med { fill: var(--text); } .strip text { fill: var(--faint); font: 10px var(--mono); }

/* matriz e painel do grupo */
.baixo { display: grid; grid-template-columns: 1.15fr 1fr; gap: 22px; margin-top: 22px; }
.card { background: var(--surface); border: 1px solid var(--line-soft); border-radius: 12px; padding: 20px; min-width: 0; }
.card h2 { font: 400 22px/1.1 var(--serif); margin-bottom: 4px; }
.card > .sub { margin: 0 0 16px; }
table.matriz { width: 100%; border-collapse: separate; border-spacing: 4px; }
.matriz th { font: 500 11px var(--mono); color: var(--faint); text-align: left; padding: 0 4px 4px; }
.matriz td { height: 46px; border-radius: 7px; padding: 6px 9px; vertical-align: top; position: relative; }
.matriz td.rot { font-size: 12.5px; color: var(--muted); padding-left: 2px; vertical-align: middle; width: 128px; }
.matriz td .v { font: 500 14px var(--mono); }
.matriz td .n { position: absolute; right: 8px; bottom: 6px; font: 10.5px var(--mono); opacity: .7; }
.matriz td.vazia { background: repeating-linear-gradient(135deg, transparent 0 5px, var(--line-soft) 5px 6px);
  color: var(--faint); font-size: 11px; vertical-align: middle; text-align: center; }
.nota { margin-top: 14px; padding: 11px 13px; border-radius: 8px; border-left: 2px solid var(--warn);
  background: rgba(232,193,90,.06); color: #d8cfb8; font-size: 12.5px; }
.nota li { margin-left: 16px; }
.shorts { display: grid; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr)); gap: 10px; }
.thumb { aspect-ratio: 9/16; border-radius: 8px; position: relative; overflow: hidden; background: var(--raised);
  border: 1px solid var(--line); display: flex; flex-direction: column; justify-content: space-between; padding: 8px;
  color: var(--text); text-decoration: none; }
.thumb img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; opacity: .32; }
.thumb > div { position: relative; }
.thumb.up { border-color: rgba(255,122,47,.45); }
.thumb .t { font-size: 11px; line-height: 1.25; font-weight: 600; text-wrap: balance; }
.thumb .x { font: 400 26px/1 var(--serif); }
.thumb .c { font: 10px var(--mono); color: var(--muted); }
.thumb.matura { opacity: .45; border-style: dashed; }
.vazio { padding: 48px 20px; text-align: center; color: var(--muted); }
.vazio h2 { font: 400 26px var(--serif); color: var(--text); margin-bottom: 6px; }

/* aviso */
.aviso { position: fixed; right: 20px; bottom: 20px; max-width: 460px; padding: 12px 16px; border-radius: 9px;
  background: #2a1d12; border: 1px solid rgba(255,122,47,.5); color: var(--text); font-size: 13px; z-index: 30; }

@media (max-width: 900px) {
  .app { grid-template-columns: 1fr; } nav { display: none; }
  main { padding: 20px 16px; }
  .linha { grid-template-columns: 1fr 70px; }
  .linha > :nth-child(2), .linha > :nth-child(4), .linha > :nth-child(5), .linha > :nth-child(6) { display: none; }
  .baixo { grid-template-columns: 1fr; }
}
```

- [ ] **Step 3: Criar `web/static/js/base.js`**

```js
"use strict";
// Estado e utilidades compartilhados pelas telas. Cada tela registra a sua função em TELAS.
const TELAS = {};
let E = null;   // /api/estado
let S = [];     // /api/shorts

const $ = (seletor, el = document) => el.querySelector(seletor);
const $$ = (seletor, el = document) => [...el.querySelectorAll(seletor)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fx = v => v == null ? "—" : v.toFixed(1).replace(".", ",") + "×";
const pct = v => Math.round(v) + "%";
const mil = v => Math.round(v).toLocaleString("pt-BR");
const thumb = id => `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
const handleDe = id => E.contas.find(c => c.id === id)?.handle ?? id;
const nomeFormato = id => E.formatos[id]?.nome ?? id;
const dataHora = iso => new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

function mediana(xs) {
  if (!xs.length) return null;
  const a = [...xs].sort((p, q) => p - q), m = a.length >> 1;
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

async function api(caminho, opcoes = {}) {
  const r = await fetch(caminho, { headers: { "Content-Type": "application/json" }, ...opcoes });
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = corpo.detail;
    throw new Error(typeof d === "string" ? d : d ? JSON.stringify(d) : `HTTP ${r.status}`);
  }
  return corpo;
}
const post = (caminho, corpo) => api(caminho, { method: "POST", body: JSON.stringify(corpo ?? {}) });

function avisar(msg) {
  const a = $("#aviso");
  a.textContent = msg;
  a.hidden = false;
  clearTimeout(avisar.t);
  avisar.t = setTimeout(() => { a.hidden = true; }, 9000);
}

function vazio(titulo, texto) {
  return `<div class="vazio"><h2>${esc(titulo)}</h2><p>${esc(texto)}</p></div>`;
}

function trilho() {
  $("#trilho-contas").innerHTML = E.contas.map(c => {
    const falhou = c.coleta && !c.coleta.ok;
    const alerta = falhou || !c.ultimo_retrato;
    const quando = falhou ? "falhou" : c.ultimo_retrato ? dataHora(c.ultimo_retrato) : "nunca";
    return `<div class="conta" title="${esc(falhou ? c.coleta.mensagem : "")}"><i class="${alerta ? "vencido" : ""}"></i>${esc(c.handle)}<small>${quando}</small></div>`;
  }).join("");
  const b = $("#atualizar-todas");
  b.disabled = E.rodando || !E.contas.length;
  b.textContent = E.rodando ? "atualizando…" : "↻ Atualizar todas";
  const sem = S.filter(l => !l.etiquetas).length;
  $("#sem-ligacao").hidden = !sem;
  $("#sem-ligacao").textContent = `${sem} sem ligação`;
}

async function carregar() {
  [E, S] = await Promise.all([api("/api/estado"), api("/api/shorts")]);
  trilho();
}
```

- [ ] **Step 4: Criar `web/static/js/comparar.js`**

```js
"use strict";
// Tela Comparar: grupos com strip plot, matriz formato × conta, Shorts do grupo selecionado.
let dim = "formato";
let selecionado = null;
const TITULOS = { formato: "por formato", conta: "por conta", tema: "por tema", podcast: "por podcast" };

// escala log de 0,1× a 10×: "metade" e "dobro" ficam à mesma distância de 1×
const px = (v, w) => (Math.log10(Math.min(10, Math.max(.1, v))) + 1) / 2 * w;

function eixo() {
  const marcas = [[.2, "0,2×"], [.5, "0,5×"], [1, "1×"], [2, "2×"], [5, "5×"]];
  return `<svg class="strip" style="height:14px" viewBox="0 0 400 14" preserveAspectRatio="none">${marcas.map(([t, r]) =>
    `<text x="${px(t, 400)}" y="11" text-anchor="middle">${r}</text>`).join("")}</svg>`;
}

function strip(rels, med) {
  const W = 400, H = 34;
  const grade = [.2, .5, 1, 2, 5].map(t => `<line class="grade" x1="${px(t, W)}" x2="${px(t, W)}" y1="4" y2="30"/>`).join("");
  const pontos = rels.map((v, i) =>
    `<circle class="${v >= 1 ? "up" : "down"}" cx="${px(v, W)}" cy="${17 + ((i % 3) - 1) * 5}" r="4.2"/>`).join("");
  return `<svg class="strip" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${grade}
    <line class="base" x1="${px(1, W)}" x2="${px(1, W)}" y1="0" y2="${H}"/>${pontos}
    <rect class="med" x="${px(med, W) - 1.5}" y="2" width="3" height="30" rx="1"/></svg>`;
}

function nomeGrupo(k) {
  return dim === "formato" ? nomeFormato(k) : dim === "conta" ? handleDe(k) : k;
}
function subGrupo(k) {
  if (dim === "formato") return `${k} · ${E.formatos[k]?.obs ?? ""}`;
  if (dim === "conta") return E.contas.find(c => c.id === k)?.nicho ?? "";
  return "";
}
function chavesDe(l) {
  const e = l.etiquetas;
  return dim === "formato" ? [e.formato] : dim === "conta" ? [l.conta] : dim === "tema" ? e.temas : [e.podcast];
}

function linhaGrupo(g) {
  const insc = g.insc_por_mil == null ? "—" : g.insc_por_mil.toFixed(1).replace(".", ",");
  return `<div class="linha ${g.chave === selecionado ? "sel" : ""}" data-chave="${esc(g.chave)}">
    <div class="nome">${esc(nomeGrupo(g.chave))}<small>${esc(subGrupo(g.chave))}</small>${g.pista ? '<span class="selo">pista · n&lt;5</span>' : ""}</div>
    <div class="num">${g.n}</div>
    <div class="rel ${g.rel_mediana >= 1 ? "up" : "down"}">${fx(g.rel_mediana)}</div>
    <div>${strip(g.rels, g.rel_mediana)}</div>
    <div class="num">${pct(g.pct_mediana)}</div>
    <div class="num">${insc}</div></div>`;
}

function tabelaGrupos(C) {
  if (!C.grupos.length) return vazio("Nenhum Short medido ainda", "Ligue os Shorts na tela Shorts. Cada um entra aqui 7 dias depois de publicado, quando a conta tiver 3 Shorts medidos.");
  return `<div class="legenda"><span><i class="pt" style="background:var(--up)"></i>acima da base da conta</span>
    <span><i class="pt" style="background:var(--down)"></i>abaixo</span><span>│ tracejado = 1× (mediana da conta)</span>
    <span>▮ traço claro = mediana do grupo</span></div>
    <section class="grupos"><div class="linha cab"><span>${esc(dim)}</span><span class="num">n</span><span class="num">Mediana</span>
    <span>${eixo()}</span><span class="num">assist.</span><span class="num">insc/1k</span></div>${C.grupos.map(linhaGrupo).join("")}</section>`;
}

function corCelula(v) {
  return v >= 1 ? `rgba(255,122,47,${Math.min(.75, .14 + (v - 1) * .3)})` : `rgba(125,147,184,${Math.min(.6, .14 + (1 - v) * .6)})`;
}

function textoConfusao(c) {
  return c.tipo === "formato" ? `${nomeFormato(c.chave)} só rodou em ${handleDe(c.unico)}`
                              : `${handleDe(c.chave)} só postou ${nomeFormato(c.unico)}`;
}

function blocoMatriz(C) {
  const formatos = Object.keys(E.formatos).filter(f => C.matriz.some(c => c.formato === f));
  if (!formatos.length) return `<h2>Formato × conta</h2>${vazio("Matriz vazia", "Aparece quando houver Shorts medidos.")}`;
  const cel = new Map(C.matriz.map(c => [`${c.formato}|${c.conta}`, c]));
  const linhas = formatos.map(f => `<tr><td class="rot">${esc(nomeFormato(f))}</td>${E.contas.map(conta => {
    const c = cel.get(`${f}|${conta.id}`);
    return c ? `<td style="background:${corCelula(c.rel_mediana)}"><span class="v">${fx(c.rel_mediana)}</span><span class="n">n${c.n}</span></td>`
             : `<td class="vazia">falta</td>`;
  }).join("")}</tr>`).join("");
  const nota = C.confusoes.length ? `<div class="nota"><b>Confusão</b> — o número mistura formato com conta:
    <ul>${C.confusoes.map(c => `<li>${esc(textoConfusao(c))}</li>`).join("")}</ul>Postar o mesmo formato em outra conta separa os dois.</div>` : "";
  return `<h2>Formato × conta</h2><p class="sub">Mediana relativa por célula · n no canto · hachura = teste que falta</p>
    <table class="matriz"><tr><th></th>${E.contas.map(c => `<th>${esc(c.handle)}</th>`).join("")}</tr>${linhas}</table>${nota}`;
}

function cartaoShort(l, matura = false) {
  const up = l.rel != null && l.rel >= 1;
  return `<a class="thumb ${matura ? "matura" : up ? "up" : ""}" href="https://youtube.com/shorts/${l.video_id}" target="_blank" rel="noopener">
    <img src="${thumb(l.video_id)}" alt="" loading="lazy"><div class="t">${esc(l.titulo)}</div>
    <div><div class="x ${up ? "up" : "down"}">${matura ? "" : fx(l.rel)}</div>
    <div class="c">${matura ? "maturando · " : ""}${esc(handleDe(l.conta))}</div></div></a>`;
}

function blocoGrupo(C) {
  const g = C.grupos.find(x => x.chave === selecionado);
  if (!g) return "";
  const porId = new Map(S.map(l => [l.video_id, l]));
  const medidos = g.video_ids.map(id => porId.get(id)).filter(Boolean).sort((a, b) => b.rel - a.rel);
  const maturando = S.filter(l => l.etiquetas && l.medida.estado === "maturando" && chavesDe(l).includes(g.chave));
  return `<h2>${esc(nomeGrupo(g.chave))}</h2>
    <p class="sub">${medidos.length} medidos · ${maturando.length} em maturação · ordenados pelo relativo à conta</p>
    <div class="shorts">${medidos.map(l => cartaoShort(l)).join("")}${maturando.map(l => cartaoShort(l, true)).join("")}</div>`;
}

async function telaComparar() {
  const C = await api(`/api/comparar?dim=${dim}`);
  if (!C.grupos.some(g => g.chave === selecionado)) selecionado = C.grupos[0]?.chave ?? null;
  const aviso = dim === "tema" ? " · um Short entra em todos os seus temas: os grupos não somam o total" : "";
  $("#tela").innerHTML = `<header><div><h1>O que está funcionando <em>— ${TITULOS[dim]}</em></h1>
    <p class="sub">Views aos 7 dias ÷ mediana da própria conta · ${C.medidos} Shorts medidos · ${C.maturando} em maturação${aviso}</p></div>
    <div class="seg">${Object.keys(TITULOS).map(d => `<button data-dim="${d}" class="${d === dim ? "ativo" : ""}">${d[0].toUpperCase() + d.slice(1)}</button>`).join("")}</div></header>
    ${tabelaGrupos(C)}
    <div class="baixo"><div class="card">${blocoMatriz(C)}</div><div class="card">${blocoGrupo(C)}</div></div>`;
  $$(".seg button").forEach(b => { b.onclick = () => { dim = b.dataset.dim; selecionado = null; desenhar(); }; });
  $$(".linha[data-chave]").forEach(el => { el.onclick = () => { selecionado = el.dataset.chave; desenhar(); }; });
}
TELAS.comparar = telaComparar;
```

- [ ] **Step 5: Criar `web/static/js/inicio.js`**

```js
"use strict";
// Roteador por hash e acompanhamento da coleta. Carregado por último.
async function desenhar() {
  const nome = TELAS[location.hash.slice(1)] ? location.hash.slice(1) : "comparar";
  $$("nav a").forEach(a => a.classList.toggle("ativo", a.dataset.tela === nome));
  try {
    await TELAS[nome]();
  } catch (e) {
    avisar(e.message);
  }
}

async function acompanhar() {
  await carregar();
  if (E.rodando) setTimeout(acompanhar, 3000);
  else desenhar();
}

async function atualizar(conta) {
  try {
    await post("/api/atualizar", { conta: conta ?? null });
    await acompanhar();
  } catch (e) {
    avisar(e.message);
  }
}

window.addEventListener("hashchange", desenhar);
$("#atualizar-todas").onclick = () => atualizar(null);
carregar().then(() => (E.rodando ? acompanhar() : desenhar())).catch(e => avisar(e.message));
```

- [ ] **Step 6: Check e commit**

Run: o comando de check (não cobre JS; garante que nada do Python quebrou).

```bash
git add web/static
git commit -m "feat: página do painel com a tela Comparar"
```

---

### Task 14: Tela Shorts e ligação

**Files:**
- Create: `web/static/js/shorts.js`
- Modify: `web/static/index.html` (incluir o script), `web/static/painel.css` (acrescentar estilos)

- [ ] **Step 1: Em `index.html`, antes de `<script src="js/inicio.js"></script>`:**

```html
<script src="js/shorts.js"></script>
```

- [ ] **Step 2: Acrescentar ao final de `web/static/painel.css`** (antes do bloco `@media`):

```css
/* tela Shorts */
h3.secao { font: 500 11px var(--mono); color: var(--faint); text-transform: uppercase; letter-spacing: .08em; margin: 24px 0 10px; }
h3.secao span { color: var(--up); margin-left: 6px; }
.linha-s { display: grid; grid-template-columns: 36px minmax(0, 1fr) 120px 48px 86px 70px 60px 190px; gap: 14px;
  align-items: center; padding: 10px 16px; border-top: 1px solid var(--line-soft); }
.linha-s:first-child { border-top: 0; }
.linha-s.matura { opacity: .55; }
.linha-s .nome { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
img.mini { width: 36px; height: 64px; object-fit: cover; border-radius: 5px; background: var(--raised); }
.chips { display: flex; flex-wrap: wrap; gap: 4px; background: none; border: 0; padding: 0; cursor: pointer; text-align: left; }
.chip { font: 11px var(--mono); padding: 2px 7px; border-radius: 99px; background: var(--raised); color: var(--muted); }
.chip.f { color: var(--text); border: 1px solid var(--line); }

/* gaveta de ligação */
.fundo { position: fixed; inset: 0; background: rgba(0,0,0,.55); z-index: 20; }
.gaveta { position: fixed; top: 0; right: 0; bottom: 0; width: min(440px, 100%); background: var(--surface);
  border-left: 1px solid var(--line); padding: 26px 24px; overflow-y: auto; z-index: 21; display: grid; gap: 14px; align-content: start; }
.gaveta h2 { font: 400 28px var(--serif); }
.gaveta label { display: grid; gap: 5px; font-size: 12px; color: var(--muted); }
.gaveta input, .gaveta select { background: var(--bg); border: 1px solid var(--line); border-radius: 7px; padding: 8px 10px; }
.gaveta input:focus, .gaveta select:focus { outline: 1px solid var(--up); border-color: var(--up); }
.temas { display: flex; flex-wrap: wrap; gap: 6px; }
.temas label { display: inline-flex; gap: 6px; align-items: center; padding: 5px 9px; border: 1px solid var(--line);
  border-radius: 99px; color: var(--text); cursor: pointer; }
.temas input { accent-color: var(--up); }
.acoes { display: flex; gap: 8px; justify-content: flex-end; margin-top: 6px; }
@media (max-width: 900px) {
  .linha-s { grid-template-columns: 36px minmax(0, 1fr) 64px; }
  .linha-s > :nth-child(3), .linha-s > :nth-child(4), .linha-s > :nth-child(5),
  .linha-s > :nth-child(7), .linha-s > :nth-child(8) { display: none; }
  .card { overflow-x: auto; }
}
```

- [ ] **Step 3: Criar `web/static/js/shorts.js`**

```js
"use strict";
// Tela Shorts: pendências de ligação no topo, ligados embaixo; gaveta para ligar Short → corte.

function idade(l) {
  return Math.floor((Date.now() - new Date(l.publicado_em + "T00:00")) / 864e5) + "d";
}

function views7d(l) {
  const m = l.medida;
  if (m.estado === "maturando") return "maturando";
  return mil(m.views_7d) + (m.estado === "estimado" ? " ≈" : "");
}

function chipsEtiquetas(l) {
  const e = l.etiquetas;
  return `<button class="chips" data-ligar="${l.video_id}" title="religar"><span class="chip f">${esc(e.formato)}</span>${
    e.temas.map(t => `<span class="chip">${esc(t)}</span>`).join("")}<span class="chip">${esc(e.podcast)}</span></button>`;
}

function tabelaShorts(ls) {
  return `<section class="grupos">
    <div class="linha-s cab"><span></span><span>Título</span><span>Conta</span><span class="num">Idade</span>
      <span class="num">Views 7d</span><span class="num">Relativo</span><span class="num">Assist.</span><span>Etiquetas</span></div>
    ${ls.map(l => `<div class="linha-s ${l.medida.estado === "maturando" ? "matura" : ""}">
      <img class="mini" src="${thumb(l.video_id)}" alt="" loading="lazy">
      <div class="nome" title="${esc(l.titulo)}">${esc(l.titulo)}</div>
      <div class="muted">${esc(handleDe(l.conta))}</div>
      <div class="num">${idade(l)}</div>
      <div class="num" title="${l.medida.estado}">${views7d(l)}</div>
      <div class="num ${l.rel == null ? "" : l.rel >= 1 ? "up" : "down"}">${fx(l.rel)}</div>
      <div class="num">${pct(l.pct_media)}</div>
      <div>${l.etiquetas ? chipsEtiquetas(l) : `<button class="botao" data-ligar="${l.video_id}">Ligar</button>`}</div>
    </div>`).join("")}</section>`;
}

async function telaShorts() {
  await carregar();
  const sem = S.filter(l => !l.etiquetas), lig = S.filter(l => l.etiquetas);
  $("#tela").innerHTML = `<header><div><h1>Shorts <em>— ${S.length} nos retratos</em></h1>
    <p class="sub">Ligue cada Short ao corte que o gerou: só Short ligado entra na comparação.</p></div>
    <button class="botao" id="ligar-link">Ligar por link</button></header>
    ${S.length ? "" : vazio("Nenhum Short ainda", "Adicione uma conta e clique em Atualizar: os Shorts dela aparecem aqui.")}
    ${sem.length ? `<h3 class="secao">Sem ligação<span>${sem.length}</span></h3>${tabelaShorts(sem)}` : ""}
    ${lig.length ? `<h3 class="secao">Ligados<span>${lig.length}</span></h3>${tabelaShorts(lig)}` : ""}`;
  $$("[data-ligar]").forEach(b => { b.onclick = () => abrirLigar(b.dataset.ligar); });
  $("#ligar-link").onclick = () => abrirLigar(null);
}

function opcoesCorte(sugeridos, todos) {
  const vistos = new Set(sugeridos.map(c => c.caminho));
  const resto = todos.filter(c => !vistos.has(c.caminho));
  const opt = c => `<option value="${esc(c.caminho)}">${esc(c.caminho)}</option>`;
  return (sugeridos.length ? `<optgroup label="Sugeridos pelo título">${sugeridos.map(opt).join("")}</optgroup>` : "")
    + `<optgroup label="Todos">${resto.map(opt).join("")}</optgroup>`;
}

function formGaveta(l, sugeridos, todos) {
  const e = l?.etiquetas;
  return `<div class="fundo"></div><form class="gaveta"><h2>Ligar Short</h2>
    ${l ? `<p class="sub">${esc(l.titulo)}</p>` : ""}
    <label>Link do Short<input name="link" required value="${l ? `https://youtube.com/shorts/${l.video_id}` : ""}"></label>
    <label>Conta<select name="conta">${E.contas.map(c => `<option value="${c.id}" ${l?.conta === c.id ? "selected" : ""}>${esc(c.handle)}</option>`).join("")}</select></label>
    <label>Corte<select name="corte" required>${opcoesCorte(sugeridos, todos)}</select></label>
    <label>Formato<select name="formato">${Object.entries(E.formatos).map(([id, f]) => `<option value="${id}">${id} · ${esc(f.nome)}</option>`).join("")}</select></label>
    <div><label>Temas</label><div class="temas">${E.temas.map(t => `<label><input type="checkbox" name="temas" value="${esc(t)}" ${e?.temas.includes(t) ? "checked" : ""}>${esc(t)}</label>`).join("")}</div></div>
    <label>Podcast<input name="podcast" required list="podcasts" value="${esc(e?.podcast ?? "")}"><datalist id="podcasts">${E.podcasts.map(p => `<option value="${esc(p)}">`).join("")}</datalist></label>
    <div class="acoes"><button type="button" class="botao" id="cancelar">Cancelar</button><button class="botao primario">Ligar</button></div></form>`;
}

function preencherDoCorte(form, todos, etiquetas) {
  const c = todos.find(x => x.caminho === form.corte.value);
  if (etiquetas) { form.formato.value = etiquetas.formato; return; }
  if (c?.formato) form.formato.value = c.formato;
  if (c?.podcast && !form.podcast.value) form.podcast.value = c.podcast;
}

async function abrirLigar(vid) {
  const l = vid ? S.find(x => x.video_id === vid) : null;
  const [sugeridos, todos] = await Promise.all([vid ? api(`/api/sugestoes/${vid}`) : [], api("/api/cortes")]);
  const camada = $("#camada");
  camada.innerHTML = formGaveta(l, sugeridos, todos);
  const form = $("form", camada);
  if (l?.corte) form.corte.value = l.corte;
  preencherDoCorte(form, todos, l?.etiquetas);
  form.corte.onchange = () => preencherDoCorte(form, todos, null);
  const fechar = () => { camada.innerHTML = ""; };
  $(".fundo", camada).onclick = fechar;
  $("#cancelar").onclick = fechar;
  form.onsubmit = async ev => {
    ev.preventDefault();
    const corpo = { link: form.link.value.trim(), conta: form.conta.value, corte: form.corte.value,
      formato: form.formato.value, podcast: form.podcast.value,
      temas: $$("input[name=temas]:checked", form).map(i => i.value) };
    try { await post("/api/ligar", corpo); fechar(); desenhar(); } catch (e) { avisar(e.message); }
  };
}
TELAS.shorts = telaShorts;
```

- [ ] **Step 4: Commit**

```bash
git add web/static
git commit -m "feat: tela Shorts com ligação a corte"
```

---

### Task 15: Tela Contas

**Files:**
- Create: `web/static/js/contas.js`
- Modify: `web/static/index.html`, `web/static/painel.css`

- [ ] **Step 1: Em `index.html`, antes de `<script src="js/inicio.js"></script>`:**

```html
<script src="js/contas.js"></script>
```

- [ ] **Step 2: Acrescentar ao final de `web/static/painel.css`** (antes do bloco `@media`):

```css
/* tela Contas */
.cartoes { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.conta-card .topo { display: flex; justify-content: space-between; align-items: start; }
.conta-card dl { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 18px 0; }
.conta-card dt { font: 500 10px var(--mono); color: var(--faint); text-transform: uppercase; letter-spacing: .06em; }
.conta-card dd { font: 400 22px/1.2 var(--serif); margin-top: 3px; }
.conta-card .erro { font-size: 12px; color: #d8cfb8; border-left: 2px solid var(--warn); padding: 6px 10px;
  background: rgba(232,193,90,.06); border-radius: 6px; margin-bottom: 12px; word-break: break-word; }
.conta-card .acoes { justify-content: flex-start; margin: 0; }
form.nova { display: grid; gap: 10px; }
form.nova label { display: grid; gap: 4px; font-size: 12px; color: var(--muted); }
form.nova input, form.nova select { background: var(--bg); border: 1px solid var(--line); border-radius: 7px; padding: 7px 10px; }
```

- [ ] **Step 3: Criar `web/static/js/contas.js`**

```js
"use strict";
// Tela Contas: estado de cada conta, atualizar, login manual e nova conta.

function cartaoConta(c) {
  const falhou = c.coleta && !c.coleta.ok;
  const medidos = S.filter(l => l.conta === c.id && l.medida.views_7d != null).map(l => l.medida.views_7d);
  const base = medidos.length >= 3 ? mil(mediana(medidos)) : `sem base · ${medidos.length}/3`;
  return `<div class="card conta-card">
    <div class="topo"><div><h2>${esc(c.nome)}</h2><p class="sub">${esc(c.handle)} · ${esc(c.nicho)}</p></div>
      <i class="estado ${falhou || !c.ultimo_retrato ? "vencido" : ""}"></i></div>
    <dl><div><dt>Último retrato</dt><dd>${c.ultimo_retrato ? dataHora(c.ultimo_retrato) : "nunca"}</dd></div>
      <div><dt>Ligados</dt><dd>${c.ligados}</dd></div>
      <div><dt>Mediana 7d</dt><dd>${base}</dd></div></dl>
    ${falhou ? `<p class="erro">${esc(c.coleta.mensagem)}</p>` : ""}
    <div class="acoes"><button class="botao" data-atualizar="${c.id}" ${E.rodando ? "disabled" : ""}>↻ Atualizar</button>
      ${falhou || !c.ultimo_retrato ? `<button class="botao" data-login="${c.id}">Fazer login</button>` : ""}</div></div>`;
}

function cartaoNova() {
  const campo = (nome, rotulo, dica) => `<label>${rotulo}<input name="${nome}" required placeholder="${dica}"></label>`;
  return `<div class="card"><h2>Nova conta</h2><p class="sub">Depois de criar, clique em Fazer login e entre na janela do Chrome.</p>
    <form class="nova">${campo("id", "Id (a-z, 0-9, -)", "grana")}${campo("nome", "Nome", "Grana Cortes")}
    ${campo("handle", "Handle", "@grana.cortes")}
    <label>Nicho<select name="nicho">${E.nichos.map(n => `<option>${esc(n)}</option>`).join("")}</select></label>
    ${campo("perfil_studio", "Perfil de login", "grana")}
    <div class="acoes"><button class="botao primario">Criar conta</button></div></form></div>`;
}

async function telaContas() {
  await carregar();
  $("#tela").innerHTML = `<header><div><h1>Contas <em>— ${E.contas.length}</em></h1>
    <p class="sub">Um perfil de login por conta. O app nunca vê senha: o login é feito na janela do Chrome.</p></div></header>
    <div class="cartoes">${E.contas.map(cartaoConta).join("")}${cartaoNova()}</div>`;
  $$("[data-atualizar]").forEach(b => { b.onclick = () => atualizar(b.dataset.atualizar); });
  $$("[data-login]").forEach(b => {
    b.onclick = async () => {
      try { await post(`/api/login/${b.dataset.login}`); avisar("Janela do Chrome aberta: entre na conta e feche a janela quando o Studio abrir."); }
      catch (e) { avisar(e.message); }
    };
  });
  $("form.nova").onsubmit = async ev => {
    ev.preventDefault();
    const corpo = Object.fromEntries(new FormData(ev.target));
    try { await post("/api/contas", corpo); desenhar(); } catch (e) { avisar(e.message); }
  };
}
TELAS.contas = telaContas;
```

- [ ] **Step 4: Commit**

```bash
git add web/static
git commit -m "feat: tela Contas com atualização, login e nova conta"
```

---

### Task 16: Verificação ponta a ponta com dados de demonstração

Dados fictícios numa pasta de rascunho (fora do repositório), para ver as três telas cheias
sem depender de contas reais.

- [ ] **Step 1: Criar a pasta de demonstração** (no diretório de rascunho da sessão; aqui `$DEMO`)

```bash
DEMO="<scratchpad>/demo-painel"
mkdir -p "$DEMO/contas" "$DEMO/testes"
cp -r nichos "$DEMO/nichos"
cp contas/formatos.yaml "$DEMO/contas/"
for p in f1-falante-95-carteiras f3-motion-400mil f4-broll-liquidez f6-hormozi-netflix f7-conversa-comediante; do mkdir -p "$DEMO/testes/$p"; done
# skill falsa: falha na hora, para testar o caminho de erro sem abrir o Chrome nem esperar login
mkdir -p "$DEMO/skill/src" "$DEMO/skill/node_modules"
echo 'console.error("perfil sem login (demo)"); process.exit(1);' > "$DEMO/skill/src/cli.mjs"
```

- [ ] **Step 2: Gerar contas, retratos e ligações fictícios**

```bash
.venv/Scripts/python - "$DEMO" <<'EOF'
import random, sys
from datetime import date, datetime, timedelta
from pathlib import Path
from cortes.painel.dados import carregar_vocabulario
from cortes.painel.publicados import Etiquetas, Publicado, gravar_publicados
from cortes.painel.retratos import Retrato, VideoRetrato, salvar_retrato

demo = Path(sys.argv[1]); random.seed(7)
(demo / "contas" / "contas.yaml").write_text(
    "contas:\n"
    '  - {id: grana, nome: Grana Cortes, handle: "@grana.cortes", nicho: financas, perfil_studio: grana}\n'
    '  - {id: bolso, nome: Bolso Clips, handle: "@bolso.clips", nicho: financas, perfil_studio: bolso}\n',
    encoding="utf-8")
voc = carregar_vocabulario(demo)
plano = {"grana": ["f7", "f7", "f7", "f4", "f4", "f4", "f1", "f3"], "bolso": ["f6", "f6", "f6", "f1", "f3", "f3", "f7"]}
pasta = {"f1": "f1-falante-95-carteiras", "f3": "f3-motion-400mil", "f4": "f4-broll-liquidez",
         "f6": "f6-hormozi-netflix", "f7": "f7-conversa-comediante"}
efeito = {"f7": 2.2, "f3": 1.4, "f4": 1.0, "f1": 0.7, "f6": 0.5}
temas = sorted(voc.temas); hoje = date(2026, 10, 30); pubs = []
for conta, formatos in plano.items():
    videos = []
    for i, f in enumerate(formatos):
        vid = f"{conta[:3]}{i:02d}{f}xxxx"[:11]
        pub = hoje - timedelta(days=4 + 3 * i)
        videos.append((vid, f, pub, efeito[f] * random.uniform(0.5, 1.6) * 800))
        pubs.append(Publicado(vid, conta, pub, f"testes/{pasta[f]}",
                              Etiquetas(f, tuple(random.sample(temas, 1)), "PrimoCast")))
    videos.append((f"{conta[:3]}semlig01", "f1", hoje - timedelta(days=12), 600.0))
    for dia in range(0, 31, 2):
        quando = date(2026, 10, 1) + timedelta(days=dia)
        vs = tuple(VideoRetrato(v, f"Short {v} sobre dinheiro", p, 35.0,
                                int(total * min(1, (quando - p).days / 9)), 70.0, 25.0, int(total / 300))
                   for v, _, p, total in videos if quando >= p)
        if vs:
            salvar_retrato(demo / "contas" / "retratos", Retrato(conta, datetime.combine(quando, datetime.min.time()), vs))
gravar_publicados(demo / "contas" / "publicados.jsonl", pubs)   # os '...semlig01' ficam sem ligação
print("ok", demo)
EOF
```

Expected: `ok <caminho>`

- [ ] **Step 3: Subir o painel apontando para a demonstração**

Run (em segundo plano): `.venv/Scripts/cortes painel --raiz "$DEMO" --skill "$DEMO/skill"`
Expected: `painel em http://127.0.0.1:8765`

- [ ] **Step 4: Conferir no navegador (painel do app) em 1440 px e em 375 px**

- `#comparar`: grupos ordenados com f7 no topo, strip plots alinhados ao eixo, selo "pista" nos
  grupos com n < 5, matriz com células "falta" hachuradas e aviso de confusão (f4 só em @grana),
  miniaturas do grupo ao clicar numa linha; trocar para Tema mostra o aviso de multivalor.
- `#shorts`: "Sem ligação" no topo com botão Ligar; a gaveta abre com o corte sugerido e o
  formato pré-preenchido; ligar um Short o move para "Ligados" e o contador do trilho cai.
- `#contas`: dois cartões; "Atualizar todas" termina com os dois cartões amarelos e a mensagem
  "perfil sem login (demo)" (a skill falsa falha), com "Fazer login" visível; "Nova conta" com
  nicho válido aparece na lista; nicho de uma conta com menos de 3 medidos mostra "sem base".
- Console do navegador sem erros.
- Em 375 px: trilho some, tabela mostra nome e mediana, sem rolagem horizontal.

Qualquer diferença visual em relação ao mockup aprovado: corrigir no CSS/JS e repetir o passo.

- [ ] **Step 5: Check final e commit de ajustes**

Run: o comando de check completo. Expected: tudo passa.

```bash
git add web/static
git commit -m "fix: ajustes visuais da verificação ponta a ponta"
```

(Só se houve ajuste.)
```
