# Reel de referência do f3 — o que ele faz, medido

Data: 2026-10-15. Fonte: reel de @tiagolemosx, 7/10/2026, 110,9 s, 9:16
(https://www.instagram.com/reel/DeNzBHuRpwW/). Davi escolheu este reel como alvo de qualidade do f3
(2026-10-14) e decidiu que o novo estilo **substitui** o f3, superando a regra de ritmo da
`03-corpus-financas-r2.md` para este formato.

**Peso da fonte:** um exemplo só, de vitrine de edição ("Comenta EDIÇÃO"), com apresentador gerado
por IA (troca de roupa e de cenário a cada assunto). Não é um corte de podcast e não mede retenção.
Vale como referência de **estilo**, não como evidência de que o estilo retém mais — isso o painel
de contas mede depois.

## Método

Quadros extraídos no navegador (canvas sobre o `<video>` da página): 12 quadros em 0,5–11,5 s,
12 em 13–46 s, 12 em 50–105 s e 36 a cada 1 s em 12–47 s. Cadência por diferença média de pixels
(RGB, 0–255) na faixa de cima (40% da altura, onde fica o painel) a cada 0,25 s, em 90×160.

## Layout

- **Tela dividida quase o tempo todo.** Painel na faixa de cima (~42% da altura); o apresentador
  num **card arredondado** embaixo (~45% da altura), com margem lateral de ~4% e sombra, sobre
  fundo escuro. Rosto cheio só em 0–6 s (gancho), em ~24 s e em ~43 s e ~70 s (troca de assunto).
- **Gancho:** rosto cheio com o título por cima da cabeça ("CONTEÚDO 2.0", grande, branco, com
  rótulo pequeno acima) e um selo ("Claude Editando") no topo.
- **Legenda:** pequena, minúscula, branca, 1–3 palavras por vez, no meio do card — não no rodapé.

## Painéis

- **Cara de interface:** cartões escuros com rótulos pequenos em caixa alta (ex.: "ORÇAMENTO"),
  linhas finas, ícones de traço, um acento de cor (laranja) por painel. Elementos entram um a um e
  o texto "digita" (6,5–11,5 s: a palavra "explicação" sendo escrita sobre uma onda de áudio).
- **Tipos vistos:** onda de áudio + texto digitando; orçamento com valor oculto (R$ •••••);
  check grande; nuvem de palavras; **fluxo** "você fala → a IA desenha → todos entendem" com
  ícones e setas, o último passo aceso; grade de avatares; gráfico de linha com ponto ("efeito do
  botox: começa a agir dia 3"); ficha de produto (35 g de açúcar); timer (03:31, 06:12); grade
  2×2 de profissões; teclado; número/título grande ("2.0").
- **Ilustrações de assunto:** planta 3D isométrica com área (72 m²) e preço (R$ 810.000), mapa
  escuro com pino, anatomia do rosto com músculos destacados, corte da pele em camadas, sol e
  Terra com a distância da luz, cidade à noite. Nesta rodada viram desenho por código (decisão
  de Davi, 2026-10-14): esquemáticas, no tema do Short.
- **Tema por assunto:** escuro quente (padrão), azul-marinho com serifa ("Residencial Aurora",
  imóvel), claro clínico (saúde), espaço (astronomia).

## Cadência

- **Cenas de 2 a 5 s, com batidas internas a cada ~1 s.** Na folha de 1 s (12–47 s): orçamento
  13–17 s (o valor e as opções entrando), check 19 s, nuvem 21 s, fluxo 22–23 s, rosto cheio
  24 s, cidade 25–27 s, imóvel 28–41 s em 5 painéis (mapa, contorno, planta, preço) e depois saúde.
- **Mudança visual forte** (diferença > 20 na faixa do painel): 37 em 110,9 s ≈ **3,3 por 10 s**.
  Cortes duros (> 28): 21, mediana de **3 s** entre eles (p25 1,25 s, p75 6,75 s).
- Comparação: a `03` mede 0,6–0,8 trocas de plano por 10 s no top de cortes de finanças; o reel
  faz ~4× isso. É a regra que o novo f3 deixa de seguir.

## Regras que o novo f3 tira daqui

| Regra | Valor | De onde |
|---|---|---|
| Tela dividida depois do gancho | ≥ 85% do tempo | layout |
| Gancho | rosto cheio + título, 0–2 s | layout |
| Rosto cheio no meio | 1–2 vezes, 1,5–3 s | layout |
| Duração da cena | 2–5 s | cadência |
| Batida dentro da cena | ~1 s | cadência |
| Legenda | pequena, minúscula, no card | layout |
| Um acento de cor por painel, tema por assunto | — | painéis |
