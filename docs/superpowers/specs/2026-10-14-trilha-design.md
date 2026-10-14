# Trilha de fundo nos Shorts

Data: 2026-10-14 · Pesquisa: `pesquisa/04-trilha.md` (regras R1–R12) · Muda a decisão "sem trilha"
da spec de produção (`2026-10-02-producao-design.md`, plano B), por pedido de Davi (2026-10-14).

## 1. Objetivo

Cada Short sai com uma cama instrumental por baixo da fala, escolhida pelo tom do trecho, num nível
que não disputa com a voz. Davi troca a cama (ou tira) no editor e ouve na prévia antes de
renderizar. A cama usada fica registrada no corte, para comparar com e sem trilha depois (R12) —
a pesquisa não achou dado de que trilha aumenta retenção em Short.

## 2. Fora de escopo

- Gerar cama por Short (Stable Audio na fila da GPU). A biblioteca cresce à parte, gerada uma vez.
- Drop/silêncio antes do punchline (R7: só depois de um A/B).
- Ducking por sidechain (R2: as pausas já são cortadas; sidechain só bombearia).
- Normalizar o MP4 final para −14 LUFS (R9). É um passo da entrega que vale com ou sem trilha;
  fica para outra mudança.
- Ligar a cama usada às métricas do painel de contas (o registro fica pronto; a leitura, não).

## 3. Biblioteca

`biblioteca/trilhas/` (já existe, hoje fora do git): `plano.json` + `final/<id>.m4a`. Cada fase do
`plano.json` ganha `"mood"` (`neutro`/`tensao`/`leve`); a cama de um mood é a primeira com ele
(rodízio fica para quando houver mais de uma). O bpm de cada cama vem do `plano.json`.

| id | mood | bpm | uso (R8) |
|----|------|-----|----------|
| A | neutro | 76 | padrão e dúvida |
| B | tensão/curiosidade | 70 | espanto, medo, raiva |
| C | leve | 84 | humor |

Novo módulo `render/trilha_biblioteca.py` lê o `plano.json` e devolve `Cama(id, mood, bpm, arquivo,
lufs)`. A loudness integrada de cada cama é medida uma vez (ffmpeg `ebur128`) e guardada em
`biblioteca/trilhas/medidas.json`, chaveada por id + tamanho + mtime do arquivo; arquivo mudou →
mede de novo. Cama listada no plano sem arquivo em `final/`, ou `plano.json` ausente, é erro claro.

O painel não sobe sem a biblioteca (mesma checagem de `ffmpeg`/`npx` em `painel/servidor.py`).
Os `.m4a` (5,9 MB os três) e o `plano.json` entram no git; `cues/` (rascunhos) e `trilhas-descartes/`
ficam de fora (`.gitignore`).

## 4. Escolha da cama (mood)

`Edicoes.trilha: str | None` — `None` = automático; `"A"`/`"B"`/`"C"` = escolhida no editor;
`"nenhuma"` = sem trilha. `corte.json` antigo sem o campo lê como automático (o campo é novo; não
há valor anterior a perder). Mudar a trilha não zera nada mais do corte.

Automático: `render/trilha_mood.py` pergunta ao LLM (`claude -p`, `MODELO = "sonnet"`, mesmo
caminho do SEO) o tom do trecho: `{"mood": "neutro" | "tensao" | "leve", "motivo": "..."}`.
Mapeamento fixo para a cama (R8). Schema inválido, mood fora da lista ou erro do LLM → ErroRender
com a causa (o corte fica em erro, como no SEO). Cache em `cortes/<n>/trilha.json` pelo texto do
corte (o mesmo `texto_do_corte` do SEO): rerender sem mudar o texto não chama o LLM.

O prompt pede, na dúvida, "neutro" — tensão por baixo de fala neutra muda o julgamento de quem
fala (Boltz 2001, R8).

## 5. Mixagem

A cama entra como `<audio>` no `index.html` do projeto HyperFrames, ao lado do `cam-audio` (a voz).
Assim a prévia do editor toca a trilha e o render a grava, sem passo extra de ffmpeg.

Funções puras em `render/trilha.py`:

- `ganho(lufs_voz, lufs_cama, alvo_lu=18.0) -> float` — `data-volume` linear para a cama ficar
  `alvo_lu` abaixo da voz (R1). Cama já mais baixa que o alvo não é amplificada acima de 1.0.
- `clipes(dur, cama) -> list[Clipe]` — `Clipe(inicio, duracao, media_inicio, fade_in, fade_out)`:
  - entrada com fade de 0,3 s (R4);
  - `media_inicio` escolhido para o fim do vídeo cair numa barra da cama (`4 × 60 / bpm`); o
    fade-out dura um compasso e termina em `dur` (R5);
  - corte mais longo que a cama: clipes encadeados com 2 s de sobreposição e crossfade.
- `html_trilha(clipes, arquivo, volume) -> str` — os `<audio data-track-index="11"
  data-audio-group="trilha" …>`; `{{TRILHA}}` nos 7 templates, logo depois do `cam-audio`.
  Sem trilha → string vazia.

I/O fino com executor injetável: `medir_lufs(arquivo, rodar)` (ffmpeg `ebur128`), usada na voz
(`assets/trecho.mp4`, a cada `montar_projeto` — o trecho muda com início/fim) e nas camas (cache
acima). A cama é copiada para `projeto/assets/trilha.m4a` e entra na lista fechada de arquivos
servidos pela prévia (`_VIDEOS_PREVIA` vira `_MIDIA_PREVIA`, com o tipo por extensão).

`data-volume` é ganho linear (0 até +12 dB), com o mesmo teto na prévia (Web Audio) e no render
(FFmpeg) — `@hyperframes/core` 0.8.104, `dist/audioGain.js`, a versão que o render e a prévia usam.
Um teste `lento` renderiza só a cama com `data-volume=0.1` e confere −20 ± 1 dB contra a fonte.

## 6. Pipeline

`montar_projeto` ganha um passo depois de `preparar_assets`: `preparar_trilha(d, c, texto, dep)`
devolve `TrilhaUsada(id | None, motivo, volume)` e copia o arquivo. `valores(...)` recebe o HTML
da trilha. O render grava `cortes/<n>/short-v<k>.trilha.json` (`TrilhaUsada`: cama, origem auto/manual,
motivo, volume) ao lado do MP4 — o registro do A/B (R12), por versão, sem mexer no `corte.json`.

A biblioteca fica em `<raiz>/biblioteca/trilhas` (constante `BIBLIOTECA`). `DepRender` ganha
`medir_lufs` (executor injetável da medição).

## 7. Editor

Na coluna de ajustes, abaixo de Formato: **Trilha** — `<select>` com "Automática (B · tensão)",
A, B, C e "Sem trilha". A opção automática mostra a cama que o LLM escolheu e, no `title`, o
motivo. Mudar vai por `POST …/editar` (`PedidoEdicao.trilha`), que pede a prévia nova como as
outras edições. `estado_editor` devolve `trilha: {escolha, automatica, motivo}`;
`automatica` é `null` enquanto a prévia não rodou o LLM.

## 8. Erros

- Biblioteca ausente/incompleta: o painel não sobe, com a causa.
- LLM do mood falhou: corte em erro com a mensagem; Davi pode escolher a cama na mão (aí o LLM não
  é chamado) ou tentar de novo.
- ffmpeg falhou ao medir: ErroRender com a cauda do stderr (padrão de `recorte.py`).

## 9. Testes

Puros: `ganho` (alvo, teto 1.0), `clipes` (fade, fim na barra, corte curto < 1 compasso, corte
mais longo que a cama), `html_trilha`, mapeamento mood → cama, validação do JSON do LLM, leitura
do plano (cama sem arquivo). Rotas: editar trilha, estado do editor com trilha, prévia servindo
`assets/trilha.m4a`. Pipeline com executor falso: cache do mood (não chama o LLM duas vezes),
escolha manual não chama o LLM, `trilha_usada` gravada. Render real (`lento`): mede voz × trilha
no MP4 e confere 18 ± 2 LU.
