# f4 B-roll automático (substitui o f9 Ilustrado)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Quando a pessoa fala de uma coisa concreta ou de um acontecimento, o Short corta para um clipe de 2 a 3 s que mostra aquilo **em tela cheia** e volta para a pessoa com corte seco.
- **Fonte principal:** vídeo do YouTube.
- **Sem vídeo que passe na conferência:** foto do DuckDuckGo, mas só quando a deixa é uma coisa (tipo "literal"), nunca um acontecimento.
- **Formato:** é o **f4 B-roll** da spec, plano D, agora automático. O f9 Ilustrado (cartão de foto) **deixa de existir**.

**Decisões (Davi, 2026-10-03):**
- Vídeo do YouTube, com foto quando não achar.
- Tela cheia por 2–3 s, corte seco.
- f9 e f4 viram um formato só, o f4.

**Decisões tomadas no plano (registrar na spec):**
- **Deixas com `tipo`:** `"literal"` (coisa citada: Vans, camisa do Corinthians) ou `"acontecimento"` (cena: "a pandemia" mostra rua vazia; "jato particular decolando"). A ideia vem da spec §6. Acontecimento não tem foto de reserva: sem vídeo, a deixa fica "sem visual", visível.
- **Ritmo:**
  - nada no primeiro 1 s, que é o gancho com o rosto;
  - cada clipe dura de 1,5 a 3,0 s;
  - pelo menos **1,5 s de rosto** entre o fim de um clipe e o início do próximo;
  - **B-roll ≤ 60% da duração** (spec §6, R2 pista).
  - Aplicado no código, não só no prompt, e testado.
- **Sem efeito:** nem o Ken Burns do protótipo (zoom de 1,08 para 1), nem flash, nem zoom. O Davi pediu tirar zoom e flash.
- **Enquadramento do vídeo 16:9 na tela 9:16:**
  - **vídeo:** preenche a tela com corte central (cover, como o `#box-cheio` do protótipo);
  - **foto:** a imagem inteira (contain) sobre ela mesma desfocada e escurecida, montada pelo ffmpeg num 1080×1920 (mesma ideia do f8). Assim o produto não é cortado.
- **YouTube:**
  - `yt-dlp ytsearch` (já é dependência, `ingestao`);
  - candidatos de 20 s a 20 min;
  - até 3 por deixa;
  - baixa só um trecho de 3 s (`--download-sections`) a partir de 25% da duração, como `testes/comum/buscar_broll.py`, em até 1080p e sem áudio;
  - `fonte_url`, `canal`, `titulo`, `licenca: desconhecida (YouTube)`, `risco: alto`.
- **HTTP 429 e bloqueio do YouTube:** a spec §8 avisa que o IP já foi bloqueado uma vez.
  - Erro 429 ou bloqueio vira falha **transitória** da deixa; a foto pode cobrir se for literal. A falha nunca é repetida em laço.
  - Buscas e downloads de vídeo são **em série**, sem paralelo no YouTube, com no máximo 3 candidatos por deixa.
- **Conferência:**
  - continua **uma chamada por corte**, com folhas de até 6 deixas;
  - cada linha traz os candidatos daquela deixa: vídeos marcados `V`, cada um num tile com 3 quadros (início, meio, fim do trecho), e fotos marcadas `F`;
  - o prompt manda **preferir vídeo** quando ele mostra a coisa;
  - foto só para literal.
- **O que se reaproveita do f9:** prompt e regras das deixas, busca e download seguro de foto, folhas, conferência com Read preso à pasta, cache com chave (início, fim, hash do texto), transitório, "vazio", "Refazer ilustração" e rotas do editor.
  - Renomear "ilustração" para "B-roll" na tela; os nomes internos podem ficar `ilustracao*` se renomear custar caro (decida e diga).
  - O cache sobe de formato (cache antigo é refeito).
- **f9:**
  - sai de `montagem.FORMATOS` e de `contas/formatos.yaml`;
  - `render/formatos/ilustrado.tpl` vira `broll.tpl` (f4);
  - um `corte.json` existente com `formato: "f9"` dá erro claro na leitura ou no render ("o formato f9 virou o f4 B-roll; renderize de novo em f4"), sem conversão silenciosa;
  - `f4` em `formatos.yaml` passa a `no_app: "plano B"`, com `descricao` atualizada.

**Check (worktree `../Cortes-formato`):** `PY="../Cortes/.venv/Scripts/python"`, depois `PYTHONPATH=src $PY -m ruff check src tests && PYTHONPATH=src $PY -m mypy src && PYTHONPATH=src $PY -m pytest -q`.

---

### Task 1: Deixas com tipo e ritmo do B-roll

- [ ] **Schema e prompt:** `ilustracao.py` (`SCHEMA_DEIXAS`, prompt) ganha `tipo: "literal" | "acontecimento"`. O prompt explica os dois tipos com exemplos e mantém a regra "cada coisa uma vez, sem retomada genérica". A busca de vídeo de acontecimento pode ser em inglês quando render melhor; diga no prompt para usar o termo que mais acharia vídeo.
- [ ] **Ritmo no código** (`deixas_do_corte`): 1,5–3,0 s por clipe, gancho de 1 s, ≥ 1,5 s de rosto entre clipes e soma ≤ 60% do `dur`. Quando passar de 60%, descarta as últimas e não corta as do meio. Testes.
- [ ] Commit `feat: deixas do B-roll com tipo (literal/acontecimento) e ritmo de corte`.

### Task 2: Busca e trecho de vídeo do YouTube

- [ ] **`render/broll_video.py`** (novo):
  - `buscar_videos(busca, n, rodar)`: `yt-dlp --flat-playlist --print ... ytsearch8:<busca>`, filtra 20 s a 20 min e devolve `VideoCandidato(id, dur, canal, titulo)`;
  - `args_trecho(...)` e `baixar_trecho(...)`: yt-dlp com `--download-sections`, depois ffmpeg para 1080×1920 em cover com corte central, sem áudio, `.parcial`, prazo de 60 s, com o executor de prazo de `processo`;
  - `quadros_args(...)`: 3 quadros do trecho para a folha;
  - 429 ou bloqueio detectado na saída do yt-dlp viram `ErroBusca` transitório.
  - Argumentos sempre em lista, sem shell; o id do vídeo é validado (`^[A-Za-z0-9_-]{11}$`).
- [ ] **Foto de reserva em tela cheia:** função pura `args_foto_cheia` (contain sobre a mesma imagem desfocada, 1080×1920) aplicada à foto escolhida.
- [ ] **Testes com falsos:** filtro de duração, id inválido recusado, 429 transitório, args do ffmpeg e do yt-dlp.
- [ ] **Uma conferência real rápida no scratchpad**, não versionada: `buscar_videos("tênis Vans Old Skool", 3)` e um `baixar_trecho` real. Olhe os 3 quadros.
- [ ] Commit `feat: busca e trecho de vídeo do YouTube para o B-roll`.

### Task 3: Etapa, conferência mista, template f4 e saída do f9

- [ ] **Etapa** (`ilustracao_etapa.py`, ou um `broll_etapa.py` que a substitua):
  - para cada deixa, primeiro os vídeos (em série) e, se literal, também as fotos;
  - a folha mista sai com tiles `V` (3 quadros) e `F`;
  - a conferência escolhe um candidato por deixa, preferindo vídeo, ou nenhum;
  - o candidato escolhido vira `assets/broll-<k>.mp4` (vídeo) ou `assets/broll-<k>.jpg` (foto em tela cheia).
  - Cache, transitório, vazio e "Refazer" continuam funcionando, com testes adaptados.
- [ ] **`render/formatos/broll.tpl` (f4):**
  - base no `conversa.tpl` atual, sem efeito;
  - cada deixa vira um elemento em tela cheia (`<video class="clip" muted playsinline data-start data-duration data-media-start="0" data-track-index="15">` ou `<img>`) que aparece e some **seco** (sem opacidade gradual);
  - a legenda continua por cima;
  - `montagem.FORMATOS` troca f9 por f4 (`_TEMPLATES["f4"] = "broll"`) e `valores` gera `BROLL`.
- [ ] **f9 removido:** template `ilustrado.tpl` apagado, `formatos.yaml` atualizado, `corte.json` em f9 dá erro claro (teste), e testes, conftest e rota da prévia ajustados (a prévia passa a servir `assets/broll-<k>.(mp4|jpg)`, em lista fechada por regex).
- [ ] **Editor:** a seção vira "B-roll", com o tipo (vídeo/foto/sem visual) e a miniatura (um quadro do vídeo ou a foto) de cada deixa, e o botão "Refazer B-roll".
- [ ] Commits coesos (`feat:`).

### Task 4: Render real e spec

- [ ] **Render real em f4** dos cortes "Bota boa por 250, não 600" e "Camisa de 700 reais, sério?" do episódio `wxCto9WSZcI`, numa raiz temporária com hardlinks e nunca em `../Cortes/episodios`, adaptando o teste lento do f9.
  - Copie os MP4, as folhas e o JSON da ilustração para o scratchpad indicado.
  - Olhe as folhas e os quadros: o vídeo mostra a coisa? o ritmo deixa o rosto aparecer? algum 429?
  - Corrija defeitos com teste; anote o que for gosto.
- [ ] **Spec:** a §11 (f9) vira "f4 B-roll automático", com as decisões acima; a §6 (B-roll, plano D) passa a apontar para ela; atualizar §3/§4.
- [ ] Commit `test/docs: B-roll real e spec`.
