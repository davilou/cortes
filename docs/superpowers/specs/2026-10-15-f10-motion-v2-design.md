# f10 Motion v2 — o "bolo de camadas"

Data: 2026-10-15 · Origem: reel do @cauhi ("o formato que vai dominar o seu feed em 2027, parte 2")
e o piloto feito no corte "Sobe no boato" do Investidor Sardinha (mesma data). Pedido de Davi: um
formato novo, sem mexer no f3. O número 9 ficou com o f9 Ilustrado que virou o f4 (`F9_SAIU`), por
isso f10.

## 1. Objetivo

As mesmas cenas do f3 (o Claude escolhe componente e parâmetros; números só os ditos; cache em
`motion/`) num layout com mais camadas visíveis:

- dois fundos que se revezam a cada cena — claro pontilhado e marinho com brilho roxo;
- quem fala num card com borda roxa e **a cabeça saindo por cima da borda** (recorte sem fundo);
- nas cenas escuras, o painel sozinho no meio e o rosto num avatar redondo no canto;
- legenda grande, **uma palavra por vez**, número em roxo;
- um efeito sonoro em cada movimento: whoosh nas trocas de fundo, pop na entrada do painel e em
  cada batida.

## 2. Fora de escopo

- Mudar o f3, o prompt das cenas ou o ritmo (`motion_ritmo`): o f10 só redesenha.
- Escolha automática de formato pelo detector.
- Biblioteca de SFX de terceiros (os dois sons são sintetizados, `biblioteca/sfx/LEIAME.md`).

## 3. Estados (`render/motion2.py`, puro)

| Estado | Quando | Tela |
|---|---|---|
| `gancho` | 0 até o fim da capa (ou 2 s) | fundo claro; rótulo e título da capa em cima; card embaixo |
| `escuro` | painéis 1, 3, 5… | fundo marinho; painel no meio (y 608–1332); avatar 220 px no canto |
| `claro` | painéis 2, 4, 6… e os vãos | fundo claro; painel em cima (y 48–772); card embaixo |
| `respiro` | as cenas `respiro` do f3 | fundo claro; só o card, subido 300 px |

- Vão entre cenas maior que 0,05 s vira `claro` com o rótulo da capa na faixa (como a faixa de
  base do f3). Estados iguais seguidos se fundem.
- Transição curta (0,2–0,28 s): o fundo cruza, o card desce/sobe, o avatar estala.

## 4. Câmeras (`render/rosto.py`)

- Card: janela 1000 × 900, alvo (500, 160) na escala do div do f3 — o rosto alto, para o alto da
  cabeça passar da borda de cima.
- Faixa da cabeça: 200 px acima do card, com a mesma trilha deslocada 200 px (`trilha_cabeca`),
  mostrando `assets/recorte.webm`. Como só a pessoa é opaca no recorte, só a cabeça aparece.
- Avatar: a mesma câmera a 40%, janela 220 × 220, alvo (110, 112).

## 5. Recorte da cabeça (`render/visao/recorte_fundo.py` + `src/cortes/render/recorte_fundo.py`)

- `u2net_human_seg` (do rembg, em `~/.u2net`) no onnxruntime **com CUDA**, no Python do ComfyUI.
  O script importa o `torch` antes da sessão: é ele que carrega o cuBLAS/cuDNN que o
  onnxruntime-gpu procura (sem isso caía na CPU sem avisar).
- Máscara a 320 px, ampliada ao tamanho do trecho, suavizada no tempo (média móvel 0,6) para a
  borda do cabelo não tremer. Saída: WebM VP9 com alfa, do tamanho e fps do trecho.
- Sem CUDA o script sai com erro: na CPU um minuto de trecho leva ~20 min. Medido na 3090: 20 s
  de trecho 920×1080 em 38 s, com a carga do torch.
- Asset do trecho como o fundo do f8: gerado se faltar (por `.parcial.webm`), apagado quando o
  trecho é refeito.

## 6. Tema

Fixo: `bolo` em `motion_tema.TEMAS` (cartão branco, acento #7b5cff), fora de `TEMAS_LLM` — o enum
do schema e as validações do LLM, do cache e do editor só aceitam os quatro do f3. A troca de tema
do editor não vale no f10 (o seletor some). As ilustrações em SVG livre usam a paleta `bolo`.

## 7. Compartilhado com o f3

- `render/motion_estilo.py`: o CSS dos componentes e o JS (`fmt`, `contar`, `relogio`) saíram do
  `motion.tpl` para os dois templates usarem o mesmo.
- `cenas_html(..., solo)` põe a classe `solo` na faixa dos painéis do estado `escuro`.
- Cache das cenas: o mesmo `motion/cenas.json`. Trocar entre f3 e f10 no editor não chama o LLM.

## 8. Testes

- Puros: estados (revezamento, vão, respiro, fresta, invasão), SFX (whoosh, pop, colagem por tipo,
  fim do Short), HTML do SFX.
- Assets: SFX copiados uma vez; falta é erro claro. Recorte: por parcial, cache, sem modelo, falha.
- Pipeline com LLM falso: HTML do f10 sem sobra de placeholder, faixa `solo`, trilha da cabeça =
  trilha do card + 200, f3 e f10 dividem as cenas, tema do editor ignorado.
- Render real: `testes/f10/render_real.py` (corte do Sardinha, 150,5–196,6 s).

## 9. Medido no render real (2026-10-15)

Corte do Sardinha, 150,5–196,6 s (45,9 s, 11 cenas, 1 descartada pelo ritmo):

- Primeira vez (LLM das cenas, rosto, recorte na GPU e MP4): 649 s; o MP4 sozinho, 4 min 26 s.
- `ALVO_CARD` começou em y 250 e a cabeça mal passava da borda (~40 px); em y 160 ela sai como no
  piloto.
- Com a máquina ocupada por outros jobs, o mesmo MP4 levou 9 min 22 s (extração 3 min 46 s, contra
  25 s livre) e uma tentativa passou dos 20 min de `processo.TIMEOUT_S` sem log. O f10 decodifica
  o trecho três vezes (card, avatar, áudio) mais o WebM com alfa: é o formato mais pesado do app.
  Se o estouro se repetir com a máquina livre, a saída é um prazo maior só para o f10.
