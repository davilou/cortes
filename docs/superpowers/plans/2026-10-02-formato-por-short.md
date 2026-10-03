# Formato por Short — sem render automático, f5/f6/f8 no app

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Nada renderiza sem pedido. Cada Short é renderizado no template que Davi escolher, e os formatos que só dependem de template (f6 Hormozi, f8 Desfoque, f5 Gameplay) entram no app junto de f7 e f1.

**Decisões (Davi, 2026-10-02):**
- **Sem render automático.** Sai o "N melhores" e o campo "Shorts" da entrada; o campo de formato da entrada vira **formato padrão**, só o valor pré-marcado no seletor.
- **"Renderizar" com seletor de formato por candidato**, e **"Cancelar"** para Short na fila que ainda não começou.
- **Formatos ligados agora:** f6, f8 e f5. O f4 (B-roll) e o f3 (Motion) seguem nos planos D e E, porque precisam de material que o app ainda não produz: clipes buscados e painéis gerados.
- **Sem flash e sem zoom em nenhum template**, valendo também para os novos (decisão de 2026-10-02 sobre f7 e f1).

**Spec:** `docs/superpowers/specs/2026-10-02-producao-design.md`. Atualizar §2, §3, §4.4 e §5 na Task 4.

**Check (worktree `../Cortes-formato`):** `PY="../Cortes/.venv/Scripts/python"`, depois `PYTHONPATH=src $PY -m ruff check src tests && PYTHONPATH=src $PY -m mypy src && PYTHONPATH=src $PY -m pytest -q`.

## Fatos verificados

- **Onde o render automático nasce:** `producao/render.py:35` chama `planejar(pasta, e.formato, e.n_shorts, candidatos)` uma vez por episódio, com o marcador `cortes/planejado.json`. As funções `corte.planejar`, `corte.melhores` e `PLANEJADO` só servem para isso.
- **Por onde passa o `n_shorts`:**
  - `estado.EstadoEpisodio.n_shorts`, `estado.novo(..., n_shorts, formato, agora)` e `estado._n_shorts`;
  - `rotas.NovoEpisodio.n_shorts`, `N_SHORTS_MAX` e a validação;
  - `web/static/js/episodios.js:34,40`;
  - muitos testes, que chamam `novo(id, url, nicho, 5, "f7", AGORA)`.
- **Templates dos protótipos** (`testes/comum/formatos/`):
  - `hormozi.tpl`: `{{DUR}} {{LEGENDAS}} {{TRILHA_CHEIO}} {{TRILHA}}`, com a legenda palavra a palavra (`<i data-t="…">` por palavra; ver `testes/comum/corte.py:legenda_html(por_palavra=True)`).
  - `desfoque.tpl`: `{{DUR}} {{LEGENDAS}} {{TITULO}} {{TRILHA}}`, mais `assets/fundo.mp4`, que é o trecho a 540×960, desfocado (`testes/f8-desfoque-20-vezes/assets/fundo.mp4`, 540×960).
  - `gameplay.tpl`: `{{DUR}} {{LEGENDAS}} {{TRILHA_METADE}} {{TRILHA}} {{CORTES}}`, mais `assets/gameplay.mp4` em 1708×960. `#q-meio` está fixo em 1920×1080, que só vale para fonte de 1080p.
    - No protótipo, `TRILHA_METADE = corte.trilha(d, 1.0, (1080, 960), (540, 380))`: escala 1,0, janela 1080×960, alvo (540, 380).
- **Gameplay de origem:** `testes/_fontes/gameplay.mp4`, 1920×1080, 30 s ("Orbital No Copyright"). Um Short pode durar mais que isso.
- **Tela:** `contas/formatos.yaml` tem `no_app` por formato. Os valores aceitos são `NO_APP_VALIDOS = ("plano B", "plano D", "plano E", "fora")`, e f5, f6 e f8 hoje estão "fora".

---

### Task 1: Sem render automático, cancelar e formato padrão (backend)

- [ ] **Render só do que foi pedido:** `producao/render.rodar_render` não planeja mais nada; processa só os cortes `na_fila`/`renderizando`. Remova `planejar`, `melhores` e `PLANEJADO` de `render/corte.py`, junto com os testes deles. Um `cortes/planejado.json` antigo no disco passa a ser ignorado; diga isso no docstring.
- [ ] **`n_shorts` sai do estado:**
  - `EstadoEpisodio` e `novo` perdem o campo;
  - `ler` ignora a chave quando ela existe em `estado.json` antigo (migração explícita, comentada);
  - `NovoEpisodio` perde o campo, e saem `N_SHORTS_MAX` e a validação dele;
  - os testes são ajustados.
- [ ] **`POST /api/episodios/{id}/cortes/{indice}/cancelar`** (em `rotas_cortes.py`, sob a trava `escrita`). Só vale para corte `na_fila`; em qualquer outro status, `ErroProducao("só dá para cancelar um Short que está na fila e ainda não começou")`. Função pura `cancelar(c) -> Corte | None` em `render/corte.py`, com teste:
  - `versao > 0`: volta a `pronto` (a versão anterior continua valendo);
  - `versao == 0` sem edições e sem `alterado`: devolve `None`, e a rota apaga a pasta do corte (o candidato volta a ter "Renderizar");
  - `versao == 0` com edições: `status="erro"`, `erro="render cancelado"` (as edições ficam).
  - Corrida conhecida, a registrar no docstring da rota: a fila pode pegar o corte entre a leitura e o cancelamento; nesse caso o Short renderiza.
- [ ] **Resumo:** `GET /api/producao` e o resumo do episódio continuam com `render: {prontos, total, rodando, erros}`; com `total == 0` a etapa render só fica ok.
- [ ] **Testes:** pedir render em f1 de um candidato num episódio criado em f7 cria o corte em f1. Episódio novo, depois dos momentos, não ganha corte nenhum sozinho. Cancelar nos três casos acima. Cancelar recusado com o corte `renderizando`.
- [ ] Commit `feat: sem render automático — Short só renderiza quando pedido, com cancelar`.

### Task 2: Tela — formato por Short e cancelar

- [ ] **Entrada (`episodios.js`):** sai o campo "Shorts", e o rótulo "Formato" vira "Formato padrão". `pedidoNovoEpisodio` não manda mais `n_shorts`.
- [ ] **Tabela de candidatos (`episodio.js`):** quem não tem corte mostra um `<select>` de formatos (de `P.formatos`/`D.formatos`, já com o formato do episódio marcado) e "Renderizar", que manda `{formato}`. O mesmo seletor aparece no "tentar de novo" do corte em erro e num "Renderizar de novo" do Short pronto (gera uma versão nova no formato escolhido).
- [ ] **"Cancelar"** no painel e no cartão da grade quando o corte está `na_fila`.
- [ ] **Barra do episódio:** com `render.total == 0`, o rótulo fica "render", e não "render 0/0".
- [ ] Sem estouro em 375 px; `node --check` passa.
- [ ] Commit `feat: escolher o formato de cada Short e cancelar da fila`.

### Task 3: f6, f8 e f5 no app

- [ ] **Templates em `render/formatos/`:**
  - `hormozi.tpl` (f6), `desfoque.tpl` (f8) e `gameplay.tpl` (f5), copiados de `testes/comum/formatos/`.
  - Remova a linha `{{TRILHA}}` e todo efeito de transição (o bloco `{{CORTES}}` do zoom no gameplay; não deixe flash).
  - No gameplay, `#q-meio`/`#v-meio` passam de 1920×1080 fixos para `{{QM_W}}px`/`{{QM_H}}px`.
- [ ] **`render/montagem.py`:**
  - `FORMATOS = ("f7", "f1", "f6", "f5", "f8")` e `_TEMPLATES` com `hormozi`, `gameplay` e `desfoque`.
  - `valores(...)` devolve um superconjunto (o `montar_html` só reclama de placeholder sem valor, nunca de valor sobrando): `DUR`, `QW`, `LEGENDAS`, `TRILHA_CHEIO`, `TRILHA_METADE`, `QM_W`, `QM_H`, `TITULO` (com `html.escape`).
  - `LEGENDAS` sai palavra a palavra quando o formato é f6.
- [ ] **`render/legenda.legenda_html(gs, por_palavra=False)`:** com `por_palavra`, cada palavra vira `<i data-t="{t}">{palavra}</i>`, com o tempo de início relativo ao trecho, como no protótipo. Isso exige guardar os tempos por palavra no `Grupo` (`palavras: tuple[tuple[str, float], ...]` ou um campo novo); ajuste quem usa.
- [ ] **`render/rosto.trilha_fixa(r, escolhas, janela=JANELA, alvo=ALVO, escala=None)`:** generalize. A metade usa janela (1080, 960), alvo (540, 380) e escala `1080 / r.altura` (que dá 1,0 em 1080p, como no protótipo). `QM_W`/`QM_H` = `largura`/`altura` × essa escala. Teste com 1080p e 720p.
- [ ] **Assets por formato (`render/pipeline.py`):**
  - **f8:** `assets/fundo.mp4`, gerado do `trecho.mp4` com ffmpeg (`scale=540:960:force_original_aspect_ratio=increase,crop=540:960,boxblur=20:2`, sem áudio).
  - **f5:** `assets/gameplay.mp4`, gerado de um vídeo de `raiz/biblioteca/gameplay/*.mp4`. A escolha é determinística (`sorted(...)[indice % n]`). `-stream_loop -1` e `-t <duração>` cobrem Shorts mais longos que o gameplay; `scale=1708:960`, sem áudio. Sem nenhum vídeo na pasta: `ErroRender("sem gameplay em biblioteca/gameplay: ponha um .mp4 lá")`.
  - Os dois são gerados só se faltarem; quando o trecho é refeito (cache inválido), são apagados. Os argumentos do ffmpeg vêm de funções puras, com teste.
  - Grave por `.parcial` e confira o arquivo, como em `recorte.recortar`.
- [ ] **`contas/formatos.yaml`:** `no_app` de f5, f6 e f8 vira "plano B" (entraram no render do app).
- [ ] **Biblioteca:** copie `testes/_fontes/gameplay.mp4` para `biblioteca/gameplay/orbital.mp4` **na pasta principal `../Cortes`, não no worktree**. Essa pasta é dado, não código, e não entra em commit (`biblioteca/` não é rastreada).
- [ ] **Testes:**
  - os templates reais de todos os formatos montam sem sobrar placeholder;
  - os argumentos de fundo e de gameplay;
  - a escolha determinística do gameplay;
  - gameplay ausente dá erro claro;
  - o pipeline do f8 e do f5 chama o ffmpeg do asset uma vez e reaproveita na segunda versão.
- [ ] Commit `feat: f6 Hormozi, f8 Desfoque e f5 Gameplay renderizam no app`.

### Task 4: Conferência real e spec

- [ ] **Render real de um corte em f6, um em f8 e um em f5** no episódio de referência, estendendo o teste lento com `parametrize` de formato. Copie os MP4 para a pasta indicada pelo controlador.
- [ ] **Spec:**
  - §2/§3: sem render automático; formato por Short; f5, f6 e f8 no app; f4 e f3 nos planos D e E, explicando o motivo.
  - §4.4: a fila só processa o pedido.
  - §5: entrada sem "quantos renderizar", seletor de formato e "Cancelar".
- [ ] Commit `docs: spec com formato por Short e sem render automático`.
