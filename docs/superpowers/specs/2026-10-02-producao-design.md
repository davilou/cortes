# Produção no Painel — Design

Data: 2026-10-02 · Autor: Davi (com Claude) · Status: aguardando revisão
Mockup aprovado: `2026-10-02-producao-mockup.html` (aba Produção, dados fictícios).
Referência de produto: Opus Clip (cola o link → Shorts prontos → ajusta → exporta).

## 1. Objetivo

Levar a produção para o painel: Davi cola o link de um episódio do YouTube, o app acha os
momentos, **renderiza sozinho os N melhores** e mostra os Shorts prontos para assistir,
aprovar, rejeitar, editar e baixar. Estende a spec principal
(`2026-09-30-app-cortes-design.md`: curadoria §10, visão §6.5, cenas §8, render §9) e roda no
mesmo servidor do painel de contas (`2026-10-01-painel-contas-design.md`).

### Fora desta spec

Upload de vídeo do PC e transcrição por arquivo enviado; formato f2; publicação automática; nicho
humor. (O f3 Motion entrou no plano E, §7.) O
`cortes detectar` do terminal segue com o
openai-whisper (`cortes/transcricao.py`) — passar o terminal para a transcrição local (§4.2) fica
para depois.

## 2. Decisões

| Decisão | Escolha | Motivo |
|---|---|---|
| Entrada | Só link do YouTube | Davi escolheu; cobre os podcasts-fonte |
| Transcrição | **Local, faster-whisper `large-v3-turbo`** na GPU (Davi decidiu em 2026-10-02; substitui a legenda do YouTube) | ~35 s por hora de áudio, boa pontuação, início e fim por palavra, sem depender do YouTube (que devolveu HTTP 429) — benchmark em §4.2. Transcrição colada removida em 2026-10-02 — com a transcrição local a ~35 s/h ela virou passo extra sem ganho |
| Render | **Sem render automático** (decisão de 2026-10-02): nada renderiza sem pedido. "Renderizar" por candidato, com seletor de formato; "Cancelar" tira da fila um Short que ainda não começou | O "N melhores" automático gastava render em Short que Davi ia rejeitar sem assistir; cada Short só é feito no formato que Davi escolher |
| Formatos | f7 Conversa, f1 Falante, f6 Hormozi, f8 Desfoque, f5 Gameplay, f4 B-roll automático e f3 Motion automático (plano E, §7) no app | Davi escolheu; f7 é o sinal mais forte da R2; f6/f8/f5 só dependem de template e entraram junto (decisão de 2026-10-02); o f9 Ilustrado (cartão de foto, pedido do Davi em 2026-10-02) virou o f4 B-roll automático em 2026-10-03 (§11); o f3 Motion entrou em 2026-10-03 com cenas escolhidas pelo Claude e montadas pelo código (§7), à espera do veredito do Davi no teste cego |
| Motor de render | **HyperFrames**, não Remotion | Os 8 formatos testados e aprovados foram feitos nele (`testes/`); substitui a decisão "Remotion" da spec principal §5 |
| Nota mostrada | Nota do detector (0–10) com a rubrica aberta | Explica o porquê, em vez de "viralidade" opaca |
| Execução | Uma fila, um trabalho por vez | GPU, cota do Claude e CPU do render são únicos |
| Entrega | Uma spec, 5 planos em ordem (A→E) | Cada plano entrega algo usável; f3 por último por ser o mais arriscado |

## 3. Planos

| Plano | Entrega | Risco |
|---|---|---|
| **A. Produção** | Link → vídeo + transcrição local → detector, com progresso por etapa; candidatos com nota, rubrica, justificativa e player do trecho | baixo |
| **B. Render f1 + f7** | Renderizar sob pedido (sem automático), com formato por Short e Cancelar; f6 Hormozi, f8 Desfoque e f5 Gameplay somam-se a f1/f7 (Davi, 2026-10-02); grade de Shorts; aprovar/rejeitar (→ exemplos); baixar MP4; pausas cortadas sempre; sem trilha; transições em corte seco, sem flash nem zoom nas emendas em nenhum formato | baixo — o código existe nos protótipos |
| **C. Editor** | Início/fim por palavra, texto da legenda, título, troca de formato, quem aparece por plano, versões | médio (multirrosto) |
| **D. f4 B-roll** | Automático (§11): deixas pelo Claude → vídeo do YouTube (foto de reserva na deixa literal) → conferência visual → clipe de 1,5–3 s em tela cheia, corte seco; substitui o f9 Ilustrado | médio — vídeo e foto de terceiros; YouTube lento e sujeito a bloqueio |
| **E. f3 Motion** | Feito (§7): 7 componentes + cenas em JSON pelo Claude, regra dos números e ritmo no código; teste cego contra o f3 manual | alto |

## 4. Arquitetura

### 4.1 Código

```
src/cortes/producao/
  fila.py          # fila única, uma thread; estados; retomada após reinício
  transcricao_local.py  # faster-whisper → list[Palavra] (conversão pura) + transcrição fina na GPU
  etapas.py        # baixar → transcrição → sinais → detector → render dos N
  rotas.py         # API da Produção (montada no servidor do painel)
src/cortes/render/
  recorte.py       # trecho.mp4 (ffmpeg), cortes de pausa
  rosto.py         # enquadramento fixo por plano (puro) + chamada ao detector
  legenda.py       # grupos de legenda (puro), aplicação das edições
  montagem.py      # plano de corte → index.html a partir do template (puro)
  hyperframes.py   # projeto, render, log (executor injetável)
  corte.py         # corte.json: modelo, transições, planejar, próximo
  pipeline.py      # um corte: trecho → rosto → (B-roll, f4 | cenas, f3) → html → mp4
  ilustracao.py    # f4: deixas pelo Claude (schema com tipo + ritmo no código)
  broll_video.py   # f4: busca e trecho de 3 s do YouTube, quadros, foto em tela cheia
  ilustracao_imagens.py      # f4: busca ddgs e download da foto de reserva
  broll_candidatos.py        # f4: vídeos e fotos de uma deixa, em série, YouTube fora no bloqueio
  broll_folha.py             # f4: folha mista V/F de conferência
  ilustracao_conferencia.py  # f4: conferência visual numa chamada com Read
  ilustracao_cache.py        # f4: cache em cortes/<n>/ilustracao/
  ilustracao_etapa.py        # f4: a etapa inteira
  processo.py      # executor injetável, ErroRender, exigir()
  motion.py        # f3: cenas pelo Claude → validadas (parâmetros, números, ritmo)
  motion_prompt.py / motion_params.py / motion_numeros.py / motion_ritmo.py / motion_sincronia.py
  motion_componentes.py / motion_animacao.py  # f3: HTML e GSAP de cada componente (puro)
  motion_cache.py  # f3: cache em cortes/<n>/motion/cenas.json e a etapa
render/formatos/   # falante.tpl, conversa.tpl, hormozi.tpl, desfoque.tpl, gameplay.tpl, broll.tpl,
                   # motion.tpl
render/visao/rosto.py  # detector (Python do ComfyUI, fora do mypy)
```

O que os protótipos em `testes/comum/` fazem (`corte.py`, `rosto.py`, `rodada.py`,
`buscar_broll.py`, `formatos/*.tpl`) é portado com o episódio como parâmetro. `testes/` fica
como histórico da rodada de formatos. O caminho do Python com onnxruntime (hoje o venv do
ComfyUI) vira configuração com verificação na subida, como a skill no painel de contas.

As pausas são achadas pelo áudio, não pelo vão entre palavras (a legenda do YouTube não tem
vão entre palavras; com a transcrição local, §4.2, o vão existe, mas o critério por áudio
segue valendo — é o que o render usa hoje). Com a transcrição local, `FOLGA_INICIO` (0,3 s)
deixou de compensar o atraso da legenda do YouTube e virou só respiro antes da primeira
palavra; o silêncio que ele adiciona é aparado pela regra de bordas de
`segmentos_sem_pausa`. O enquadramento troca no instante real da troca de câmera (ponto
`corte: true` do detector), não num horário fixo por plano.

### 4.2 Transcrição local

A etapa de transcrição (chave `legenda` no `estado.json`, mantida pelos episódios já gravados)
roda o faster-whisper `large-v3-turbo` na GPU sobre o `audio.wav` do episódio
(`producao/transcricao_local.py`) e grava `palavras.json` com início e fim por palavra.

Benchmark de 2026-10-02 (20 min do PrimoCast 536, `c5xqNNWFT9w`, RTX 3090; Davi escolheu o
turbo):

| motor | 20 min | por hora | diferença vs legenda do YouTube |
|---|---|---|---|
| openai-whisper large-v3 (o do `cortes detectar`) | 358 s | ~18 min | 12,4% |
| **faster-whisper large-v3-turbo** (int8_float16, BatchedInferencePipeline lote 16, word_timestamps) | 11,1 s | ~35 s | 12,2% |
| faster-whisper large-v3 | 22,5 s | ~70 s | 12,3% (pontuação pior: frases sem ponto) |
| Parakeet TDT 0.6B v3 (onnx-asr) | 55,9 s | ~3 min | 12,2% (mais erros de palavra) |

O turbo é o mais rápido, pontua bem (o segmentador corta frases pela pontuação), dá início e
fim por palavra e não depende do YouTube. A legenda do YouTube saiu do pipeline (o download
dela levou HTTP 429), e com ela a transcrição colada (§2). Regras:

- o áudio entra como array float32 16 kHz mono (`sinais.ler_wav_mono`): passar o caminho faz o
  faster-whisper abrir com PyAV, e o PyAV instalado recusa o `metadata_errors` que ele passa;
- o CTranslate2 precisa do CUDA 12 + cuDNN 9 (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`, que
  convivem com o torch cu130); no Windows as pastas `bin` deles são registradas antes do
  import — se faltarem, a etapa para com "instale nvidia-cublas-cu12 e nvidia-cudnn-cu12";
- o modelo é carregado a cada transcrição (~4 s; 3,2 s medidos) e liberado em seguida
  (`unload_model` do CTranslate2 + `gc.collect()`), para não prender VRAM que o ComfyUI usa
  (~1 GB a menos depois de liberar); uma trava serializa carga e transcrição;
- o modelo vem só do cache local do Hugging Face: sem ele, a etapa para com o comando que o
  baixa uma vez (a fila não baixa nada escondido);
- texto sem espaço nas pontas, palavra vazia descartada, tempos com 3 casas; o início nunca
  volta para trás da palavra anterior e o fim nunca fica antes do início; nenhuma palavra → erro;
- conferido no trecho de 20 min pelo venv do projeto: 4.164 palavras em ~15 s por chamada,
  carga e liberação incluídas.

### 4.3 Dados por episódio

```
episodios/<id>/
  video.mp4  audio.wav  meta.json  palavras.json  sinais.json  candidatos.json   (já existem)
  estado.json        # etapas: pendente | rodando (progresso) | ok | erro (causa, arquivo)
  cortes/
    planejado.json   # marcador: os N melhores já foram postos na fila (uma vez por episódio)
    <n>/
      corte.json     # candidato de origem, início/fim, formato, título, `edicoes` (editor,
                     # plano C: legenda e mascaradas por índice global da palavra em
                     # palavras.json, rostos por plano de câmera), `alterado` (há edição salva
                     # ainda não renderizada; volta a false em `concluir`), status do render:
                     # na_fila | renderizando | pronto | erro (+ causa), versão atual
      recorte.json   # início/fim/segmentos: marcador de trecho e rosto prontos (cache)
      rosto.json     # formato 2 (plano C): até 3 rostos por amostra — {formato, largura,
                     # altura, cortes (trocas reais de câmera), amostras: [{t, rostos: [{x, y,
                     # r, conf}]}]}. Um `rosto.json` de formato velho (1, plano B) não serve de
                     # cache: o editor precisa das pessoas por plano, que só existem no formato
                     # atual, e a medição roda de novo.
      miniaturas/    # p<plano>-<pessoa>.jpg: quadro do meio do plano, recortado em volta do
                     # rosto (editor, "quem aparece"). Apaga quando início/fim muda (trecho novo).
      ilustracao/    # só f4 (§11): deixas.json, ilustracao.json (formato 4: início/fim e hash
                     # do texto do corte + uma entrada por deixa), trechos D<k>-v<j>.mp4 com os
                     # quadros -q1..-q3.jpg, fotos D<k>-c<j>.jpg (-cheia.jpg a escolhida) e
                     # folha-<i>.jpg. Apaga quando início/fim muda, como miniaturas/. O clipe
                     # escolhido é copiado para projeto/assets/broll-<k>.mp4|jpg.
      projeto/       # projeto HyperFrames
      short-v<k>.mp4 # versões; a anterior é mantida
```

Aprovado/rejeitado ficam em `curadoria.json`, não em `corte.json` (o índice do candidato é o
índice do corte, então a curadoria do plano A já vale para o Short; repetir a decisão criaria
duas cópias, e uma delas envelheceria).

O `corte.json` guarda o título: a sugestão de corte do painel de contas (aba Shorts) passa a
casar cortes de episódio pelo título, e não só as pastas de `testes/` (`ligacao.py` lê o
`corte.json`; limite registrado no painel de contas some).

### 4.4 Fila

- Trabalhos: `processar_episodio(id)` e `renderizar(id, n, versão)`. FIFO, uma thread.
- Cada etapa grava seu arquivo e é pulada se ele existe (padrão do `cortes detectar`).
- Ao subir, o servidor relê os `estado.json` e recoloca na fila o que estava `rodando`.
- **Sem render automático** (Davi, 2026-10-02): o detector termina em `momentos`; nenhum corte é
  posto na fila sozinho. A fila só processa o que foi pedido — "Renderizar" num candidato grava
  um corte `na_fila` no formato escolhido no seletor e reenfileira o episódio; um gancho `antes`
  da fila reabre a etapa `render` se ela já tinha fechado. Um `cortes/planejado.json` antigo no
  disco (de antes desta decisão) é ignorado.
- **Cancelar** (`POST /cortes/{indice}/cancelar`, sob a trava `escrita`): só vale para corte
  `na_fila`; em qualquer outro status, recusa com motivo. A fila reivindica o próximo corte sob
  a mesma trava `escrita` (`_reivindicar`, `producao/render.py`), então não há corrida: ou o
  Cancelar vê o corte ainda `na_fila` (e a fila não o pega mais) ou já `renderizando` (e o
  Cancelar é recusado).
- Cota do Claude atingida → a fila **pausa** e a tela avisa; não descarta trabalhos.

### 4.5 Curadoria e retorno ao detector

Aprovar grava o trecho em `nichos/<nicho>/exemplos/bons.jsonl`; rejeitar pede o motivo
(lista fixa + texto livre) e grava em `ruins.jsonl` — o mesmo formato que o detector já lê.

## 5. Telas (mockup aprovado)

Trilho com dois grupos: **Produção** (Episódios) e **Retorno** (Contas, Shorts, Comparar). No
rodapé do trilho, a fila: o que roda agora, com progresso, e quantos esperam.

**Episódios**
1. Entrada: link, nicho, **formato padrão** (f7/f1/f6/f8/f5/f4/f3) — só o valor pré-marcado no seletor de cada Short, não um campo "Shorts"/quantos
   renderizar, que saiu (decisão de 2026-10-02: sem render automático). "Gerar Shorts". Link sem
   id de vídeo ou já processado → recusa com motivo.
2. Lista de episódios: capa, título, canal, duração, barra de etapas (vídeo, transcrição, sinais,
   momentos, render) com estados ok/rodando/erro; a etapa render mostra "k/N" só quando há algum
   corte pedido (`total > 0`) — com `total == 0` o rótulo é só "render", e ela já conta como ok;
   erro mostra a causa e "tentar de novo".
3. Episódio selecionado: grade de Shorts 9:16 (nota 0–10, status, prévia, título, duração,
   formato, ✓ ✕ Editar; "Cancelar" quando `na_fila`; "Renderizar de novo" com seletor de formato
   quando pronto, gera uma versão nova); tabela "Outros candidatos" (nota, início, duração,
   título, justificativa, **seletor de formato** pré-marcado com o formato padrão do episódio +
   "Renderizar"). O mesmo seletor aparece no "tentar de novo" de um corte em erro.
4. Painel do Short: player, as 5 notas da rubrica em barras, justificativa, tags de bônus,
   aprovar/rejeitar/editar, baixar MP4, copiar título.

**Editor** (plano C, implementado), três colunas:
- **Prévia 9:16** no próprio navegador: o `index.html` do projeto HyperFrames servido com o
  runtime injetado logo depois de `<head>` (`render/previa.py` `com_runtime`), dentro de
  `<hyperframes-player src="/composition/index.html" controls>` (confirmado por teste real,
  §"Fatos verificados" do plano C). "Renderizar" gera o MP4 final.
  - A montagem da prévia roda numa thread própria (`producao/previas.py`), fora da fila do
    render — recortar o trecho e medir o rosto leva de 10 a 30 s quando início ou fim mudam, e
    a prévia não deve esperar atrás de outro render.
  - Situação da prévia (`situacao_previa`): com a memória da thread, vale ela; sem memória
    (painel reiniciado), vale o disco — `projeto/index.html` mais novo que `corte.json` é
    "pronta", mais velho é "desatualizada", sem o arquivo é "ausente". A tela pede a prévia
    sozinha nos dois últimos casos. Sem edição pendente (`corte.alterado is False`) a prévia
    está sempre "pronta": o render grava o `index.html` e só depois o `corte.json`
    (`concluir`), então comparar os dois mtimes só faz sentido quando há edição pendente.
  - Edição é recusada enquanto o corte está `na_fila`/`renderizando` ou com a prévia em
    preparo, e "Renderizar" é recusado com a prévia em preparo — nunca dois escritores no
    mesmo `projeto/` (`editavel`, `_exigir_editavel`). A miniatura de um rosto também é
    recusada nesse estado, porque o rosto pode estar sendo medido de novo.
- **Transcrição** em volta do corte, palavra a palavra: clicar move início/fim (sempre por
  palavra); a regra de início do detector avisa quando o início depende de contexto. Edição é
  por palavra (corrigir nome/número, juntar palavras apagando uma com texto vazio, apagar); a
  quebra manual de grupo fica fora, os grupos continuam saindo de `legenda.grupos`. Clicar numa
  palavra alterna o mascaramento; "Mascarar palavrões" aplica a lista fixa de `edicao.PALAVROES`.
  Mudar início ou fim zera as escolhas de rosto (os planos de câmera mudam com o trecho; a
  escolha antiga apontaria para outro plano) e exige nova medição do rosto.
- **Ajustes:** título; formato (gera versão nova); **quem aparece** — linha do tempo dos planos
  de câmera (`render/rosto.py` `planos`) com as miniaturas dos rostos de cada plano
  (`render/miniatura.py`, quadro do meio do plano recortado num quadrado em volta do rosto),
  clique escolhe quem fica na tela (padrão: a pessoa mais confiável — mais detecções, depois
  maior confiança). Agrupar os rostos de um plano em pessoas usa a posição x (câmera parada:
  cada pessoa fica no seu lugar), medindo o vão contra o PRIMEIRO rosto de cada grupo, não o
  último — single-linkage deixava uma cadeia de detecções intermediárias emendar duas pessoas
  que nunca ficaram próximas entre si. Rosto ilegível (poucas detecções, trilha não confiável)
  não bloqueia o editor: os planos saem vazios e a tela mostra um aviso (`rosto_erro`), em vez
  de um 500 — a prévia refaz a medição e resolve. Escolha de rosto inválida (pessoa que não
  existe mais no plano, por exemplo depois de remedir) volta ao padrão com aviso
  (`escolha_invalida`), em vez de recusar a tela inteira. "Editar" só existe para candidato que
  já tem corte (`corte.json`), ou seja, que foi renderizado ou pedido; no f4, as opções de
  B-roll por deixa; no f3, as cenas (só leitura, com as descartadas e o motivo) e "Refazer motion".

## 6. B-roll (plano D)

> **Feito como f4 B-roll automático — ver §11**, que vale no lugar desta seção onde as duas
> divergem: clipe em tela cheia (não dividido/cheio), escolha automática pela conferência (não 3
> opções no editor), vídeos de 15 s a 3 min, foto de reserva na deixa literal. O texto abaixo é o
> desenho original, mantido como histórico.

1. **Deixas:** `claude -p` (schema obrigatório) lê a transcrição do corte e devolve
   `{inicio, duracao, tipo: literal|acontecimento, busca}`.
2. **Busca:** `yt-dlp ytsearch` como o protótipo (`buscar_broll.py`): vídeo de 30 s–30 min,
   trecho da duração pedida, 1080p sem áudio; `fonte_url`, `licenca: desconhecida`, `risco: alto`.
3. **Conferência:** folha de quadros por candidato; `claude -p` com `Read` liberado só na pasta
   da folha diz se bate com a deixa; descarta o que não bate.
4. **Escolha:** 3 opções por deixa no editor; deixa sem opção vira "sem visual" visível, nunca
   um visual qualquer.
5. **Layout:** alterna dividido/cheio pelo template, B-roll ≤ 60% do tempo (R2, pista).

## 7. Motion (plano E)

Feito em 2026-10-03 (plano `2026-10-03-motion.md`). O f3 mostra o que a pessoa diz em painéis
animados, portados dos feitos à mão em `testes/short-400mil-dinamica/modelo.tpl`, alternando em
**corte seco** dois estados: **div** (painel numa faixa de 680 px em cima, rosto na janela de
baixo, 1080×1240, escala 1,2, rosto em (540, 400)) e **cheio** (cartão na tela inteira, ou o rosto).
Sem flash, sem zoom de transição e sem o `scale 1.04` da capa; a câmera não segue o rosto — trilha
fixa por plano de câmera nas duas janelas (`rosto.trilha_fixa`, `JANELA_DIV`/`ALVO_DIV`). Ficam as
entradas dos elementos (descer de cima, barra crescendo, contagem, pino no mapa). Tema e fontes do
protótipo.

- **Componentes** (`render/motion_params.py`, tipados, com limite de caracteres pelo layout):
  `capa` (cheio, 0–2,2 s, título com 1 palavra destacada), `contador` (div, de 0 ao valor, com
  `marcos` e barra de progresso opcionais), `valor_cheio` (cheio, com `de` e `selo`), `comparacao`
  (cheio, 2 barras e `carimbo`), `chat` (div), `lista` (div, 2–4 itens), `rota` (div). A contagem é
  escrita quadro a quadro no próprio template (como o count-up do registry), sem subcomposição.
- **Cenas:** `claude -p` (sonnet) lê as palavras numeradas e devolve **JSON validado por schema**
  (componente, palavras de início e fim, parâmetros) — nunca HTML. Todo texto do LLM passa por
  `html.escape`; o JavaScript só leva ids e números. Índice de palavra inválido é erro do LLM;
  parâmetro inválido, número não dito ou ritmo descartam só a cena, que fica registrada com o
  motivo.
- **Números:** só os **ditos na fala até o fim da cena** (não só dentro da janela da cena — a
  pergunta ao ChatGPT retoma "isso", dito antes; mas nada que ainda vai ser dito). O leitor entende
  algarismo ("400", "1.500", "37,5%", "R$7.500"), extenso ("mil e duzentos", "trinta e sete") e
  "pau" ("3 pau e meio" = 3.500); "por cento" e pontuação separam números, e "um/uma" sozinho é
  artigo. Número da tela com multiplicador vale quando a fala disse só a base ("tava valendo 550"
  sustenta "R$ 550 mil"); zero sempre passa. Número calculado (o "+37,5%" do protótipo manual) é
  recusado — decisão do plano, mais estrita que a regra antiga "ou calculados deles".
- **Ritmo** (`render/motion_ritmo.py`): capa só uma, em 0–2,2 s; nenhuma outra cena antes de 1 s;
  cada cena de 1,5 a 4 s; cenas não se sobrepõem; pelo menos 1 s de rosto só entre dois cartões
  **cheios** — painel div cola no vizinho (o rosto já está na janela de baixo; o manual cola chat →
  "PERDI DINHEIRO"), e duas div coladas não piscam o cheio; motion ≤ 70% (saem as últimas, nunca
  as já aceitas). O prompt pede de 50% a 70% de cobertura. Pesquisa 03: alvo de 0,6–0,8 trocas de
  plano por 10 s; cada entrada e saída de painel é troca, e 4 cenas em 28 s já dão ~2,5 — o ritmo
  não segura abaixo do alvo (teste em `test_render_motion_ritmo.py`).
- **Segunda chamada** (`render/motion_cobertura.py`, plano `2026-10-03-melhora-f3.md`): validada a
  primeira resposta, se a cobertura ficou < 50% ou sobrou vão de rosto > 6 s com número,
  comparação, lista ou lugar, o LLM recebe as cenas aceitas (fixas no ritmo), as recusadas com o
  motivo e os vãos (≥ 3,5 s depois do gancho) com as palavras, e devolve cenas só para eles. No
  máximo 2 chamadas por corte; o cache guarda o resultado final.
- **Prompt:** recebe título e canal do `meta.json` (sem eles, erro claro); o rótulo da capa é o
  nome de quem fala quando o título o identifica ("COMO MAURÍCIO MEIRELLES GANHA..." → "MAURÍCIO
  MEIRELLES"), senão o tema. Contraste, perda ou ganho ("perdi dinheiro", "rendeu mais", "X contra
  Y") é `comparacao`, com um lado não numérico ("mais") se a fala não deu o número. Nomes próprios
  e palavras deformados pela transcrição saem com a grafia certa nos textos ("saco arema" →
  "Saquarema"), sem inventar; números continuam só os ditos.
- **Sincronia** (`render/motion_sincronia.py`): a cena entra na palavra que o LLM apontou; dentro
  dela, cada "batida" (item da lista, destino da rota, selo, carimbo, fim da barra dos marcos)
  entra na palavra que a diz — o número escrito nela ou a palavra mais longa —, e a que a fala não
  diz com essas letras entra num passo regular.
- **Cache** em `cortes/<n>/motion/cenas.json`, chave (início, fim, hash do texto), com cenas e
  descartadas; apagado quando o trecho é refeito ou por "Refazer motion". Sem cena válida: "nada
  neste trecho vira painel — use outro formato", com as descartadas no erro.

**Teste cego (2026-10-03),** `tests/test_render_lento_motion.py`, numa raiz temporária com
hardlinks (~3 min por corte, LLM + rosto + render):
- "400 mil reais em 10 anos" (c5xqNNWFT9w): capa (0–2,2), `valor_cheio` 400→550 mil com selo
  "10 ANOS" na palavra "10" (3,8–6,6), `chat` "Quanto que renderia isso na renda fixa?"
  (8,9–11,1), `lista` "Oportunidade"/"Localização" entrando nas palavras (20,0–23,8). Números
  corretos, painéis no tempo da fala, sem sobreposição com legenda nem rosto. Os primeiros 11 s
  ficam muito perto do manual. Onde perde: não fez o "PERDI DINHEIRO" (comparação) nem a rota
  Rio → Saquarema (a transcrição diz "saco arema"), deixando 8 s seguidos só de rosto; ~40% de
  motion contra ~60% do manual; o "+37,5%" do manual seria recusado pela regra.
- "Uber à noite pagou a dívida" (wxCto9WSZcI): capa, `valor_cheio` 1.200→1.500 ("mil e duzentos,
  mil e quinhentos") e `comparacao` 4,5 mil × 1.500 com carimbo "PAGOU A DÍVIDA" ("quatro pau e
  meio"). ~30% de motion.
- Defeito achado e corrigido: o GSAP lia o texto "1.500" como o número 1,5 e escrevia "1.5"; a
  contagem vai com um espaço de largura zero na frente. A primeira rodada saiu com 23–38% de
  motion, e o prompt passou a pedir cobertura (efeito pequeno na segunda rodada).
- Gosto, para o Davi: o rótulo da capa sai como tema ("Investimento imobiliário"), não o nome de
  quem fala (o prompt não recebe o nome); a escolha das cenas ainda é conservadora. Davi decide se
  segue.

**Melhora (2026-10-03, plano `2026-10-03-melhora-f3.md`), mesmo teste lento:**
- "400 mil reais em 10 anos": 6 cenas, **64%** de motion (antes 4 cenas, 40%; manual ~61%), 3,7
  trocas/10 s (antes 2,6; manual ~3,3). Capa "MAURÍCIO MEIRELLES" / "TIVE UM APARTAMENTO NO RIO";
  valor cheio 400→550 mil; chat; **comparação "PERDI DINHEIRO"** (R$ 550 mil × "mais") colada no
  chat; lista Oportunidade/Localização; **rota Rio de Janeiro → Saquarema** ("saco arema"). Uma
  chamada só bastou. Fica perto do manual do começo ao fim.
- "Uber à noite pagou a dívida": a cobertura varia de rodada para rodada (37% com 4 cenas, 52% com 5
  e capa "O DEPOIMENTO QUE MAIS RECEBO"; antes 30%): a fala de 1 a 11 s é conversa sobre
  depoimentos, sem nada mostrável, e a segunda chamada cobre o resto (lista "Uber à noite / Após o
  trabalho / Das 6h à meia-noite", 1.200→1.500, 4,5 mil em 3 meses, "PAGOU A DÍVIDA").
- Defeitos do render real corrigidos com teste: `fim_palavra` = nº de palavras (fim exclusivo)
  derrubava o corte inteiro — vira a última palavra, e o prompt diz o intervalo; capa com número
  dito depois de 2,2 s era recusada — a capa vale com o que o corte inteiro diz; cena esticada
  derrubava a seguinte — a que invade acaba antes (se ainda dura 1,5 s); lista que passava de 4 s
  deixava o último item 0,4 s — lista e rota acabam 0,6 s depois da última palavra e, longas,
  entram mais tarde; batida sem a palavra mais longa na fala entrava junto com a anterior — tenta
  as outras palavras e nunca entra junto; a capa copiava o título do episódio — o título vem do
  trecho.

## 8. Erros

Nada de fallback silencioso:
- Etapa com erro grava etapa, causa e arquivo no `estado.json`; o episódio mostra "tentar de novo".
- GPU sem memória na transcrição → para com "placa de vídeo sem memória para transcrever (feche
  o ComfyUI ou outro programa que usa a GPU e tente de novo)".
- DLLs do CUDA 12/cuDNN 9 ausentes → para com "instale nvidia-cublas-cu12 e nvidia-cudnn-cu12".
- Modelo `large-v3-turbo` fora do cache → para com o comando que o baixa uma vez com internet.
- Transcrição sem nenhuma palavra → para (não grava `palavras.json` vazio).
- Render que falha mantém a versão anterior e mostra o fim do log.
- Processo do render (ffmpeg, detector de rosto, HyperFrames) tem timeout de 20 min; ao vencer,
  mata a árvore de processos (não só o processo-pai) e falha a etapa com a causa.
- "Renderizar" manual é recusado quando a etapa `render` do episódio já está em erro — reenfileirar
  por cima de uma etapa quebrada escondia a causa; é preciso corrigir e tentar de novo primeiro.
- Cota do Claude → fila pausada com aviso.
- Configuração ausente (Python do rosto, HyperFrames, ffmpeg) → o servidor não sobe e diz o que falta.

## 9. Testes

Funções puras com teste: conversão dos segmentos do faster-whisper em palavras (segmentos
falsos, sem GPU); máquina de estados da fila e retomada; grupos de
legenda; quadro fixo por plano; seleção de rosto por plano; aplicação das edições do
`corte.json`; montagem do `index.html` (placeholder sobrando = erro); schemas de deixas e de
cenas; gravação dos exemplos bons/ruins. O que precisa da GPU ou de minutos (transcrição de
verdade, render ponta a ponta) é marcado `lento` e fica fora do check padrão (`addopts = -m
"not lento"` no `pyproject.toml`; rodar com `pytest -m lento`).

## 10. Riscos

- **Direitos:** cortes de podcast e B-roll do YouTube são de terceiros (spec principal §14);
  f4 marca risco alto de Content ID por visual. A foto de reserva do f4 vem da busca de imagens
  do DuckDuckGo: fotos de loja e de terceiros, com `fonte_url` e `licenca: desconhecida` (§11).
- **YouTube sujeito a bloqueio no B-roll:** o vídeo inteiro (15 s a 3 min) vem em ~10 s pelo
  downloader nativo; antes, a seção pelo ffmpeg levava ~45 s e estourava o prazo em metade dos
  casos (§11). 403/429 tiram o YouTube da rodada.
- **Transcrição automática erra nomes e números** — o editor (plano C) corrige; até lá, o
  render usa a transcrição como veio.
- **GPU dividida:** o modelo só ocupa a placa durante a transcrição, mas o ComfyUI rodando
  junto pode deixar faltar memória nesse momento (erro claro, §8).
- **Render de 1–4 min por Short:** N=5 → 10–20 min por episódio, em segundo plano.
- **Detecção de rosto em CPU** pelo venv do ComfyUI: dependência externa, verificada na subida.
- **Qualidade do f3 automático** é a maior incerteza — por isso o teste cego antes de seguir
  (§7: números e tempo certos, mas menos cenas que o manual).

## 11. f4 B-roll automático

Decisões do Davi em 2026-10-03 (plano `2026-10-03-broll-automatico.md`): quando a pessoa fala de
uma coisa concreta ou de um acontecimento, o Short corta seco para um clipe de 1,5 a 3 s que mostra
aquilo **em tela cheia** e volta para ela. A fonte principal é **vídeo do YouTube**. Sem vídeo que
passe na conferência, entra **foto** do DuckDuckGo, mas só na deixa de coisa (`literal`), nunca no
acontecimento. É o f4 B-roll do plano D (§6), agora automático, e **substitui o f9 Ilustrado**
(cartão de foto do plano `2026-10-02-ilustrado.md`, de 2026-10-02), que deixou de existir.

Etapa do corte, só no f4, antes do `index.html`:

1. **Deixas:** `claude -p` com schema lê a fala numerada do corte (já sem pausas e com as edições)
   e devolve `{inicio_palavra, fim_palavra, coisa, busca, tipo}`, até 12.
   - `tipo: "literal"` é a coisa citada (Vans, camisa do Corinthians); `"acontecimento"` é a cena
     que a fala evoca ("a pandemia" → rua vazia; "fui de jatinho" → jato decolando). A busca do
     acontecimento pode ser em inglês quando render mais vídeo.
   - Nada abstrato, nem peça ou característica de produto descrita de forma vaga ("negócio que
     evita torção", "sola ultra resistente"): só a coisa inteira e nomeável. Cada coisa entra uma vez só, sem busca genérica para uma coisa específica já
     citada ("a camiseta" depois de "camisa do Corinthians" trouxe a camisa da seleção no render
     de 2026-10-02).
   - **Ritmo no prompt e no código** (`ilustracao.deixas_do_corte`): nada no primeiro 1 s (gancho
     com o rosto); cada clipe de 1,5 a 3,0 s; pelo menos 1,5 s de rosto entre um clipe e o próximo;
     somados, no máximo 60% do Short (R2, pista). Passou de 60%: saem as últimas, as do meio não
     são encurtadas. Índice de palavra ou tipo inválido é resposta errada (erro), não deixa
     descartada em silêncio.
2. **Candidatos por deixa** (`broll_candidatos.py`), sempre **em série**, nunca em paralelo no
   YouTube:
   - **2 vídeos:** `yt-dlp ytsearch15:` filtrado para 15 s a 3 min, os 2 primeiros. De cada um
     baixa o **vídeo inteiro** pelo downloader nativo do yt-dlp (sem `--download-sections`), até
     1080p, só vídeo, com `--max-filesize 120M` e prazo de 45 s; o ffmpeg tira localmente 3 s a
     partir de 25% da duração (passa da vinheta) em 1080×1920 em **cover** com corte central (o
     16:9 preenche a tela), gravando por `.parcial`. O vídeo baixado é apagado sempre; se o Windows
     não deixa apagar, isso vira nota no erro original ou, sem erro, `ErroRender` com o caminho.
     Id validado (`^[A-Za-z0-9_-]{11}$`), argumentos em lista, sem shell.
   - **2 fotos**, só na deixa literal: busca ddgs, download pelo ffmpeg com os limites do f9
     (só `http`/`https`, só demuxers de imagem, `-max_pixels`, prazo de 30 s por foto). A foto
     escolhida vira um 1080×1920 com a imagem inteira (contain) sobre ela mesma desfocada e
     escurecida — o produto não é cortado (mesma ideia do f8).
   - **YouTube fora da rodada no primeiro bloqueio:** a primeira busca que falha, ou um 429 / "não
     é um robô" na saída do yt-dlp, marca o YouTube como fora; as deixas seguintes nem tentam e
     ficam transitórias (a foto ainda cobre a literal). Nada é repetido em laço (§8: o IP já foi
     bloqueado uma vez). No download, o downloader nativo diz `unable to download video data: HTTP
     Error 403: Forbidden` (ou 429): os dois contam como bloqueio — o 403 da googlevideo vale para a
     sessão (URL sem PO Token ou estrangulada), não para um vídeo.
   - **yt-dlp quebrado não é "temporário":** na busca, só prazo, bloqueio e sinal de rede
     (`Unable to download`, `urlopen error`, `timed out`, ...) viram falha transitória; outro código
     diferente de 0 (módulo ausente, extractor quebrado) derruba o corte com a mensagem do yt-dlp.
   - **Candidatos guardados antes da conferência** (`ilustracao/candidatos.json`, mesma chave e
     mesma deixa, arquivos ainda no disco): erro na folha ou na conferência (ErroLLM) não faz buscar
     e baixar de novo na próxima rodada. Apagado quando a conferência responde.
3. **Conferência:** os candidatos viram **folhas mistas** — uma linha por deixa, tiles `D<k>-V<j>`
   (3 quadros do trecho: início, meio e fim) e `D<k>-F<j>` (a foto), rótulo numa faixa acima de
   cada tile — com **até 4 deixas por folha** (com 2 vídeos + 2 fotos a linha fica larga; 6
   deixas deixavam o quadro ilegível depois que o modelo reduz a imagem). **Uma chamada só** por
   corte confere todas as folhas e devolve, por deixa, `V<j>`, `F<j>` ou `null`. O prompt manda
   **preferir vídeo** quando ele mostra a coisa, recusar vídeo em que a coisa aparece num quadro só
   ou que é alguém falando para a câmera, e foto só na literal. Read preso à pasta das folhas como
   no f9 (`--tools Read`, `--permission-mode dontAsk`, `permission_denials` vira `ErroLLM`).
4. **Montagem** (`render/formatos/broll.tpl`, base do f7): cada deixa com visual vira um
   `<video class="clip broll">` (ou `<div class="clip broll"><img>`) em tela cheia, que aparece e
   some **seco** — sem Ken Burns, sem flash, sem zoom, sem opacidade gradual. A legenda continua
   por cima. Clipe que sobraria menos de 0,3 s antes do fim do Short não entra.
5. **Sem visual:** a deixa sem candidato aprovado fica **"sem visual"**, com o motivo, visível no
   editor; nunca entra um visual qualquer. A foto escolhida que o ffmpeg não monta em tela cheia
   também fica "sem visual" com o motivo (não transitória). Se nenhuma deixa ganhou visual, o corte para em erro:
   "nada a mostrar em B-roll" (guardado, não refaz sozinho) ou, se alguma falha foi transitória,
   "falha temporária do YouTube ou da busca de fotos — tente de novo mais tarde" (refeita no
   próximo render).

Cache em `cortes/<n>/ilustracao/` (§4.3), formato 4 (o cache do f9 é refeito), com chave
(início, fim, hash do texto): `deixas.json` evita chamar o Claude de novo, e só as deixas
transitórias são buscadas outra vez. Cada entrada guarda `coisa`, `busca`, `tipo`, tempos, `midia`
(`video`/`foto`/null), arquivo, `motivo`, `falhas` e a fonte: no vídeo `fonte_url`, `canal`,
`titulo`, `licenca: desconhecida (YouTube)` e `risco: alto`; na foto `fonte_url` (página de
origem) e `licenca: desconhecida`. Trocar o formato ou editar a legenda sem mudar o texto não refaz
a busca. Os nomes internos seguem `ilustracao*` (renomear custava caro e não muda nada para o
Davi); na tela é "B-roll".

**f9 removido:** saiu de `montagem.FORMATOS` e de `contas/formatos.yaml` (`f4` passou a
`no_app: "plano B"`), `ilustrado.tpl` virou `broll.tpl`, e um `corte.json` com `formato: "f9"` dá
erro claro no render ("o formato f9 virou o f4 B-roll; renderize de novo em f4"), sem conversão
silenciosa. Pedir f9 no app (episódio novo, renderizar, edição) dá a mesma mensagem
(`montagem.validar_formato`).

**Editor:** a seção "B-roll" mostra, por deixa, o tipo (vídeo, foto ou sem visual), a miniatura (um
quadro do vídeo ou a foto) e o motivo, e tem o botão "Refazer B-roll". O link da fonte mostra o
canal do vídeo e só sai com `http`/`https`. Trocar ou tirar um clipe à
mão fica para depois.

**Tempo do vídeo (medido em 2026-10-03, segunda rodada):** o vídeo inteiro pelo downloader
nativo resolveu o gargalo.
- Vídeo inteiro só-vídeo 1080p: 71 s/38 MB em 9 s (controlador); 96 s/43,8 MB em 9,7 s mais
  2,4 s do ffmpeg dos 3 s (conferência isolada, 2 requisições). Prazo: 45 s. O cliente
  `android_vr` não serve (exige PO Token, 403).
- **Render real de novo** (mesmos 2 cortes, depois das mudanças desta seção): 270 s e 377 s por
  corte (eram 769 s e 935 s); YouTube somado (busca + downloads + ffmpeg dos trechos, quadros e
  foto cheia) 45 s e 68 s para 6 e 7 vídeos baixados. Nenhum estouro de prazo, nenhum 429/403;
  2 vídeos "This video is not available". Deixas: 120 s numa chamada do LLM (a outra, 32 s).
- Resultado: 7 clipes, **4 de vídeo e 3 de foto** (eram 2 e 5). A deixa vaga da peça da bota
  sumiu. Visto nos quadros do MP4: Corinthians, Macboot, moto trocando marcha e Vans em vídeo;
  camisa do São Paulo, boné New Era e All Star em foto; entra e sai seco, rosto entre os clipes.
  Ainda falha: o vídeo da Macboot tem um quadro de paisagem no meio dos 3 s (a conferência viu
  isso na folha e aprovou), e "fazer comercial" (acontecimento) ficou sem visual — só 1 vídeo
  entre 15 s e 3 min na busca, e ele era texto.

**Tempo do trecho (medido em 2026-10-03, primeira rodada, histórico):**
- `yt-dlp --download-sections` leva ~43 s por trecho, igual com ou sem recodificar e em 1080p ou
  720p; o 720p sai mole no 1080×1920, então fica 1080p. Prazo do trecho: 90 s.
- **URL direta não acelera:** `yt-dlp -g` leva 2,5–3,7 s, mas `ffmpeg -ss <ini> -i <url>` passou
  de 90 s sem gravar nada, com e sem os cabeçalhos do yt-dlp — é o mesmo caminho que o yt-dlp usa
  na seção. Ficou o caminho do yt-dlp.
- **Causa provável, não confirmada:** sem runtime JS o yt-dlp avisa (escondido por
  `--no-warnings`) que não resolve o desafio "n" do YouTube, e a URL vem estrangulada. Com
  `--js-runtimes node` e o pacote `yt-dlp-ejs` (dependência nova, fora do venv) a URL deu 403 no
  único teste; não insisti para não arriscar bloqueio. Fica para investigar.
- **Render real** (episódio `wxCto9WSZcI`, 2 cortes): 769 s e 935 s por corte, dos quais ~400 s
  no YouTube (8 trechos por corte). 7 dos 16 trechos estouraram os 90 s (outros 2 falharam: vídeo indisponível e seção sem vídeo); nenhum 429.

**Render real de 2026-10-03, primeira rodada** (cortes "Camisa de 700 reais, sério?" e "Bota boa por 250, não
600"): 7 clipes, 2 de vídeo e 5 de foto; nos quadros o clipe mostra a coisa, entra e sai seco e o
rosto volta entre um clipe e outro. A foto domina porque metade dos vídeos não baixou no prazo e a
conferência recusou vídeo com texto grande ou com a coisa num quadro só. Um "negócio que evita
torção" (peça de uma bota) virou foto de bota de motociclista: deixa vaga demais para buscar.
