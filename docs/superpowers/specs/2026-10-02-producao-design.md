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

Upload de vídeo do PC, transcrição por arquivo enviado e Whisper pelo painel (o Whisper segue
no `cortes detectar` do terminal); formatos f2, f5, f6, f8; publicação automática; nicho humor.

## 2. Decisões

| Decisão | Escolha | Motivo |
|---|---|---|
| Entrada | Só link do YouTube | Davi escolheu; cobre os podcasts-fonte |
| Transcrição | Legenda do YouTube (json3), sem Whisper | Whisper é lento; a legenda tem tempo por palavra e pontuação (conferido, §4.2) |
| Render | Automático nos N melhores (padrão 5) + "Renderizar" manual nos demais | Como o Opus; rejeição vira exemplo para o detector |
| Formatos | f7 Conversa, f1 Falante, f4 B-roll, f3 Motion | Davi escolheu; f7 é o sinal mais forte da R2, f4/f3 os que ele mais gostou |
| Motor de render | **HyperFrames**, não Remotion | Os 8 formatos testados e aprovados foram feitos nele (`testes/`); substitui a decisão "Remotion" da spec principal §5 |
| Nota mostrada | Nota do detector (0–10) com a rubrica aberta | Explica o porquê, em vez de "viralidade" opaca |
| Execução | Uma fila, um trabalho por vez | GPU, cota do Claude e CPU do render são únicos |
| Entrega | Uma spec, 5 planos em ordem (A→E) | Cada plano entrega algo usável; f3 por último por ser o mais arriscado |

## 3. Planos

| Plano | Entrega | Risco |
|---|---|---|
| **A. Produção** | Link → vídeo + legenda do YouTube → detector, com progresso por etapa; candidatos com nota, rubrica, justificativa e player do trecho | baixo |
| **B. Render f1 + f7** | N melhores renderizados sozinhos; grade de Shorts; aprovar/rejeitar (→ exemplos); baixar MP4 | baixo — o código existe nos protótipos |
| **C. Editor** | Início/fim por palavra, texto da legenda, título, troca de formato, quem aparece por plano, versões | médio (multirrosto) |
| **D. f4 B-roll** | Deixas pelo Claude → busca no YouTube → conferência visual → 3 opções por deixa no editor | médio |
| **E. f3 Motion** | Biblioteca de componentes + cenas em JSON pelo Claude; teste cego contra o f3 manual | alto |

## 4. Arquitetura

### 4.1 Código

```
src/cortes/producao/
  fila.py          # fila única, uma thread; estados; retomada após reinício
  legenda_yt.py    # json3 do YouTube → list[Palavra] (puro) + download fino
  etapas.py        # baixar → legenda → sinais → detector → render dos N
  rotas.py         # API da Produção (montada no servidor do painel)
src/cortes/render/
  recorte.py       # trecho.mp4 (ffmpeg), cortes de pausa
  rosto.py         # rostos por quadro (até 3) + trocas de câmera
  legenda.py       # grupos de legenda (puro), aplicação das edições
  montagem.py      # plano de corte → index.html a partir do template (puro)
  hyperframes.py   # projeto, render, log (executor injetável)
  broll.py         # plano D
  cenas.py         # plano E
render/formatos/   # falante.tpl, conversa.tpl, broll.tpl, motion.tpl (no git)
render/componentes/# plano E: componentes parametrizados
```

O que os protótipos em `testes/comum/` fazem (`corte.py`, `rosto.py`, `rodada.py`,
`buscar_broll.py`, `formatos/*.tpl`) é portado com o episódio como parâmetro. `testes/` fica
como histórico da rodada de formatos. O caminho do Python com onnxruntime (hoje o venv do
ComfyUI) vira configuração com verificação na subida, como a skill no painel de contas.

### 4.2 Legenda do YouTube

Conferido em 2026-10-02 no PrimoCast 536 (`c5xqNNWFT9w`): `yt-dlp --skip-download
--write-auto-subs --write-subs --sub-langs pt --sub-format json3` baixou 2,1 MB em < 1 s;
20.234 palavras (Whisper: 19.752), com pontuação (1.425 fins de frase), tempo de início por
palavra (`tStartMs` do evento + `tOffsetMs` do segmento). Regras:

- pede **só** a faixa `pt` original (a tradução `pt-PT` levou HTTP 429);
- legenda manual tem preferência sobre a automática quando existir;
- descarta marcas entre colchetes (`[música]`, `[aplausos]`);
- fim de cada palavra = início da seguinte (limitado a 1,5 s), em todo o episódio — não só
  dentro do evento;
- sem faixa `pt` → o episódio para com "vídeo sem legenda em português no YouTube";
- marcas de troca de locutor (`>>`) e palavrões censurados (`[ __ ]`) são descartados; o
  YouTube começa a palavra ~0,2–0,4 s depois do Whisper (dar folga na borda inicial do corte,
  plano B);
- **transcrição colada** (saída quando o YouTube bloqueia o download com HTTP 429): na entrada,
  Davi pode colar o texto de "Mostrar transcrição" — linha de tempo (`0:10`, `1:00:03`) seguida
  do texto do bloco, em uma ou mais linhas. A API valida (parse completo, até 5 MB, mínimo 50
  palavras; erro diz a linha) antes de criar o episódio e grava `transcricao.txt`; a etapa
  legenda usa esse arquivo em vez de baixar (`producao/transcricao_colada.py`). Só o início do
  bloco (~5–7 s) tem tempo: as palavras são distribuídas no bloco pelo tamanho (mesma regra da
  legenda manual), o último bloco dura nº de palavras × 0,35 s (~2,8 palavras/s). Precisão por
  palavra estimada em ~±0,3 s — basta para achar momentos; para a legenda queimada do plano B,
  considerar refinar (alinhamento forçado com o áudio ou Whisper só no trecho do corte).

### 4.3 Dados por episódio

```
episodios/<id>/
  video.mp4  audio.wav  meta.json  palavras.json  sinais.json  candidatos.json   (já existem)
  estado.json        # etapas: pendente | rodando (progresso) | ok | erro (causa, arquivo)
  cortes/<n>/
    corte.json       # candidato de origem, início/fim, formato, título, edições de legenda,
                     # escolhas de rosto/B-roll/cenas, status: na_fila | renderizando |
                     # pronto | aprovado | rejeitado (+ motivo), versão atual
    projeto/         # projeto HyperFrames
    short-v<k>.mp4   # versões; a anterior é mantida
```

O `corte.json` guarda o título: a sugestão de corte do painel de contas (aba Shorts) passa a
casar cortes de episódio pelo título, e não só as pastas de `testes/` (`ligacao.py` lê o
`corte.json`; limite registrado no painel de contas some).

### 4.4 Fila

- Trabalhos: `processar_episodio(id)` e `renderizar(id, n, versão)`. FIFO, uma thread.
- Cada etapa grava seu arquivo e é pulada se ele existe (padrão do `cortes detectar`).
- Ao subir, o servidor relê os `estado.json` e recoloca na fila o que estava `rodando`.
- O detector termina enfileirando o render dos N melhores no formato escolhido na entrada.
- Cota do Claude atingida → a fila **pausa** e a tela avisa; não descarta trabalhos.

### 4.5 Curadoria e retorno ao detector

Aprovar grava o trecho em `nichos/<nicho>/exemplos/bons.jsonl`; rejeitar pede o motivo
(lista fixa + texto livre) e grava em `ruins.jsonl` — o mesmo formato que o detector já lê.

## 5. Telas (mockup aprovado)

Trilho com dois grupos: **Produção** (Episódios) e **Retorno** (Contas, Shorts, Comparar). No
rodapé do trilho, a fila: o que roda agora, com progresso, e quantos esperam.

**Episódios**
1. Entrada: link, nicho, formato padrão (f7/f1; f4/f3 quando os planos D/E existirem), quantos
   renderizar (3/5/10), "Gerar Shorts". Link sem id de vídeo ou já processado → recusa com motivo.
2. Lista de episódios: capa, título, canal, duração, barra de 5 etapas (vídeo, legenda, sinais,
   momentos, render k/N) com estados ok/rodando/erro; erro mostra a causa e "tentar de novo".
3. Episódio selecionado: grade de Shorts 9:16 (nota 0–10, status, prévia, título, duração,
   formato, ✓ ✕ Editar); tabela "Outros candidatos" (nota, início, duração, título,
   justificativa, "Renderizar").
4. Painel do Short: player, as 5 notas da rubrica em barras, justificativa, tags de bônus,
   aprovar/rejeitar/editar, baixar MP4, copiar título.

**Editor** (plano C), três colunas:
- **Prévia 9:16** no próprio navegador (o formato é HTML do HyperFrames; o plano C confirma a
  reprodução no navegador como primeira tarefa — se não der, prévia por render rascunho em
  resolução/fps reduzidos). "Renderizar" gera o MP4 final.
- **Transcrição** em volta do corte, palavra a palavra: clicar move início/fim (sempre por
  palavra); a regra de início do detector avisa quando o início depende de contexto. Grupos de
  legenda editáveis; botão de mascarar palavrão (só na legenda).
- **Ajustes:** título; formato (gera versão nova); **quem aparece** — linha do tempo dos planos
  de câmera com as miniaturas dos rostos de cada plano, clique escolhe quem fica na tela
  (padrão: o rosto mais confiável); no f4, as opções de B-roll por deixa; no f3, as cenas.

## 6. B-roll (plano D)

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

- Os painéis feitos à mão em `testes/short-400mil-dinamica/modelo.tpl` viram componentes
  parametrizados: contador de valor (já existe no registry do HyperFrames), barra de
  progresso, lista numerada, mapa de rota, card de número grande, caixa de chat.
- `claude -p` devolve **JSON validado por schema** (componente, parâmetros, início, duração) —
  nunca HTML. O código monta a timeline; números na tela só os ditos na fala ou calculados
  deles (regra dos testes).
- Primeira tarefa: teste cego, f3 automático × f3 manual no mesmo corte. Davi decide se segue.

## 8. Erros

Nada de fallback silencioso:
- Etapa com erro grava etapa, causa e arquivo no `estado.json`; o episódio mostra "tentar de novo".
- Sem legenda `pt` → para (não cai no Whisper escondido).
- HTTP 429 do YouTube → para com "YouTube limitou as requisições; tente em alguns minutos" (sem
  repetição em loop — o IP já foi bloqueado uma vez na pesquisa).
- Render que falha mantém a versão anterior e mostra o fim do log.
- Cota do Claude → fila pausada com aviso.
- Configuração ausente (Python do rosto, HyperFrames, ffmpeg) → o servidor não sobe e diz o que falta.

## 9. Testes

Funções puras com teste: parser do json3 (amostra real recortada do PrimoCast 536, com
`[música]`, pontuação e fim de evento); máquina de estados da fila e retomada; grupos de
legenda; quadro fixo por plano; seleção de rosto por plano; aplicação das edições do
`corte.json`; montagem do `index.html` (placeholder sobrando = erro); schemas de deixas e de
cenas; gravação dos exemplos bons/ruins. Render ponta a ponta: um teste marcado `lento`, fora do
check padrão (`pytest -m "not lento"` no `CLAUDE.md`).

## 10. Riscos

- **Direitos:** cortes de podcast e B-roll do YouTube são de terceiros (spec principal §14);
  f4 marca risco alto de Content ID por visual.
- **Legenda automática erra nomes e números** — o editor (plano C) corrige; até lá, o render
  usa a legenda como veio.
- **Render de 1–4 min por Short:** N=5 → 10–20 min por episódio, em segundo plano.
- **Detecção de rosto em CPU** pelo venv do ComfyUI: dependência externa, verificada na subida.
- **Qualidade do f3 automático** é a maior incerteza — por isso o teste cego antes de seguir.
