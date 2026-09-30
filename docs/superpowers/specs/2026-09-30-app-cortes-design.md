# App de Cortes — Design

Data: 2026-09-30 · Autor: Davi (com Claude) · Status: aguardando revisão

## 1. Objetivo

Ferramenta **local** que transforma episódios de podcast em Shorts verticais prontos para
postar, para alimentar canais próprios de cortes por nicho. Começa pelo nicho de
**finanças (PT-BR)**; o segundo nicho é **humor**.

O app faz duas coisas, nesta ordem de importância (a pesquisa mostrou que a primeira
pesa mais):

1. **Achar o momento** que merece virar corte.
2. **Editar** o corte com um template que a evidência diz que funciona.

### Modo de operação (decisão C)

- **Fase 1 — curadoria:** o app sugere candidatos com nota e justificativa; Davi aprova,
  ajusta início/fim ou rejeita com motivo. Só o aprovado é renderizado.
- **Fase 2 — automático:** quando as notas do app baterem com as aprovações de Davi,
  liga-se o modo que renderiza sozinho os N melhores. O critério de "bater" está em §11.

### Fora do escopo da v1

Publicação automática, interface multiusuário, nuvem, nicho de humor (vem depois com
pesquisa própria), gráficos animados de finanças (entram na v1.1 — ver §15).

## 2. Base de evidência

Tudo que é regra de corte ou de edição vem destes documentos, e cada parâmetro dos
templates cita de onde veio:

- `pesquisa/01-pesquisa-documental.md` — literatura, com nível de evidência por afirmação.
- `pesquisa/02-corpus-financas.md` — rodada 1: 72 shorts, 6 canais, top × fundo, cego.
- `pesquisa/03-corpus-financas-r2.md` — rodada 2: 247 shorts, 12 canais escolhidos por
  desempenho, top × meio × fundo, só shorts com mais de 60 dias, cego. Responde o que leva
  um corte **mediano** ao topo.

Achados que sustentam o design (R1 + R2 + literatura):

| Achado | Força | Vira |
|---|---|---|
| Gancho forte nos 3 s e corte autocontido separam top de fundo | 6/6 canais | Rubrica do detector (§6.4) |
| Começar no meio da frase é o erro nº 1 dos fracassos (12 × 4) | forte | Regra dura de início (§6.4) |
| Espanto separa (9 × 0); utilidade pura fracassa (8 × 14) | forte | Peso da rubrica |
| Mais trocas de plano (confirmado top × meio) | R1 5/6 · R2 9×3 | Ritmo-alvo do template |
| **Mostrar a outra pessoa da conversa** separa top de meio | R2 10×1 | Planos de reação (§6.5) |
| Zoom variado **não** separa top de meio | R2 3×7 (R1 dizia o contrário) | Zoom vira opcional |
| Destaque colorido na legenda é mais comum quanto pior o grupo | R1 + R2 (35·48·65%) | Legenda sem destaque |
| Motivacional puro e palestra rendem menos; humor, número e famoso rendem mais | R2, pista | Bônus/penalidade do perfil |
| Vídeo de retenção (satisfatório) sem efeito; acontecimento e gráfico com pista positiva | R2 | Tipos de visual do template |
| Título fixo o vídeo todo associado ao fundo | 3/6 contra | Template não usa |
| Visual literal sincronizado com a fala gera o ritmo (exemplo Hype Automotivo, 25 mi) | caso | Buscador de cenas (§8) |
| Canal de nicho viraliza cortando podcast genérico | caso + padrão "quanto ganha" | Filtro de nicho em qualquer podcast (§6.4) |
| Só transcrição é pior que áudio + texto para achar momento | dado medido (Rhapsody) | Sinais de áudio (§6.3) |

## 3. Conceitos

**Perfil de nicho** — *o que cortar*. Um arquivo por nicho.
**Template de edição** — *como editar*. Um ou mais por nicho (permite teste A/B).
**Plano de corte** — o JSON que descreve um Short inteiro (linha do tempo completa). É o
contrato entre quem decide (montador) e quem executa (render).

Separar os três permite: trocar o renderizador sem mexer na decisão; saber, quando um
Short sai ruim, se o erro foi de escolha (plano) ou de execução (render); e testar
dois templates no mesmo corte.

## 4. Formatos

### 4.1 Perfil de nicho (`nichos/<nicho>/perfil.yaml`)

```yaml
nicho: financas
filtro_tema: "O trecho é sobre dinheiro: ganhar, perder, gastar, investir, salário, preço, patrimônio, economia."
rubrica:            # pesos somam 1; cada critério é nota 1-5 dada pelo LLM
  gancho_3s: 0.30
  autocontido: 0.25
  espanto: 0.20
  historia_ou_virada: 0.10
  fechamento: 0.15
bonus:              # tag: descrição que o LLM lê (sem descrição ele adivinha o sentido)
  numero_na_primeira_frase: "a primeira frase do trecho traz um número ou valor concreto"
  dinheiro_alheio_quanto_ganha: "revela quanto alguém ganha, cobra, gasta ou tem"
  humor: "o trecho faz rir (piada, reação engraçada, situação cômica)"
  personagem_famoso_citado: "cita pelo nome um político, bilionário ou celebridade"
penalidade: {}      # mesmo formato; vazia em finanças (utilidade/motivacional já pesam via 'espanto')
duracao_s: {min: 20, max: 90}
exemplos_bons: exemplos/bons.jsonl    # trechos aprovados (cresce com a curadoria)
exemplos_ruins: exemplos/ruins.jsonl  # rejeitados + motivo
fonte: {rubrica: "02 §1-2 + 03 (8×4)", bonus_penalidade: "03 §emoção/formato (pista)", duracao: "01: sem duração mágica"}
```

### 4.2 Template de edição (`nichos/<nicho>/templates/<nome>.yaml`)

```yaml
nome: financas-falante-v1
layout_base: falante_reenquadrado
estados_permitidos: [falante_cheio, reacao_ouvinte, dividido_visual_topo, visual_cheio]
ritmo_alvo_trocas_por_10s: 0.7          # top R2 = 0.62, top R1 = 0.83
reacao_ouvinte: {ativo: true, min_por_corte: 1}   # R2: 10×1 canais
visual_externo:
  tipos: [acontecimento, grafico_ou_dado, literal, gerado_ia]   # ordem = prioridade; retencao desligada (R2: sem efeito)
  exigir_sincronia: true
  fracao_max_tempo: 0.6                   # R2: >50% do tempo = 33% top · 27% meio · 20% fundo (pista)
legenda: {estilo: sem_destaque, posicao: centro_ou_terco_inferior, max_palavras: 8}
zoom_punch: {ativo: false, gatilho: "frase de pico de energia ou marcada pelo LLM", escala: 1.15}  # R2: não separa top de meio
capa: {ativa: true, duracao_s: 2.5, conteudo: "título curto + imagem do assunto"}
titulo_fixo: false                        # R1 negativo, R2 neutro
fonte:                                    # uma entrada por parâmetro
  ritmo_alvo_trocas_por_10s: "02 §3 (5/6) + 03 (9×3)"
  reacao_ouvinte: "03 (10×1)"
  legenda: "02 §4 + 03 (destaque 35·48·65%)"
  zoom_punch: "03 (3×7, derruba R1)"
  visual_externo: "03 §visual externo (pista)"
```

### 4.3 Plano de corte (`episodios/<id>/cortes/<n>/plano.json`)

Validado por JSON Schema (`schemas/plano.schema.json`). Campos:

- `origem`: episódio, `inicio_s`, `fim_s` no vídeo original.
- `template`: nome + versão.
- `faixas` (tempo relativo ao corte, em segundos):
  - `layout[]`: `{de, ate, estado, falante_id?, visual_id?}`
  - `crop[]`: trilha do recorte 9:16 do falante `{t, x, y, escala}` (amostrada a 10 Hz).
  - `legenda[]`: `{de, ate, texto}` (palavras agrupadas pelo template).
  - `zoom[]`: `{de, ate, escala}`.
  - `capa?`: `{ate, titulo, visual_id}`.
- `visuais[]`: `{id, tipo, arquivo, fonte_url, licenca, risco}` — risco ∈ `baixo|medio|alto`.
- `audio`: normalização alvo (-14 LUFS).

## 5. Arquitetura

**Abordagem B (decidida):** análise em Python, render em HTML/React com **Remotion**
(Davi já usa no ChessDirector; maduro para render em lote; React facilita gráfico
animado). Qualidade acima de economia.

Módulos, cada um lê e grava arquivos em `episodios/<id>/` (pipeline retomável):

| Módulo | Entra | Sai |
|---|---|---|
| `ingestao` | URL | `video.mp4` (1080p), `audio.wav`, `meta.json` |
| `transcricao` | áudio | `palavras.json` (tempo por palavra), `falantes.json` |
| `sinais` | áudio | `sinais.json` (energia, ritmo, risada por janela de 0,5 s) |
| `detector` | transcrição + sinais + perfil | `candidatos.json` (nota, justificativa, título sugerido) |
| `curadoria` | candidatos | `aprovados.json` + motivos → `exemplos/*.jsonl` |
| `visao` | vídeo + trecho | `rostos.json` (trilha de cada rosto, falante ativo) |
| `cenas` | transcrição do corte | `deixas.json` + `visuais/` com fonte e licença |
| `montador` | tudo acima + template | `plano.json` |
| `render` | plano | `short.mp4` 1080×1920 |
| `retorno` | métricas dos Shorts postados | ajuste proposto de perfil/template |

Estrutura do repositório:

```
cortes/
  src/cortes/     # Python: um módulo por etapa + llm.py + cli.py
  render/         # Remotion (TypeScript): composições por estado de layout
  web/            # curadoria (FastAPI + página estática)
  nichos/financas/{perfil.yaml,templates/,exemplos/}
  schemas/        # JSON Schemas: candidatos, plano, deixas
  biblioteca/     # vídeos de retenção baixados uma vez (Pexels/Pixabay)
  episodios/      # dados de trabalho (fora do git)
  pesquisa/       # documentos e corpus da pesquisa
```

Local proposto: `C:\Users\User\Documents\Vibe Code\Cortes\`.

## 6. Módulos

### 6.1 Ingestão
yt-dlp em 1080p; se só houver formatos restritos, tenta cliente `android_vr` (aprendido
na pesquisa). Ritmo baixo de requisições (o YouTube bloqueou o IP por excesso). Grava
`meta.json` (título, canal, duração, data).

### 6.2 Transcrição e falantes
faster-whisper `large-v3` na GPU, tempo por palavra, `pt`. Diarização com pyannote
(modelo exige aceite de termos no HuggingFace — passo manual único de Davi). Saída:
palavras com `falante_id`.

### 6.3 Sinais de áudio
Por janela de 0,5 s: energia RMS, taxa de fala, pausa, e detector de risada (usado no
humor; em finanças só vira sinal auxiliar). Picos de energia marcam candidatos a zoom.

### 6.4 Detector
1. **Segmentação** em unidades de ideia: frases completas agrupadas por pausa e troca
   de assunto.
2. **Regra dura de início:** um candidato não pode começar em frase que dependa de
   contexto anterior (conectivo inicial — "mas", "também", "e aí", "só que" —, pronome
   sem referente no trecho). Implementada em código + confirmada pelo LLM.
   “Então” fica de fora da regra dura de propósito: em PT-BR falado costuma abrir história ("Então, eu vendi a casa").
3. **Pontuação** via `llm` (§7): uma chamada por episódio com a transcrição inteira
   segmentada, o perfil e os exemplos bons/ruins; devolve até 20 candidatos com nota
   por critério da rubrica, `filtro_tema` (sim/não — permite cortar podcast genérico),
   justificativa, título sugerido e início/fim.
4. **Nota final** = soma ponderada da rubrica + bônus/penalidades + ajuste pelos sinais
   de áudio (energia na abertura). Ordena e grava.

### 6.5 Visão
Detecção e trilha de rostos (MediaPipe) a 10 Hz. Falante ativo = rosto cuja movimentação
da boca correlaciona com o `falante_id` da diarização naquele intervalo. Recorte 9:16
centrado no falante ativo, com suavização (sem tremer) e troca de falante com corte seco.
**Planos de reação:** marca intervalos em que o ouvinte reage (expressão, riso, gesto) enquanto
o outro fala; o montador usa esses planos para cumprir `reacao_ouvinte` — o sinal mais forte
da R2 entre top e meio. Em podcast multicâmera o plano do ouvinte vem da própria edição
original; em plano único com duas pessoas, sai do crop do rosto do ouvinte.

### 6.6 Montador
Converte corte aprovado + template em `plano.json`: agrupa legenda, distribui estados de
layout nos trechos com deixa visual, aplica zoom nos picos, respeita `ritmo_alvo` e
`fracao_max_tempo`, monta a capa. Função pura (mesma entrada → mesmo plano).

## 7. LLM pela assinatura (sem API paga)

Decisão: usar a assinatura do Claude Code via CLI, não a API.

```
claude -p --output-format json --json-schema <schema> --tools "" \
       --no-session-persistence --model <modelo>
```

- Resposta em `structured_output`, validada pelo schema. `is_error: true` ou JSON fora do
  schema → erro alto, sem valor default.
- **Não usar `--bare`**: pula a leitura do login no keychain.
- **Isolar contexto**: o CLI carrega o CLAUDE.md global de Davi a cada chamada (gasta
  cota, pode contaminar). A implementação tem de achar e testar a flag/configuração que
  evita isso sem perder o login — não está verificada ainda.
- **Cota compartilhada** com o uso interativo (janela de 5 h). O app processa em **fila**
  com limite configurável de episódios por janela e para com mensagem clara se o CLI
  reportar limite atingido.
- Volume: 1 chamada por episódio (detector) + 1 por corte aprovado (deixas visuais).

## 8. Buscador de cenas

Por corte aprovado:

1. **Deixas:** o `llm` lê a transcrição do corte e marca, com tempo, o que dá para
   mostrar, com tipo: `literal` (coisa/pessoa citada), `acontecimento` (filmagem do fato
   narrado), `grafico_ou_dado` (número falado), `retencao`, `gerado_ia`. Inclui termo de
   busca.
2. **Busca por tipo:**
   - literal / acontecimento → YouTube (yt-dlp, trecho curto), Wikimedia Commons, Pexels.
   - retenção → `biblioteca/` local.
   - gerado → FlowPool (API local), quando não há imagem real.
   - dado → gerado pelo próprio render (componente de gráfico) a partir do número.
3. **Conferência:** modelo de visão avalia quadros de cada candidato contra a deixa e
   descarta os que não batem (um carro qualquer ≠ Supra). Usa o `llm` com a ferramenta
   `Read` liberada só para a pasta de quadros do candidato (`--tools Read --add-dir <pasta>`),
   já que imagem entra no CLI pela leitura de arquivo.
4. **Escolha na curadoria:** 3–5 opções por deixa; Davi escolhe ou troca.

**Política de fontes: A (decidida)** — todas liberadas, YouTube incluído. Cada visual
guarda `fonte_url`, `licenca` e `risco` (YouTube = alto: pode gerar reivindicação de
Content ID). A curadoria mostra o risco do corte antes do render. Se usar ou não cada
tipo é parâmetro do **template**, calibrado pela pesquisa.

## 9. Render (Remotion)

Uma composição `Short` que recebe `plano.json` como props. Componentes: `Falante`
(vídeo original + crop animado), `Dividido`, `VisualCheio`, `Legenda`, `Capa`, `Zoom`,
`Grafico` (v1.1). 1080×1920, 30 fps, áudio original normalizado. Render em lote pela CLI
do Remotion, um processo por Short.

## 10. Curadoria (web local)

FastAPI + página estática em `127.0.0.1`. Tela do episódio: candidatos ordenados por
nota, com justificativa, notas da rubrica, player do trecho, ajuste de início/fim,
aprovar/rejeitar com motivo (lista fixa + texto livre). Tela do corte: deixas com opções
de visual e risco. Tela do render: Short final lado a lado com o plano. Toda ação grava
em disco.

## 11. Retorno e passagem para o automático

- **Concordância:** a cada episódio curado, mede-se a precisão do top-10 do app contra as
  aprovações de Davi. Critério para ligar o automático: precisão ≥ 70% em 3 episódios
  seguidos (valor inicial; Davi pode mudar).
- **Desempenho:** para os Shorts postados, puxar views e retenção (skill
  `youtube-analytics`) e comparar com a nota do app. O `retorno` **propõe** ajuste de
  pesos; nunca altera perfil/template sozinho — Davi aprova.

## 12. Erros

Cada módulo grava saída ao terminar; rerodar pula o que está pronto. Falha de download,
LLM, visão ou render interrompe o episódio com mensagem que diz o módulo, a causa e o
arquivo. Nada de default silencioso: visual não encontrado vira deixa marcada "sem visual"
visível na curadoria, não um visual qualquer.

## 13. Testes

Nos caminhos críticos, não por cobertura:
- Regra de início (§6.4.2) com frases reais do corpus (os 12 "começa no meio" viram casos).
- `montador` é puro: dado candidato + template, plano esperado (snapshot).
- Schemas: todo `plano.json`, `candidatos.json` e `deixas.json` valida.
- `llm`: resposta de erro e JSON inválido geram exceção.
- Ponta a ponta: um trecho de referência de 20 s gera um MP4 com duração, resolução e
  áudio corretos.

Comando de check (a registrar no CLAUDE.md do repo): `ruff check`, `mypy --strict app`,
`pytest`, e `tsc --noEmit` em `render/`.

## 14. Riscos

- **Direitos:** corte de podcast e trecho de YouTube são conteúdo de terceiros; YouTube
  pode desmonetizar "clipes com pouca narrativa" e o Instagram rebaixa conta de repost
  (01-pesquisa-documental). Verificar se cada podcast autoriza cortes.
- **Bloqueio do YouTube** por excesso de requisições (ocorreu na pesquisa).
- **Cota da assinatura** compartilhada (§7).
- **Evidência correlacional:** templates vêm de dados alheios; a verdade final é a
  retenção dos Shorts de Davi (§11).

## 15. Entregas

- **v1:** ingestão → detector → curadoria → visão → cenas (literal, acontecimento,
  gerado) → montador → render com falante, dividido, visual cheio, legenda, capa, zoom.
- **v1.1:** gráficos de dados animados. (Biblioteca de retenção descartada: R2 sem efeito.)
- **v2:** modo automático; perfil e template de humor (com pesquisa própria).

## 16. Decisões registradas

| Decisão | Escolha | Motivo |
|---|---|---|
| Para quem | Ferramenta local de Davi | Canais próprios, sem custo por vídeo |
| Operação | Curadoria → automático (C) | Curadoria gera o dado que calibra |
| Nichos | Finanças primeiro, humor depois; perfil por nicho | Regras diferem por nicho |
| Base das regras | Pesquisa própria (corpus cego) + literatura | Lista de palpite foi rejeitada |
| Render | HTML/React — Remotion (B) | Qualidade; Davi já usa |
| LLM | Assinatura via `claude -p` | Sem gasto com API |
| Fontes de visual | Todas, YouTube incluído (A), com risco registrado | Fidelidade ao formato que viraliza |
| Separação | Perfil (o que cortar) × template (como editar) | Trocar/testar independentes |
