# Painel de Contas — Design

Data: 2026-10-01 · Autor: Davi (com Claude) · Status: aguardando revisão
Mockup aprovado: `2026-10-01-painel-contas-mockup.html` (tela Comparar, dados fictícios).

## 1. Objetivo

Ler os números de **várias contas do YouTube** (uma por nicho/perfil) e mostrar **que tipo de
Short funciona** — por formato de edição, conta/nicho, tema do corte e podcast de origem.
É o módulo `retorno` da spec principal (§11), estendido para várias contas, e a primeira tela
do servidor web que depois recebe a curadoria (§10).

### Fora da v1

Publicação pelo app (vem depois com `youtube-publicar`), curva de retenção pela Analytics API
(OAuth por canal vence a cada 7 dias), coleta agendada, métrica "viewed vs swiped" (o token do
Studio ainda não está conferido), veredito automático ("use o formato X").

## 2. Decisões

| Decisão | Escolha | Motivo |
|---|---|---|
| Dimensões | formato, conta/nicho, tema, podcast | Davi escolheu as quatro |
| Publicação | manual na v1; app publica depois | Escopo menor; ligação Short→corte vira passo da tela |
| Coleta | 2–4 contas, botão "Atualizar", só export do Studio | Login uma vez por conta; API exige OAuth semanal por canal |
| Stack | FastAPI + HTML/JS puro em `127.0.0.1` | Mesma stack prevista para a curadoria — uma interface só |
| Métrica principal | views aos 7 dias ÷ mediana da própria conta | Mesma idade para todos; contas novas têm bases muito diferentes |
| Estatística | mediana, n sempre visível, n<5 = "pista" | Views de Short têm cauda longa: um viral puxa a média |
| Veredito | o painel mostra, Davi decide | §11: o retorno propõe, não decide |

## 3. Dados

Arquivos de trabalho ficam fora do git (como `episodios/`); só a configuração entra.

```
contas/
  contas.yaml                         # no git
  formatos.yaml                       # no git: vocabulário fechado de formatos
  publicados.jsonl                    # fora do git: 1 linha por Short ligado
  retratos/<conta>/<AAAA-MM-DD>.json  # fora do git: export do Studio do dia
```

`.gitignore` ganha `contas/publicados.jsonl` e `contas/retratos/`.

### 3.1 `contas.yaml`

```yaml
contas:
  - id: grana                 # [a-z0-9-]+, único
    nome: Grana Cortes
    handle: "@grana.cortes"
    nicho: financas           # tem de existir em nichos/<nicho>/perfil.yaml
    perfil_studio: grana      # nome do perfil de login da skill youtube-analytics
```

### 3.2 `formatos.yaml`

```yaml
formatos:
  f1: {nome: Falante puro, obs: controle}
  f3: {nome: Motion dinâmico, obs: troca de imagem por fala}
  f4: {nome: B-roll real, obs: risco alto de Content ID}
  # ... um por formato de testes/TEMPLATES.md; templates de nichos/*/templates/ entram pelo nome
```

### 3.3 Linha de `publicados.jsonl`

```json
{"video_id": "c5xqNNWFT9w", "conta": "grana", "publicado_em": "2026-10-03",
 "corte": "testes/f7-conversa-comediante",
 "etiquetas": {"formato": "f7", "temas": ["humor", "dinheiro_alheio_quanto_ganha"], "podcast": "PrimoCast"}}
```

- `temas` usa o vocabulário das tags de **bônus/penalidade** dos perfis de nicho
  (`nichos/*/perfil.yaml`) — o mesmo que o detector já usa.
- `formato` tem de existir em `formatos.yaml`; `conta` em `contas.yaml`.
- Etiqueta fora do vocabulário é **recusada com erro** (texto livre fragmenta os grupos:
  "b-roll" ≠ "broll").
- `video_id` é único no arquivo; religar substitui a linha (o arquivo é reescrito inteiro a
  partir da lista validada, não editado no lugar).

### 3.4 Retrato

Export do Studio de uma conta num dia, período **"desde sempre"** (total acumulado por vídeo),
convertido pelo `ler_csv.py` da skill e gravado como:

```json
{"conta": "grana", "coletado_em": "2026-10-10T09:12:00", "videos": [
  {"video_id": "...", "titulo": "...", "publicado_em": "2026-10-03", "duracao_s": 26,
   "views": 1830, "pct_media": 87.4, "duracao_media_s": 22.7, "inscritos": 3}]}
```

Métricas pedidas ao export: `views,duracao_media,pct_media,inscritos` (as que o método usa).
Formato real do CSV conferido num export de 2026-08: data de publicação em inglês
(`"Aug 11, 2026"`) mesmo com cabeçalho em português; decimal com ponto; duração média `h:mm:ss`.
Célula vazia só é aceita (como 0) em vídeo com 0 views; em qualquer outro caso é erro.

Coluna obrigatória ausente no CSV → erro que nomeia conta e coluna. Um retrato por conta por
dia; atualizar de novo no mesmo dia sobrescreve o do dia.

## 4. Fluxo

1. **Atualizar.** Para cada conta, roda o export do Studio da skill `youtube-analytics`
   (subprocesso; executor injetável para teste). Contas rodam uma após a outra; a falha de uma
   não interrompe as outras e aparece na tela com a causa (login vencido, export vazio, coluna
   faltando). Retrato antigo nunca é apresentado como novo: a tela mostra a data do último
   retrato bom de cada conta.
2. **Ligar.** Davi cola o link do Short publicado. O app extrai o `video_id` (`/shorts/<id>`,
   `youtu.be/<id>`, `watch?v=<id>`; outra forma → erro), confere que o vídeo existe no último
   retrato da conta escolhida (senão recusa e diz para atualizar), e **sugere o corte** pelo
   título mais parecido entre as pastas de corte conhecidas (`testes/*/` e
   `episodios/*/cortes/*/`). Pré-preenchimento das etiquetas: `formato` pelo prefixo da pasta
   (`f7-...` → `f7`), `podcast` pelo campo `canal` do `meta.json` quando o corte está em
   `episodios/<id>/cortes/`. `temas` são escolhidos na tela: hoje nenhum arquivo liga a pasta do
   corte ao candidato do detector (isso nasce com a curadoria). Davi confirma ou corrige.
3. **Comparar.** Funções puras sobre `publicados.jsonl` + retratos (§5).

O caminho da skill `youtube-analytics` vem de configuração; se não existir, o servidor falha
ao subir com mensagem clara.

## 5. Método (funções puras)

### 5.1 Views aos 7 dias

Para cada Short ligado, a série é `(publicado_em, 0)` seguida de `(dia do retrato, views)`
de cada retrato da conta em que o vídeo aparece.

- **Medido:** existe retrato até 3 dias depois do dia 7 → interpolação linear entre os
  pontos que cercam o dia 7.
- **Estimado:** o primeiro retrato depois do dia 7 está a mais de 3 dias dele → mesma
  interpolação, marcada "estimado" na tela (entra na comparação com a marca).
- **Em maturação:** nenhum retrato depois do dia 7 → fora da comparação, aparece apagado.

### 5.2 Relativo à conta

`rel = views_7d / mediana(views_7d dos Shorts medidos da mesma conta)`. Conta com menos de 3
Shorts medidos não tem base: seus Shorts aparecem sem `rel` e com o aviso "conta sem base".

### 5.3 Grupos

Por dimensão escolhida (formato, conta, tema, podcast), cada grupo tem: `n`, mediana de `rel`,
mediana de `pct_media`, inscritos por mil views (soma de inscritos ÷ soma de views × 1000).
`n < 5` → selo "pista". Em **tema**, um Short entra em todos os grupos das suas tags; a tela
avisa que os grupos não somam o total.

### 5.4 Matriz e confusão

Matriz formato × conta: mediana de `rel` e `n` por célula; célula vazia = teste que falta.
**Confusão:** formato que só aparece em uma conta (ou conta com um formato só) é listado no
aviso: o número dele mistura formato com conta.

## 6. Telas

Linguagem visual do mockup, igual nas três telas.

- **Paleta:** fundo grafite escuro; divergente **laranja** (acima da base da conta) ×
  **ardósia** (abaixo) — legível para daltonismo, sem o verde/vermelho de corretora; amarelo só
  para aviso (pista, login vencido, confusão).
- **Tipografia:** Instrument Serif (títulos e números de destaque), Instrument Sans (interface),
  JetBrains Mono (números tabulares), pelo Google Fonts (a coleta já exige internet; sem
  arquivo de fonte no repositório).
- **Gráficos:** SVG desenhado à mão em JS, sem biblioteca. Escala log de 0,1× a 10× (metade e
  dobro com o mesmo passo).
- **Miniaturas 9:16** dos Shorts como unidade visual, com o `rel` sobreposto; imagem vinda do
  YouTube pelo `video_id`.

**Trilho lateral (todas as telas):** Contas, Shorts (com contador "N sem ligação"), Comparar;
lista das contas com estado (verde ok, amarelo login vencido / falhou) e hora do último retrato;
botão "Atualizar todas".

**Contas.** Cartão por conta: nicho, handle, último retrato, estado, nº de Shorts ligados,
mediana de views aos 7 dias. Botões "Atualizar" e, se o login venceu, "Fazer login" (abre o
Chrome da skill para Davi entrar; o app nunca vê senha). Formulário "Nova conta" (valida `id`,
`nicho` existente, perfil).

**Shorts.** Seção "Sem ligação" no topo (pendência), depois "Ligados". Colunas: miniatura,
título, conta, idade, views aos 7 dias (com marca medido/estimado/maturando), `rel`, % assistida,
etiquetas. "Ligar" abre um painel com o corte sugerido, as etiquetas pré-preenchidas em seletores
do vocabulário fechado, e confirmar.

**Comparar** (mockup). Seletor de dimensão; uma linha por grupo ordenada pela mediana de `rel`,
com nome, n, mediana em serifa grande, strip plot (um ponto por Short, linha tracejada em 1×,
traço da mediana do grupo), % assistida e inscritos/1k; selo "pista". Abaixo: matriz formato ×
conta com aviso de confusão, e as miniaturas do grupo selecionado ordenadas por `rel`
(maturando apagadas).

Largura de celular: trilho some, tabela mostra só nome e mediana, matriz e miniaturas empilham.

## 7. Arquitetura

```
src/cortes/painel/
  dados.py        # contas.yaml, formatos.yaml, vocabulário de temas (dos perfis de nicho)
  publicados.py   # publicados.jsonl: ler, validar, ligar, gravar
  retratos.py     # tipos do retrato; ler e gravar retratos/<conta>/<dia>.json
  studio.py       # puro: CSV do export do Studio → vídeos do retrato
  metodo.py       # puro: views_7d, relativo à conta, linhas da tela Shorts
  comparacao.py   # puro: grupos, matriz, confusão
  ligacao.py      # puro: cortes conhecidos, sugestão por título, etiquetas pré-preenchidas
  coleta.py       # fino: roda o export da skill por conta (executor injetável), grava retrato
  servidor.py     # FastAPI: rotas JSON finas + arquivos estáticos
web/static/       # index.html, painel.css, painel.js (uma página, três telas)
```

`video_id` do link reaproveita `cortes.episodio.id_do_video` (já testado com as formas de link).

CLI: `cortes painel` sobe o servidor em `127.0.0.1` e imprime o endereço.

Dependências novas: `fastapi` e `uvicorn` (servidor local; já previstos para a curadoria na
spec principal §5). Comparação de títulos com `difflib` da biblioteca padrão.

## 8. Erros

Nada de default silencioso:
- Configuração inválida (conta sem nicho existente, formato duplicado) → servidor não sobe e
  diz arquivo e campo.
- Falha de coleta de uma conta → registrada com a causa, visível na tela; as outras seguem.
- CSV sem coluna obrigatória → erro com conta e coluna; o retrato não é gravado.
- Link sem `video_id` reconhecível, vídeo ausente no retrato da conta, etiqueta fora do
  vocabulário → recusa com o motivo, nada é gravado.

## 9. Testes

Caminhos críticos, não cobertura:
- `views_7d`: medido, estimado (lacuna > 3 dias), em maturação, retrato no próprio dia 7.
- `rel`: mediana por conta; conta com < 3 Shorts medidos fica sem base.
- Grupos: mediana, inscritos/1k, selo de pista, tema multivalor.
- Matriz e detecção de confusão.
- Leitura do retrato: fixture de CSV real e CSV com coluna faltando.
- `video_id` das três formas de link e recusa de link estranho.
- Validação de vocabulário e unicidade de `video_id` em `publicados.jsonl`.
- `coleta`: executor falso que falha numa conta — as outras gravam, a falha é reportada.

## 10. Riscos

- **Mudança no Studio** quebra o export (a skill usa URL parametrizada e Playwright); a falha
  aparece por conta, com a causa.
- **Amostra pequena:** com 2–4 contas e poucos Shorts por formato, quase tudo será "pista" por
  semanas. O painel mostra isso em vez de esconder.
- **Confusão conta × formato:** se cada conta testar formatos diferentes, nada se separa. A
  matriz existe para guiar o que postar em seguida.
- **Correlação:** grupos diferem também em tema e no dia de postagem; o painel mede, não prova.
