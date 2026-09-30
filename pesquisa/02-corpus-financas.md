# Corpus — cortes de finanças BR: o que separa viral de fracasso

Data: 2026-09-30. Complementa `01-pesquisa-documental.md` (literatura) com medição própria.

## Método

- **Canais (6):** PrimoCast, Os Economistas, Gêmeos Investem (oficiais) · Cortes da Economia,
  Cortes Capitalista, Os Sócios Cortes (terceiros). Mapeados por busca no YouTube; excluídos
  canais com menos de 20 shorts.
- **Amostra:** até 300 shorts por canal; descartados os 20 mais recentes (views ainda subindo);
  **top 6 e fundo 6 de cada canal** = 72 shorts. A comparação é sempre dentro do canal, para
  que tamanho do canal não explique a diferença.
- **Medido por código:** duração, trocas de plano (ffmpeg, scene > 0.3), palavras/s e
  transcrição (Whisper medium), likes, comentários.
- **Classificado às cegas:** 3 classificadores (LLM, visão + transcrição) com esquema fixo
  (`corpus/esquema_classificacao.md`), sobre códigos embaralhados V01–V72, sem acesso a
  views, canal-grupo ou título. A chave só foi aberta depois.
- **Robustez:** além do total, conto em quantos dos 6 canais a direção se repete.
  6/6 ou 5/6 = sinal forte; o resto = pista.

Tabela completa: `corpus/tabela_final.json`.

## Resultado — ordenado pela força do sinal

### 1. O momento pesa mais que a edição (6/6 canais)

| Medida (1–5) | Top | Fundo | Canais na direção |
|---|---|---|---|
| Força do gancho nos 3 primeiros segundos | 3,39 | 2,53 | **6/6** |
| Autocontido (entende sem ver o episódio) | 4,25 | 3,64 | **6/6** |

Tipo de gancho (top | fundo):
- **Começa no meio da frase, sem contexto: 4 | 12** — o erro mais comum dos fracassos.
- História pessoal: 7 | 1 · Número/dado: 5 | 2 · Promessa de revelação: 4 | 1.
- Pergunta: 8 | 8 e opinião forte: 6 | 8 — não separam sozinhas.

Exemplos de abertura top: "Nenhuma força aérea do mundo tem capacidade de lutar contra…" (1,3 mi);
"Cara, não sei se eu deveria falar, melhor não falar…" (696 mil).
Exemplos de fundo: "a paciência começou a surgir, parcerias começaram a…" (17 views);
"…até chegar na digital. Mas como é que foi…" (14 views).

### 2. Emoção: espanto ganha, utilidade pura perde

| Emoção dominante | Top | Fundo |
|---|---|---|
| Espanto / surpresa | **9** | **0** |
| Utilidade prática | 8 | 14 |
| Inspiração, humor, raiva, medo | ~iguais | |

Tema "polêmica social / comportamento": 9 | 3. "Investimentos" puro: 5 | 9.
**Leitura:** no nicho de finanças, a dica útil sem choque é o que mais fracassa. O corte que
viraliza usa finanças como pano de fundo de algo surpreendente (juro de 0,7% na Europa,
vendeu a casa, geopolítica). Isso contraria a leitura simples de Berger & Milkman
("utilidade aumenta compartilhamento"), que foi medida em texto, não em Short.

### 3. Edição: movimento sim; enfeite não

| Medida | Top | Fundo | Canais |
|---|---|---|---|
| Trocas de plano por 10 s (mediana) | 0,83 | 0,22 | **5/6** |
| Zoom variado no mesmo falante | 24 | 17 | **5/6** (0 contra) |
| Palavras por segundo (mediana) | 3,42 | 3,20 | 5/6 (efeito pequeno) |
| Inserções visuais (imagem, gráfico, b-roll) | 14 | 8 | 3/6 (pista) |
| Título fixo na tela o vídeo todo | 2 | 6 | **0/6 — associado ao fundo** |
| Duração | 59 s | 49 s | sem direção |

### 4. Layout e legenda — o que derruba a minha lista inicial

| Layout principal | Top | Fundo |
|---|---|---|
| Falante reenquadrado (1 pessoa) | **27** | 21 |
| Falante + visual (gráfico/b-roll/react) | 6 | 7 |
| Tela dividida 2 pessoas | **0** | 2 |
| Quadro 16:9 com faixas/blur | **0** | 3 |

| Legenda | Top | Fundo |
|---|---|---|
| Sem legenda | **5** | **12** |
| Frase curta sem destaque | 23 | 17 |
| Palavra a palavra com destaque colorido | 3 | 7 |
| Frase longa em bloco | 5 | 0 |

- **Ter legenda importa; o estilo "Hormozi" colorido não se mostrou superior** neste nicho.
- **Tela dividida não apareceu em nenhum viral de finanças.** A hipótese que eu tinha
  sugerido para a v1 não se sustenta aqui.
- Abertura "capa" (título grande + imagem, antes do falante): 5 | 1. "Falante com título
  por cima": 0 | 8. A capa curta funciona; título colado o vídeo inteiro, não.

### 5. Achado lateral: repostar o vencedor funciona

Os Economistas postou o mesmo corte duas vezes (V50 e V58): 674 mil e 362 mil views,
os dois no top. Conteúdo forte repete desempenho.

## Limites — o que este estudo não prova

- **n = 72, 6 canais.** Mostra direção, não tamanho de efeito; não fiz teste estatístico
  formal porque a amostra por canal (6+6) não sustenta.
- **Confusão por data:** em Os Economistas e PrimoCast o grupo fundo é mais recente (set/2026);
  parte do fracasso pode ser só tempo. Os achados 6/6 resistem a isso; os de 3/6 não.
- **Classificador é LLM.** Os três divergiram em bordas (posição da legenda, legenda de
  2–3 linhas com destaque). Campos subjetivos (força do gancho) são julgamento, embora cego.
- **Views como métrica:** desde 31/03/2025 o YouTube conta replays; não temos
  "viewed vs swiped" nem retenção dos canais alheios — só views.
- **Correlação, não causa:** canal que caprichou no gancho também pode ter caprichado em
  título, horário e thumbnail.
- 17 dos 72 não eram corte de podcast (react, entrevista de evento); não alteram as direções.

## O que isso vira no app (perfil de nicho: finanças v1)

**Detector de momento (peso maior):**
1. Rejeitar trecho cuja primeira frase dependa de contexto anterior ("Mas…", "Também…",
   pronome sem referente). O início do corte deve cair no começo de uma ideia.
2. Pontuar alto: espanto (número ou fato contraintuitivo), história pessoal com virada,
   promessa de revelação, polêmica de comportamento.
3. Pontuar baixo: dica útil sem elemento surpreendente.
4. Exigir fechamento: o trecho termina em conclusão ou punchline.

**Editor (v1):**
1. Falante reenquadrado seguindo o rosto, com zoom variado (punch-in) nas frases fortes.
2. Legenda sempre ligada; estilo simples de frase curta (sem pagar o custo do destaque colorido).
3. Capa opcional nos 2–3 primeiros segundos (título + imagem) — sem título fixo o vídeo todo.
4. Inserções visuais (b-roll/imagem) como pista a testar, não padrão.
5. **Fora da v1:** tela dividida e 16:9 com faixas (zero virais na amostra).
