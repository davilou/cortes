# Rodada 2 — o que leva um corte de finanças do mediano ao topo

Data: 2026-09-30. Continua `02-corpus-financas.md` (rodada 1). Saída bruta:
`corpus2/analise_saida.txt`; tabela: `corpus2/tabela_final.json`.

## Método — o que mudou em relação à R1

- **Canais escolhidos por desempenho, não por nome.** Puxei ~8.000 shorts de 20 hashtags
  de finanças e cortes, separei os 1.735 com ≥300 mil views, descobri o canal de cada um
  (oEmbed) e fiquei com canais de dinheiro em PT-BR com short ≥1 mi views. 12 canais:
  7 de terceiros (Reflexão do Dia, Códigos Bilionários, Marçal na Íntegra, Relevantes de
  Negócios, JM Cortes, Cortes da Economia, Mindset.Outlier) e 5 oficiais (PrimoCast,
  Os Economistas, Os Sócios, Bruno Perini, Irmãos Dias).
- **Três grupos por canal:** top 10, **meio 10 (em torno da mediana)**, fundo 5. A pergunta
  central é **top × meio** — os cortes do app não vão ser lixo, vão ser medianos.
- **Só shorts com mais de 60 dias** (data achada por busca binária) — elimina a confusão
  de "fundo = recente" da R1.
- **12 quadros por short** (a R1 tinha 6) e campos novos: tipo de visual externo,
  sincronia com a fala, alternância de layout, dose de visual.
- **n = 247** (de 300 selecionados; 53 bloqueados pelo YouTube, espalhados por grupo e
  canal — top 19, meio 23, fundo 11). 10 classificadores cegos, códigos sorteados.
- **Robustez:** em quantos dos 12 canais a direção top > meio se repete.
  ≥ 9 contra ≤ 3 = forte; 8×4 ou 7×1 = moderado; o resto = pista ou ruído.

## Resultado

### O que separa top de meio

| Sinal | Top | Meio | Fundo | Canais top>meio × top<meio | Força |
|---|---|---|---|---|---|
| **Mostra a outra pessoa da conversa** (troca de falante visível) | 53% | 37% | 41% | **10 × 1** | forte |
| **Mais trocas de plano** (por 10 s, mediana) | 0,62 | 0,52 | 0,42 | **9 × 3** | forte — confirma R1 |
| Fecha com conclusão/punchline (corta no meio: 9% · 12% · 14%) | 90% | 88% | 82% | 8 × 2 | moderado — confirma R1 |
| Força do gancho (média 1-5) | — | — | — | 8 × 4 | moderado |
| Autocontido | — | — | — | 8 × 4 | moderado |
| Legenda longa sem destaque (frase inteira) | 17% | 9% | 8% | 7 × 1 | moderado |
| Personagem famoso citado | 42% | 31% | 33% | 6 × 3 | pista |

**Emoção** (sem consistência forte por canal, mas com gradiente limpo top → fundo):
espanto 28% · 20% · 8% (confirma R1); humor 18% · 8% · 14%; inspiração/motivação
**13% · 25% · 22%** — o motivacional puro rende menos. Gancho com **número ou dado**:
15% · 7% · 2%.

**Formato de origem:** podcast de estúdio 75% · 70% · 59%; entrevista em evento 2% · 4% · 12%;
palestra 5% · 11% · 12%. Conversa de estúdio > palco.

### O que NÃO separa (ou contradiz a R1)

| Sinal | Top | Meio | Canais | Leitura |
|---|---|---|---|---|
| Zoom variado | 45% | 55% | 3 × 7 | **Contradiz a R1** (lá 5×0 contra o fundo). Não diferencia top de meio. |
| Palavras por segundo | 3,51 | 3,59 | 4 × 8 | Contradiz a R1 (efeito pequeno lá). Não é sinal. |
| Legenda curta com destaque colorido | 35% | 48% (fundo 65%) | 1 × 4 | O estilo "palavra colorida" é **mais comum quanto pior o grupo**. |
| Vídeo de retenção (satisfatório/gameplay) | 10% | 10% | 1 × 0 | Nenhum efeito, nem pra bem nem pra mal. |
| Tela dividida 2 pessoas | 2% | 4% (fundo 6%) | 1 × 3 | Confirma R1: não ajuda. |
| Título fixo | 17% | 15% | 3 × 2 | Neutro (R1 sugeria negativo). |

### Visual externo — a pergunta que o exemplo do Supra levantou

| | Top | Meio | Fundo | Canais |
|---|---|---|---|---|
| Nenhum visual externo | 40% | 48% | 55% | 4 × 5 |
| Visual em mais de 50% do tempo | 33% | 27% | 20% | 5 × 3 |
| Acontecimento (filmagem do fato) | 14% | 7% | 8% | 5 × 3 |
| Gráfico ou dado | 5% | 1% | 2% | 4 × 0 |
| Literal (a coisa citada) | 41% | 36% | 31% | 4 × 5 |
| Sincronizado com a fala (entre os que têm) | 79% | 80% | 86% | — |

Gradiente consistente no total (mais visual → melhor grupo), mas **não se repete canal a
canal** — é pista, não regra. O que tem cara de sinal: **acontecimento** e **gráfico/dado**
(n pequeno). Sincronia não diferencia porque quase todo mundo que usa visual já sincroniza.

## Limites

- **Muitas comparações** (~90 linhas): algumas diferenças são acaso. Confiar em ≥ 9×3 e no
  que R1 e R2 concordam.
- **Top × meio é uma diferença menor que top × fundo** — a R1 comparava extremos; por isso
  os sinais aqui são mais fracos, e é o esperado.
- Classificadores divergiram em bordas (tema motivacional: "outro" × "negócios";
  personagem famoso). Como os códigos foram sorteados entre lotes, isso vira ruído, não viés.
- Uma duplicata provável (W204/W226); curtíssimos sem fala (3–6 s) mantidos.
- Correlação, não causa; só views (sem retenção).

## R1 × R2 — o que ficou de pé

| Achado | R1 (top×fundo) | R2 (top×meio) | Status |
|---|---|---|---|
| Mais trocas de plano | 5/6 | 9×3 | **confirmado** |
| Fecha com conclusão | forte | 8×2 | **confirmado** |
| Gancho forte / autocontido | 6/6 | 8×4 | **confirmado** (separa mais o fundo que o topo) |
| Espanto | 9×0 | gradiente 28·20·8 | **confirmado** |
| Número/dado no gancho | 5×2 | 15·7·2 | **confirmado** |
| Tela dividida não ajuda | 0×2 | 2·4·6 | **confirmado** |
| Destaque colorido na legenda não é melhor | 3×7 | 35·48·65 | **confirmado** (tende a pior) |
| Mostrar a outra pessoa | não medido | 10×1 | **novo, forte** |
| Humor em corte de finanças | 4×5 | 18·8·14 | novo, pista |
| Motivacional rende menos | 7×7 | 13·25·22 | novo, pista |
| Zoom variado | 5×0 | 3×7 | **derrubado** como diferencial |
| Fala mais rápida | 5/6 | 4×8 | **derrubado** |

## O que muda no app

**Perfil de finanças (detector):**
- Manter rubrica: gancho, autocontido, espanto, fechamento.
- Bônus: número/dado, humor, personagem famoso citado, conversa de estúdio.
- Penalidade: motivacional puro (inspiração sem espanto), trecho de palestra/palco.

**Template de finanças (edição):**
- **Novo:** cortar para a **reação da outra pessoa** (troca de falante visível) — o sinal mais
  forte da rodada. Exige diarização + visão acharem o ouvinte e montar planos de reação.
- Ritmo-alvo: **0,6–0,8 trocas por 10 s** (top R2 = 0,62; top R1 = 0,83).
- Legenda: **frase curta ou inteira, sem destaque colorido**.
- Zoom punch: rebaixado de padrão para opcional (sem evidência de ganho top × meio).
- Visual externo: ligado, priorizando **acontecimento** e **gráfico/dado**; retenção
  (satisfatório/gameplay) **desligada** — não ajuda.
- Tela dividida entre 2 pessoas: fora.
