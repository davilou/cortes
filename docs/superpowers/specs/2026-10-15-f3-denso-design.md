# f3 Motion denso — o estilo do reel de referência

Data: 2026-10-15 · Fonte: `pesquisa/05-reel-referencia-f3.md` · Substitui o f3 da spec de produção
§7 (`2026-10-02-producao-design.md`), por decisão de Davi (2026-10-14). A regra de ritmo de lá
(0,6–0,8 trocas por 10 s, `pesquisa/03`) deixa de valer para o f3; os outros formatos não mudam.

## 1. Objetivo

O f3 passa a parecer o reel de referência: tela dividida quase o tempo todo, painéis com cara de
interface que trocam a cada 2–5 s acompanhando a fala, ilustrações desenhadas por código e um tema
por assunto. Continua valendo tudo que torna o f3 confiável: o LLM devolve JSON validado (nunca
HTML de layout), números só os ditos, grafia corrigida, sincronia por batida, cache e "Refazer
motion".

## 2. Fora de escopo

- Imagem real ou gerada (FlowPool, ComfyUI, busca): fica para outra rodada.
- Troca de tema no meio do Short; transições animadas entre painéis (continua corte seco).
- Trocar o apresentador de roupa ou cenário (o reel usa avatar de IA; o podcast é filmado).
- Os outros formatos e a escolha de formato do detector.

## 3. Layout (`render/formatos/motion.tpl`, refeito)

Três estados, em corte seco:

| Estado | Quando | O que aparece |
|---|---|---|
| `gancho` | 0–2 s | rosto cheio, vinheta, título por cima da cabeça (rótulo pequeno + título grande), selo opcional no topo |
| `div` | o resto, ≥ 85% do tempo depois do gancho | painel na faixa de cima (0–820 px); card do falante embaixo (x 40–1040, y 860–1840, cantos de 36 px, sombra) |
| `respiro` | 1–2 vezes, 1,5–3 s cada | rosto cheio, sem painel |

- O card enquadra o rosto como o `div` de hoje: trilha fixa por plano de câmera
  (`rosto.trilha_fixa`) com janela e alvo novos (`JANELA_CARD`, `ALVO_CARD`), sem seguir o rosto.
- **Legenda:** a do f3 vira pequena (44 px), minúscula, 1–3 palavras, centrada a 70% da altura do
  card; nos estados de rosto cheio, a 72% da tela. Os outros formatos não mudam.
- Fundo da tela: a cor de fundo do tema (o card e o painel ficam sobre ele).

## 4. Ritmo (`render/motion_ritmo.py`, reescrito)

- Gancho: exatamente um, 0–2 s (o componente `capa` de hoje, no estado `gancho`).
- Cena de painel: **2 a 5 s**; dentro dela, as batidas (itens, passos, valores) entram nas palavras
  que as dizem — como a sincronia de hoje —, e o prompt pede uma batida a cada ~1 s.
- Painéis se encostam (sem rosto cheio entre eles); sobreposição é corrigida como hoje (a que
  invade acaba antes se ainda dura o mínimo; senão sai).
- `respiro`: no máximo 2, de 1,5 a 3 s, nunca antes de 6 s nem colado em outro respiro.
- Cobertura de painel depois do gancho: alvo ≥ 85%. Vão sem painel > 3 s (fora dos respiros)
  dispara a segunda chamada (`motion_cobertura`, com os novos limites) — no máximo 2 chamadas.
- Sai: `ROSTO_MIN_S` entre cheios, `FRACAO_MAX = 0,7`, o alvo de trocas da `03`.
- Vão que sobra depois da segunda chamada continua no estado `div`: a faixa de cima mostra só o
  fundo do tema com o rótulo do Short (`rotulo` da capa) — nunca um painel velho que já saiu da
  fala.

## 5. Componentes (`render/motion_params.py` + `render/motion_componentes.py`)

Todos no estado `div`, exceto `capa` (gancho). Cada um tem limites de texto pelo layout novo e
entra com animação de elementos (descer, crescer, contar, digitar), como hoje.

**Redesenhados** (mesmos parâmetros de hoje; `valor_cheio` e `comparacao` deixam de ser cheios):
`capa`, `contador`, `valor_cheio` → `valor`, `comparacao`, `chat`, `lista`, `rota`.

**Novos:**

| Componente | Parâmetros | Batidas |
|---|---|---|
| `grafico` | `rotulo`, `pontos` (2–6 de `{x: texto curto, y: número}`), `destaque` (índice) | linha desenhando, ponto em destaque |
| `fluxo` | `passos` (2–4 de `{icone, texto}`), `ativo` (índice) | cada passo entra na palavra; o ativo acende |
| `timer` | `rotulo`, `segundos` (inteiro), `sentido` (`sobe`/`desce`) | contagem |
| `check` | `texto`, `sinal` (`sim`/`nao`) | o sinal desenha |
| `grade` | `itens` (2–6 de `{icone, texto}`) | um a um |
| `destaque` | `frase` (≤ 60), `palavra` (contida na frase) | digita; a palavra muda de cor |
| `planta` | `comodos` (2–6 de `{nome, m2}`), `total_m2` opcional | cômodos sobem em isométrico |
| `ilustracao` | `descricao` (o que desenhar, ≤ 140), `rotulo` (≤ 28) | o desenho entra; o rótulo depois |

- Números em todos (incluindo `y` do gráfico, `segundos`, `m2`, `total_m2`) seguem a regra dos
  números ditos (`motion_numeros`), como hoje.
- `planta` é desenhada por código a partir dos cômodos (retângulos em grade isométrica, proporção
  pela área), sem SVG do LLM.

**Ícones:** conjunto fixo de 36 ícones de traço desenhados no próprio repo
(`render/motion_icones.py`, sem baixar pacote — mudou na execução: a ideia era copiar do Lucide);
o LLM escolhe pelo nome numa lista fechada (o schema leva o enum). Nome fora da lista recusa a cena.

**Na execução (2026-10-15):** o campo da `grade` virou `blocos` (o schema tem uma propriedade por
nome e `itens` já é a lista de textos da `lista`); painel que acaba até 1 s antes do seguinte é
esticado até ele (`motion_ritmo.emendar`) para a faixa não piscar o fundo; área de cômodo calculada
dá o tamanho na planta mas não aparece escrita (só a dita).

## 6. Ilustração em SVG livre (`render/motion_svg.py`, novo)

- Para cada cena `ilustracao` aceita, uma chamada `claude -p` à parte recebe a `descricao`, o tema
  (paleta) e as regras de desenho, e devolve `{"svg": "..."}`. No máximo **3 ilustrações por Short**
  (a 4ª em diante é recusada no ritmo, com motivo). Cache em `motion/svg/<k>.json` pela chave
  (descrição, tema).
- **Sanitização (função pura):** parse XML; raiz `<svg>` com `viewBox="0 0 1000 700"`; lista branca
  de elementos (`svg g path rect circle ellipse line polyline polygon text tspan defs
  linearGradient radialGradient stop`) e de atributos (geometria, `fill`, `stroke*`, `opacity`,
  `transform`, `font-*`, `text-anchor`, `id`, `offset`, `stop-*`, `gradientUnits`); nada de
  `script`, `foreignObject`, `image`, `use`, `style`, `href`/`xlink:href`, `on*` nem `url(` fora de
  `#id`; até 8 KB e 400 elementos; cores só da paleta do tema ou `none`. Texto dentro do SVG passa
  pela regra dos números ditos.
- **Recusado ou erro do LLM:** a cena vira `grade` de 1 item (ícone mais próximo da lista pelo
  `rotulo`, ou `circulo`) com o rótulo, e a descartada fica registrada com o motivo — o Short não
  falha por causa de uma ilustração.
- Entrada animada: os elementos de primeiro nível do SVG aparecem em sequência (opacidade e
  escala), em ~0,6 s.

## 7. Tema (`render/motion_tema.py`, novo)

| Tema | Fundo | Cartão | Texto | Acento | Uso |
|---|---|---|---|---|---|
| `escuro` (padrão) | #0d0d0f | #17171b | #f2f2f2 | #ff6a3d | geral |
| `noite` | #0b1424 | #12203a | #eef2f8 | #d9b46a | imóvel, luxo, patrimônio |
| `clinico` | #f4f6f8 | #ffffff | #16202a | #2f7de1 | saúde, corpo |
| `dados` | #0c1512 | #13211c | #eaf4ef | #3ddc84 | investimento, mercado, números |

- O LLM escolhe o tema na chamada principal (campo `tema`, enum). `Edicoes.tema: str | None`
  (`None` = o do LLM), editado no editor por um seletor "Tema", como o de trilha. Trocar o tema
  refaz o HTML e as ilustrações (a chave do SVG inclui o tema); as cenas não mudam.
- O tema vira variáveis CSS no `motion.tpl` (`{{TEMA_CSS}}`); componentes só usam as variáveis.

## 8. LLM (`render/motion_prompt.py`)

- Uma chamada principal (sonnet), como hoje: palavras numeradas + contexto → `{tema, cenas[]}`;
  cada cena com componente, palavras de início e fim e parâmetros; `respiro` é uma "cena" sem
  parâmetros.
- O prompt passa a pedir: cobrir o corte inteiro depois do gancho, cenas de 2–5 s, uma batida por
  ~1 s, preferir componentes de dado quando há número, `ilustracao` só quando o assunto tem um
  objeto concreto (corpo, imóvel, produto, lugar, astro) e nenhum componente do catálogo serve.
- Segunda chamada (cobertura) igual à de hoje, com os limites novos.
- Chamada do SVG: §6.

## 9. Editor

- Seletor "Tema" (Automático (escuro) / escuro / noite / clinico / dados), igual ao de trilha.
- A lista de cenas do f3 no editor continua (componente, tempo, descartadas com motivo); ganha o
  tipo `respiro` e as ilustrações recusadas.

## 10. Cache e migração

- `motion/cenas.json` ganha `versao: 2` na chave; cache da versão 1 é ignorado e refeito na próxima
  prévia (o f3 antigo não é mais renderizável com o template novo).
- Cortes já renderizados em f3 mantêm os MP4 antigos; a próxima prévia/render usa o estilo novo.

## 11. Erros

- Sem nenhuma cena de painel válida: "nada neste trecho vira painel — use outro formato" (hoje).
- LLM principal falhou ou schema inválido: o corte fica em erro com a causa (hoje).
- SVG: nunca derruba o corte (§6).
- Tema desconhecido no `corte.json`: erro claro na leitura.

## 12. Testes

- Puros: ritmo (cobertura, durações, respiros, gancho, sobreposição), sanitizador de SVG (cada
  regra da lista branca com caso positivo e negativo, limite de tamanho, cor fora da paleta,
  número não dito no texto), parâmetros de cada componente novo, planta isométrica (proporção pela
  área), tema (CSS gerado, `Edicoes.tema`), schema do prompt (enums de ícone e tema).
- Rotas: editar tema; editor mostra tema e respiros.
- Pipeline com LLM falso: SVG recusado vira grade sem derrubar o corte; cache do SVG pela chave.
- `lento`: os 2 cortes do teste cego atual (c5xqNNWFT9w, wxCto9WSZcI) e o corte 0 do rZfwNiJhJM0,
  com folha de quadros a cada 1 s comparada à do reel; mede cobertura (≥ 85%) e mudanças fortes
  por 10 s (alvo ~3, `pesquisa/05`).

## 13. Riscos

- **Fala de podcast é menos roteirizada que a do reel:** pode não haver o que mostrar a cada 2–5 s,
  e o LLM inventar painel fraco para cumprir a cobertura. Mitigação: o prompt prefere `destaque`
  (frase-chave da própria fala) a inventar; o teste lento mede.
- **SVG livre feio ou errado:** fallback para ícone; teto de 3 por Short.
- **Custo de LLM por corte:** 1–2 chamadas principais + até 3 de SVG.
