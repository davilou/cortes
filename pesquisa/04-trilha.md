# Trilha de fundo em cortes de podcast: nível, sincronia, mood e riscos

Data da pesquisa: 2026-10-14. Método: WebSearch e WebFetch. Complementa `01-pesquisa-documental.md`.
Contexto: Shorts de 20–90 s, conversa com pausas sempre cortadas, camas lo-fi da biblioteca
`biblioteca/trilhas/plano.json` (A neutro 76 bpm, B tensão 70 bpm, C leve/humor 84 bpm, 90 s cada).

Etiquetas, as mesmas do `01`, mais duas:

- **[DADO MEDIDO]**: número medido, com n quando a fonte informa
- **[DOC OFICIAL]**: YouTube, TikTok, Stability AI, W3C, AES
- **[DOC DE FERRAMENTA]**: Adobe, Opus Clip, Submagic, CapCut, plug-ins
- **[OPINIÃO]**: editor, blog ou fórum sem método
- **[NÃO VERIFICADO]**: só apareceu em blog de terceiro ou resumo de busca, sem a fonte primária confirmada
- **[NORMA]**: recomendação técnica de órgão (W3C, AES), não medição
- **[DERIVADO]**: conta minha a partir de números citados

---

## Resumo executivo

1. **Nível**: o único estudo com teste de escuta achado recomenda **pelo menos 10 LU** entre comentário e música; leigos preferiram **~4 LU a mais** que especialistas (n=22) [DADO MEDIDO]. A WCAG pede **20 dB** para áudio só-de-fala (nível AAA) [NORMA]. Guias de editor variam de −12 a −25 dB [OPINIÃO].
2. **Ducking**: não achei fonte medida de attack/release. Valores de ferramenta: attack 30–80 ms, release 250–700 ms (CapCut); fade de 800 ms no Auto Ducking do Premiere [DOC DE FERRAMENTA]. Release curto faz a música "voltar" nas respirações [OPINIÃO]. Com as pausas cortadas, quase não há onde a música subir: **nível fixo** é o caso natural (raciocínio meu, ver §1.3).
3. **Entrega**: −14 LUFS integrado e true peak ≤ −1 dBTP é **referência observada**, não spec publicada pelo YouTube [NÃO VERIFICADO como oficial]. O YouTube só abaixa o que vem alto [OPINIÃO consistente entre várias fontes].
4. **Retenção**: **não achei nenhum dado** de Shorts/TikTok com e sem música. Os dois experimentos controlados em vídeo (data videos, CHI 2026 e arXiv 2026) **não acharam efeito consistente em engajamento** [DADO MEDIDO, não é Short]. Números como "+30% de watch time" vêm de blogs sem estudo [NÃO VERIFICADO].
5. **Mood**: a música muda como o espectador interpreta a cena e julga o personagem, na direção do mood da música (Boltz 2001) [DADO MEDIDO, filme]. Trilha de tensão em fala neutra pode fazer o convidado parecer suspeito.
6. **Sincronia**: "music stop" antes do punchline, no tempo forte, com moderação; terminar a música num fim de compasso depois da última fala [OPINIÃO de editores]. Nenhum dado de retenção.
7. **Direitos**: Stable Audio 3.0 (Medium é open-weight) foi treinado em dados licenciados, e pela Community License "você é dono das saídas", comercial livre abaixo de US$ 1 mi de receita anual [DOC OFICIAL]. Música de IA "em geral não está no Content ID" [NÃO VERIFICADO].

---

## 1. Nível da trilha contra a voz

### 1.1 O que tem medição ou norma

| Fonte | Número | Etiqueta |
|---|---|---|
| Torcoli et al., JAES 67(12), 2019 (Fraunhofer IIS + Salford). Teste de escuta, n=22 (11 especialistas, 11 leigos), documentários de TV | Recomenda **≥ 10 LU** entre comentário e música (CoM) e **≥ 15 LU** sobre ambiência (CoA). Leigos preferiram LD **~4 LU maior** que especialistas, diferença significativa. Preferência muito individual. "Diálogo de locação requer LD maior" (sem número) | [DADO MEDIDO] |
| WCAG 2.2, critério 1.4.7 (AAA) | Fundo **≥ 20 dB abaixo** da fala, exceto sons de 1–2 s. Vale para áudio pré-gravado só-de-áudio, não para vídeo | [NORMA] |
| BBC, diretriz após *Wonders of the Universe* (BroadcastNow) | Sugestão de **baixar a música em 4 dB** em todos os programas, por reclamação de inteligibilidade | [OPINIÃO institucional, sem teste publicado achado] |
| Estudo JASA 2011 (nível aceitável de fala em ruído, jovens e idosos) | Limite inferior aceitável com relação fala/ruído de **+15 dB** (ruído 50–55 dB(A)) e **+10 dB** (60–70 dB(A)). Ruído, não música | [DADO MEDIDO, só resumo lido] |

Leitura para o app [DERIVADO]: corte de podcast é diálogo de locação (sala, dois microfones),
não locução de estúdio; o público é leigo (+4 LU sobre o especialista); e o Short toca em
alto-falante de celular. As três coisas empurram para cima do piso de 10 LU. 20 dB é o teto
da norma de acessibilidade.

### 1.2 O que é prática de editor

- Pro Moviemaker: música sob diálogo "normalmente na faixa de −12 a −20 ou menos" [OPINIÃO].
- Adorama: música de fundo em −25 a −18 dBFS [OPINIÃO; medida em pico, não comparável a LU].
- VidPros: −18 a −25 dB sob narração; "se você consegue acompanhar a música enquanto o narrador fala, está alta demais" [OPINIÃO].
- VoxBooster (streaming): voz −12 LUFS, música −20 LUFS ou menos, ou seja, ~8 LU [OPINIÃO].
- 4K Shooters (2015): só −3 a −9 dB abaixo do diálogo [OPINIÃO; fora da curva das demais].
- Choppity: música "em torno de 10 a 20% do nível da voz" [DOC DE FERRAMENTA; 10–20% de amplitude ≈ −20 a −14 dB, conta minha].

As fontes discordam porque medem coisas diferentes (pico dBFS, dB relativo, LUFS). **Para o app,
a medida certa é loudness integrada (LUFS) da voz contra a da música, cada uma medida sozinha**,
que é a métrica do Torcoli.

### 1.3 Ducking: sidechain contra nível fixo

- Ferramentas: CapCut sugere duck de **6–12 dB**, attack **30–80 ms**, release **250–700 ms** [DOC DE FERRAMENTA]. Vindral: ratio padrão 4:1 [DOC DE FERRAMENTA]. VoxDucker: attack padrão 10 ms; 1–10 ms "duck instantâneo", 50–200 ms deixa vazar o início da fala [DOC DE FERRAMENTA].
- Adobe Premiere, Auto Ducking: parâmetros "Reduce By" (dB) e "Fade Duration" (ms); o padrão citado é **800 ms**, que um tutorial chama de "lento demais" [DOC DE FERRAMENTA + OPINIÃO]. O padrão de dB não está documentado; −23 dB aparece num curso, inferência.
- SmartSound: release curto faz a música "voltar entre as respirações"; "erre para o lado longo" [OPINIÃO].
- Torcoli et al. notam que **não há detalhe técnico de ducking documentado em manuais de mixagem nem em recomendações de broadcaster** [DADO MEDIDO sobre a literatura].

**Não achei** fonte que trate de ducking com fala quase contínua. Raciocínio [DERIVADO]: no
corte, as pausas já saíram, então o sidechain ficaria abaixado quase o tempo todo e só
"respiraria" nos micro-gaps entre palavras, o que vira bombeamento (pumping). Nível fixo com
fade de entrada e saída dá o mesmo resultado sem esse risco. Ducking só faz sentido se houver
trecho sem fala maior que o release (por exemplo, abertura visual antes da primeira fala).

---

## 2. Loudness de entrega (YouTube e Shorts)

- **O YouTube não publica alvo de loudness.** Engenheiros observam a normalização em torno de **−14 LUFS**, e ela só abaixa: vídeo mais alto é reduzido, vídeo mais baixo fica como está [NÃO VERIFICADO como oficial; consistente em IRPR Sound, Production Advice "Stats for Nerds" e outros]. Consequência: mixar acima de −14 não ganha volume, só perde dinâmica; mixar abaixo sai mais baixo que os vizinhos do feed.
- **True peak**: a maioria recomenda **≤ −1 dBTP** [OPINIÃO consistente]. Spotify (música): −14 LUFS e ≤ −1 dBTP, ou ≤ −2 dBTP se o master for mais alto que −14 [DOC OFICIAL, via resumo de busca]. Apple Podcasts: −16 LKFS ±1, true peak ≤ −1 dBFS [DOC OFICIAL, citado pela WBUR, página da Apple não aberta]. AES TD1008: fala e conteúdo misto em **−18 LUFS** para streaming [NORMA]; o −1 dBTP é do TD1004 anterior. EBU R128 de distribuição pede −3 dBTP por causa de codecs com perda [NORMA, citada pelo Production Expert].
- **Stable volume** do YouTube: "equilibra a faixa entre partes baixas e altas, ajustando o volume continuamente"; **ligado por padrão**; não disponível para todo vídeo [DOC OFICIAL, Help 14106294]. **Voice boost** "reduz sons de fundo e destaca a fala", no computador e na TV [DOC OFICIAL]. Nenhuma das duas páginas menciona Shorts.
- Mono mede ~3 dB abaixo de estéreo com a mesma percepção (Podnews/Auphonic) [OPINIÃO técnica].

---

## 3. Canais de cortes usam música? Há efeito em retenção?

### 3.1 Uso

- **Não achei levantamento** de quantos canais de cortes (BR ou EUA, finanças ou não) usam trilha de fundo. Os nossos corpora (`02`, `03`, 319 Shorts de finanças BR) **não mediram presença de música**: as 7 categorias de emoção existem, mas não há campo de áudio de fundo. Uma única observação manual cita "música antes da primeira fala" num vídeo de rua.
- Ferramentas de corte: Submagic tem biblioteca de música por mood/gênero com controle de volume; Opus Clip promete "balanceamento automático de voz e música" na página de ferramenta [DOC DE FERRAMENTA]. Não achei documentação de que alguma delas **adicione música por padrão** em cortes de podcast.
- Resenha do Opus Clip: música de fundo **no vídeo de origem** atrapalha transcrição e detecção de falante [OPINIÃO]. Vale para o app: transcrever antes de mixar.

### 3.2 Retenção: dado contra opinião

| Afirmação | Fonte | Etiqueta |
|---|---|---|
| Sem efeito consistente de música em persuasão, engajamento ou memória, em 6 data videos populares (pré-registrado, entre sujeitos) | Djavaherpour et al., CHI 2026 | [DADO MEDIDO, n não visto; não é Short] |
| Música padrão aumentou persuasão; música sob medida teve efeito misto; **música não aumentou engajamento**; emoção foi **mais intensa sem música** | Gomasta et al., arXiv 2601.17893 (2026) | [DADO MEDIDO, n não visto; não é Short] |
| Música mudou o humor do espectador, mas sem efeito direto na retenção de conteúdo de um documentário | Peters, dissertação Univ. Twente | [DADO MEDIDO, n não confirmado] |
| 88% dos usuários do TikTok consideram o som vital para a experiência | TikTok (pesquisa com usuários) | [DOC OFICIAL, autodeclarado] |
| 93% dos vídeos top do TikTok usam som | Smartly, sem definição de "top" | [NÃO VERIFICADO] |
| Música "até 30% mais watch time" / "22% mais conclusão" em Shorts | blogs sem estudo citado | [NÃO VERIFICADO] |
| Música "disfarça jump cuts" e dá consistência; ambiente suaviza, rítmica pede corte no tempo | RouteNote | [OPINIÃO] |
| Música costuma atrapalhar a mensagem; se usar, "bem lá no fundo" | ATD | [OPINIÃO] |

**Conclusão**: não há evidência de que trilha aumente retenção em Short falado. A justificativa
que sobra é estética (cola os jump cuts, dá identidade) e é opinião. Isso pede um **teste A/B
próprio**: os mesmos tipos de corte com e sem trilha, no mesmo canal.

---

## 4. Sincronia da música com a fala

- **Music stop**: parar a música para destacar uma fala, o punchline de uma piada ou um visual. Parar num tempo natural, "muitas vezes, mas nem sempre, no tempo forte". Se soar cortado, adoçar com batida ou prato. **Usar com moderação**, porque parar demais quebra o momentum. A pausa também serve de vão para trocar de música quando o tom muda (Film Editing Pro, edição de trailer) [OPINIÃO de editor].
- **Duração do silêncio**: um blog sugere segurar 1,5–3 s após o impacto [NÃO VERIFICADO; página de baixa qualidade]. Num corte sem pausas, 1,5–3 s de silêncio nem existe; a música para e a **fala** preenche.
- **Timing cômico**: o efeito entra "um tempo depois da fala, nunca na última palavra" (Morphic, biblioteca de SFX) [OPINIÃO].
- **Fim**: o tempo forte final da música deve cair **depois de toda a fala** (Artlist). Cortes de música no meio de frase musical soam errados; trabalhe em blocos de 4 ou 8 compassos (RouteNote) [OPINIÃO].
- **Não cortar em todo tempo**: tempos para ações, frases para seções; alinhamento exato só nos momentos-chave [OPINIÃO, resumo de busca de vários guias].
- **Entrada no hook**: **não achei fonte** sobre a música entrar no frame 0, depois do hook ou junto com ele.
- **Troca de mood dentro do Short**: **não achei fonte** específica para vídeo curto. O guia de trailer usa a troca só num ponto de virada narrativa, aproveitando um music stop [OPINIÃO]. Num corte de 20–90 s com um só arco, isso é raro.

Compassos das camas (4/4) [DERIVADO]: A 76 bpm = **3,16 s**; B 70 bpm = **3,43 s**; C 84 bpm = **2,86 s**.

---

## 5. Mood por conteúdo

- **Boltz (2001), *Music Perception* 18(4)**: clipes ambíguos com música positiva, negativa ou sem música. A música mudou a interpretação, a previsão do final e o que se lembrou uma semana depois, **na direção do mood da música**. Numa cena benigna com música negativa, o personagem foi descrito como "manipulador" e "mau" [DADO MEDIDO, filme; n não visto].
- Boltz, Schulkind & Kantra (1991), *Memory & Cognition*: música de fundo afeta a lembrança de eventos filmados [DADO MEDIDO, só citação].
- Revisão da Frontiers (2020): música de fundo dá "quadro interpretativo" e molda julgamento moral sobre personagens [revisão, não experimento].
- CHI 2026: participantes acharam a música "distraindo ou desencaixada" em alguns vídeos e útil quando combinava com o tom [DADO MEDIDO, qualitativo].
- TikTok: som e música "definem o mood" [DOC OFICIAL, sem número].

Implicação [DERIVADO]: em finanças, onde o convidado precisa parecer confiável, a cama B (tensão)
num corte de utilidade prática pode tingir o convidado de suspeito. O risco de errar o mood é
assimétrico, então na dúvida vai a neutra. Os corpora do projeto já classificam a emoção dominante;
no `03` (n=247) dá: espanto 51, utilidade 49, inspiração 48, humor 33, raiva 31, neutra 27, medo 8.

---

## 6. Riscos

### 6.1 Direitos e Content ID

- **Stable Audio 3.0**: Small, Small SFX e **Medium são open-weight**; todos "treinados em dados totalmente licenciados". Pela Stability AI Community License, "você é dono das saídas e pode distribuí-las e comercializá-las livremente". Licença Enterprise para organizações com **mais de US$ 1 mi** de receita anual [DOC OFICIAL, anúncio do Stable Audio 3].
- Exigência de registro e de exibir "Powered by Stability AI" no free tier: só numa resenha de terceiro [NÃO VERIFICADO]. Conferir o texto da licença.
- Música de IA "em geral não está registrada no Content ID" no início de 2026, mas acordos de processos contra plataformas de IA musical podem mudar isso sem aviso [NÃO VERIFICADO, blog de vendedor de música].
- **Biblioteca de Áudio do YouTube**: o YouTube sugere trocar áudio reivindicado por faixa da Biblioteca de Áudio para resolver uma reivindicação [DOC OFICIAL, Help 2902117]. Há relatos de faixa da biblioteca reivindicada mesmo assim [OPINIÃO, fórum].
- **Seletor de música do Shorts**: segundo terceiro, gera reivindicação que o criador não vê nem contesta, e cobre só vídeo < 60 s [NÃO VERIFICADO]. Não se aplica ao app, que embute a trilha no render.
- **Divulgação de IA**: o YouTube exige rótulo para conteúdo **realista** alterado ou sintético; "gerar música sinteticamente" aparece em resumos como exemplo. Música de fundo de IA que não se passa por artista real estaria isenta [NÃO VERIFICADO, só fontes secundárias].
- O YouTube lançou troca de trilha reivindicada por instrumental gerado por IA no Studio (EUA, desktop) [DOC OFICIAL via Music Business Worldwide].

### 6.2 Inteligibilidade, legenda e transcrição

- Whisper: num teste com ruído de pub, todos os modelos degradam rápido e pioram abaixo de **10 dB de SNR** [DADO MEDIDO, artigo do Whisper; ruído de conversa, não música]. Whisper Medium: WER ~4,3% a 10 dB e ~34% a −10 dB [DADO MEDIDO, slides, normalização desconhecida]. **Não achei curva de WER com música de fundo.**
- Música mascara mais em ouvintes de meia-idade: o SRT com música piorou 0,4–1,6 dB contra 2,1 dB com fala concorrente (Başkent 2014, JASA-EL) [DADO MEDIDO].
- Legenda automática do YouTube com música de fundo: **não achei dado**.
- Para o app [DERIVADO]: a transcrição já sai do áudio original, então a legenda queimada não é afetada. O risco fica na legenda automática do YouTube e em quem ouve no alto-falante.

---

## 7. Contradições e lacunas

1. **Nível**: de −3 a −25 dB entre editores, contra ≥ 10 LU (teste de escuta) e 20 dB (norma de acessibilidade). Só o Torcoli tem teste com ouvinte, e foi em TV.
2. **Retenção**: nenhuma fonte primária mede trilha em Short. Os estudos controlados acham efeito nulo ou misto em engajamento.
3. **Uso nos canais de cortes**: não medido por ninguém que eu tenha achado. Dá para medir no nosso corpus separando as fontes do áudio (por exemplo, a energia do *stem* não-vocal do HDemucs). Não rodei porque precisaria baixar os pesos do modelo.
4. **Ducking com fala contínua**, **entrada da música no hook** e **troca de mood no Short**: sem fonte.

---

## Regras propostas para o app

| # | Regra | Valor | Fonte |
|---|---|---|---|
| R1 | Diferença de loudness voz − música, medida em LUFS integrado de cada stem sozinho | **18 LU** (padrão); faixa aceita **14–20 LU**; **nunca < 12 LU** | Piso de 10 LU do Torcoli 2019 [DADO MEDIDO] + ~4 LU de preferência de leigos [DADO MEDIDO] + "diálogo de locação pede mais"; teto de 20 dB da WCAG 1.4.7 [NORMA]; a faixa −18 a −25 dB dos editores [OPINIÃO]. O 18 é escolha minha dentro desse intervalo [DERIVADO] |
| R2 | Nível da música fixo durante a fala, **sem sidechain** | ganho constante | Pausas cortadas não deixam vão para a música subir; release curto bombeia nas respirações (SmartSound) [OPINIÃO]; [DERIVADO] |
| R3 | Se houver trecho sem fala > 1 s (abertura visual, por exemplo) e ele quiser ducking | duck 6–12 dB, attack **50 ms**, release **500 ms** | CapCut 30–80 / 250–700 ms [DOC DE FERRAMENTA]; o valor do meio é escolha minha |
| R4 | Fade de entrada e de saída da cama | entrada **300 ms**; saída = **1 compasso** (A 3,16 s; B 3,43 s; C 2,86 s), terminando **no fim do vídeo** | Fim no tempo forte, depois de toda a fala (Artlist) [OPINIÃO]; durações dos compassos [DERIVADO]. **Sem fonte para os 300 ms** |
| R5 | Alinhar o fim pelo compasso: começar a cama no offset `compasso − (duração mod compasso)`, para o vídeo terminar numa barra | — | Blocos de 4/8 compassos; não cortar no meio da frase musical (RouteNote, Artlist) [OPINIÃO]; conta [DERIVADO] |
| R6 | Uma cama por Short, **sem troca de mood** dentro do corte | 1 cue | Troca de música só em virada narrativa, via music stop (Film Editing Pro) [OPINIÃO]; corte de 20–90 s tem um arco só [DERIVADO] |
| R7 | Music stop antes do punchline: **opcional, desligado por padrão**, no máximo **1 por Short**; para no tempo forte anterior à frase-payoff e não volta, ou volta no tempo forte seguinte ao fim dela | ≤ 1 | Film Editing Pro ("com moderação", tempo forte) [OPINIÃO]; timing cômico (Morphic) [OPINIÃO]. Ligar só depois de A/B |
| R8 | Mood pela `emocao_dominante` já classificada: humor → **C**; espanto, medo, raiva → **B**; utilidade, inspiração, neutra ou dúvida → **A** | — | A música muda o julgamento do personagem na direção do mood (Boltz 2001) [DADO MEDIDO]; o erro é assimétrico, então a dúvida vai para a neutra [DERIVADO]; categorias do `esquema_classificacao.md` |
| R9 | Loudness final do Short | **−14 LUFS integrado**, true peak **≤ −1 dBTP** (limitador de true peak) | −14 observado no YouTube [NÃO VERIFICADO como oficial]; −1 dBTP consistente em Spotify, Apple e AES TD1004 [DOC OFICIAL / NORMA] |
| R10 | Transcrever e gerar a legenda a partir da **voz sem trilha** | — | Whisper degrada abaixo de 10 dB de SNR [DADO MEDIDO, ruído]; música de fundo atrapalha a transcrição (resenha do Opus Clip) [OPINIÃO] |
| R11 | Guardar por Short: id da cama, prompt, seed, hash do arquivo e modelo (Stable Audio 3.0 Medium), para contestar reivindicação de Content ID | — | Community License: dono das saídas, comercial < US$ 1 mi [DOC OFICIAL]; risco de mudança no Content ID [NÃO VERIFICADO] |
| R12 | Trilha liga/desliga por corte e fica registrada, para um **A/B com e sem trilha** medindo viewed-vs-swiped e retenção | — | Nenhum dado de retenção em Short; estudos controlados dão efeito nulo ou misto (CHI 2026; arXiv 2601.17893) [DADO MEDIDO]; métricas no `01` §1.1 |

---

## 8. Fontes

### Oficiais e normas

- W3C, Understanding SC 1.4.7 Low or No Background Audio: https://www.w3.org/WAI/WCAG22/Understanding/low-or-no-background-audio.html
- YouTube Help, controlar volume (Stable volume, Voice boost): https://support.google.com/youtube/answer/14106294?hl=en
- YouTube Help, melhorias de vídeo e áudio: https://support.google.com/youtube/answer/16619284?hl=en
- YouTube Help, remover conteúdo reivindicado: https://support.google.com/youtube/answer/2902117?hl=en
- Stability AI, anúncio do Stable Audio 3: https://stability.ai/news-updates/meet-stable-audio-3-the-model-family-built-for-artistic-experimentation-with-open-weight-models
- Stability AI, licenças: https://stability.ai/license
- TikTok Ads, creative best practices: https://ads.tiktok.com/help/article/creative-best-practices?lang=en
- TikTok Ads, blog de criativos de melhor desempenho: https://ads.tiktok.com/business/en-US/blog/creative-best-practices-top-performing-ads
- Music Business Worldwide, troca de trilha por IA no Studio: https://www.musicbusinessworldwide.com/youtube-creators-hit-by-music-copyright-claims-can-now-replace-tracks-with-ai-at-the-touch-of-a-button/
- AES TD1008 (resumo): https://productionadvice.co.uk/td1008/ e https://www.radioworld.com/?p=115138
- AES TD1004 e EBU R128 (−1 / −3 dBTP): https://www.production-expert.com/production-expert-1/aes-update-loudness-recommendations-for-audio-only-streaming
- Apple Podcasts e Spotify, loudness (via WBUR e Auphonic): https://www.wbur.org/citrus/2020/07/02/lufs-loudness-public-radio-npr-spotify-google e https://auphonic.com/blog/2019/06/12/the-new-loudness-target-war/
- Podnews, LUFS para podcasters: https://podnews.net/article/lufs-lkfs-for-podcasters

### Estudos com dados e acadêmicos

- Torcoli et al. 2019, Preferred levels for background ducking (JAES 67(12)): https://cris.fau.de/publications/234640600
- Resumo do Fraunhofer IIS sobre o mesmo estudo: https://www.audioblog.iis.fraunhofer.com/?p=4251
- Djavaherpour et al., Does Background Music Matter in Data Videos? (CHI 2026): https://openaccess.city.ac.uk/id/eprint/37604/
- Gomasta et al., Investigating How Music Affects Persuasion, Engagement, and Emotion in Data Videos: https://arxiv.org/abs/2601.17893
- Peters, música de fundo em documentários (Univ. Twente): https://purl.utwente.nl/essays/87899
- Boltz 2001, Musical soundtracks as a schematic influence: https://scholarship.haverford.edu/psychology_facpubs/20
- Boltz, Schulkind & Kantra 1991: https://scholarship.haverford.edu/psychology_facpubs/260
- Frontiers in Psychology 2020 (música e interpretação de personagens): https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2020.02242/epub
- Başkent et al. 2014, música e fala como mascaradores em meia-idade: https://dbspl.nl/pubs/2014%20baskent%20Susceptibility%20to%20interference%20by%20music%20and%20speech%20maskers%20in%20middle-aged%20adults%20jasaEL.pdf
- Nível aceitável de fala em ruído, jovens e idosos (JASA 2011): https://labs.sonicfield.org/library/acceptable-range-of-speech-level-in-noisy-sound-fields-for-young-adults-and-elde
- Radford et al., Whisper (ruído de pub e SNR): https://arxiv.org/pdf/2212.04356
- Whisper-AT (robustez a sons de fundo): https://arxiv.org/pdf/2307.03183
- Slides de ASR em húngaro (WER do Whisper por SNR): https://math-projects.elte.hu/media/works/451/presentation/hungarian_asr_slides.pdf

### Documentação de ferramentas

- CapCut, audio ducking: https://www.capcut.com/create/audio-ducking-for-clear-dialogue-in-video
- Vindral, sidechain ducking: https://composer-docs.vindral.com/operators/operators-sidechain-ducking.html
- VoxDucker, manual: https://unitedplugins.com/VoxDucker/documentation
- Adobe, automatic audio ducking: https://helpx.adobe.com/lv/premiere-pro/how-to/automatic-audio-ducking.html
- Motion Array, Auto Ducking no Premiere: https://blog.motionarray.com/learn/premiere-pro/auto-ducking-premiere-pro/
- Choppity, música de fundo e mixagem: https://help.choppity.com/articles/0057970-background-music-sfx-and-volume-mixing
- Submagic, adicionar música de fundo: https://www.submagic.co/pt-br/features/add-background-music-to-video
- Opus Clip, adicionar áudio ao vídeo: https://www.opus.pro/tools/add-audio-to-video

### Opinião e blogs (usados só como indício, marcados no texto)

- Film Editing Pro, "music stop": https://www.filmeditingpro.com/?p=12897
- Artlist, editar música no vídeo: https://artlist.io/blog/how-to-add-music-to-a-video/
- RouteNote, sincronizar música e imagem: https://licensing.routenote.com/blog/?p=9560
- RouteNote, música e efeitos para retenção: https://licensing.routenote.com/blog/?p=9382
- Morphic, rimshot e timing cômico: https://morphic.com/resources/sounds/rimshot-sound-effect
- SmartSound, ducking e automação: https://cloud.smartsound.com/audio-ducking-and-automation/
- VidPros, música alta demais: https://vidpros.com/fix-background-music-too-loud-video/
- Adorama, níveis de áudio: https://www.adorama.com/alc/?p=118366
- Pro Moviemaker, primavera 2019: https://online.bright-publishing.com/view/322383/49/
- 4K Shooters, níveis de áudio (2015): https://4kshooters.net/2015/08/17/what-are-the-optimal-audio-levels-for-your-video-production
- VoxBooster, voz e música para streamers: https://voxbooster.com/blog/mix-voice-with-background-music
- IRPR Sound, LUFS para YouTube: https://sounddesign.irpr.agency/guides/what-is-the-right-lufs-for-youtube-podcast-broadcast/
- Production Advice, Stats for Nerds: https://productionadvice.co.uk/stats-for-nerds/
- BroadcastNow, BBC e a música 4 dB mais baixa: https://www.broadcastnow.co.uk/audio-experts-call-for-caution/5025307.article
- ATD, "seu podcast não precisa de música": https://www.td.org/insights/no-your-podcast-does-not-need-music
- Smartly, boas práticas de criativo no TikTok: https://www.smartly.io/blog/top-5-tiktok-creative-best-practices
- Foxi Music, Content ID e música de IA (vendedor): https://www.foximusic.com/blog/content-id-music-guide-monetization/
- Foxi Music, biblioteca de música do Shorts (vendedor): https://www.foximusic.com/blog/youtube-shorts-copyright-music-library-guide/
- Marc Andrews, resenha do Opus Clip 2026: https://marcandrews.com/opus-clip-review-2026-ai-video-shorts-tool-tested/
- Search Engine Journal, divulgação de IA no YouTube: https://searchenginejournal.com/youtube-introduces-mandatory-disclosure-for-ai-generated-content/511392
