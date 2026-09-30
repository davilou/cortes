# Pesquisa documental: o que faz um corte de podcast viralizar em Shorts, Reels e TikTok

Data da pesquisa: 2026-09-30. Método: WebSearch e WebFetch. Toda afirmação traz uma etiqueta:

- **[DADO MEDIDO]**: número medido, com n quando a fonte informa
- **[DOC OFICIAL]**: YouTube, Meta/Instagram, TikTok, CVM/ANBIMA
- **[DOC DE FERRAMENTA]**: Opus Clip, Vizard, Klap, Submagic, Descript, Munch
- **[OPINIÃO]**: criador, guru ou blog sem método
- **[NÃO VERIFICADO]**: número que só apareceu em blog de terceiro ou snippet de busca, sem a fonte primária confirmada

---

## Resumo executivo

1. No feed de Shorts, o **primeiro gargalo é a decisão de ficar ou arrastar**. O YouTube expõe isso como a métrica "Viewed vs. Swiped away" [DOC OFICIAL]. Numa amostra de 5.400 Shorts, os melhores tinham 70–90% de "viewed", e abaixo de 60% raramente iam bem [DADO MEDIDO].
2. O **gancho precisa estar no 1º–3º segundo**. Meta/Nielsen: 47% do valor de uma campanha de vídeo acontece nos 3 primeiros segundos [DADO MEDIDO, anúncios]. O TikTok manda apresentar a proposta nos primeiros 3 segundos [DOC OFICIAL].
3. **Quando o detector usa só a transcrição, ele perde momentos.** Num dataset de 13 mil episódios rotulado pelo "mais repetidos" do YouTube, GPT-4o e Gemini sem ajuste foram mal, e juntar áudio com texto melhorou o resultado [DADO MEDIDO].
4. No humor, **a risada é o rótulo natural de um momento engraçado**. Em modelos de "momento engraçado", o áudio carrega mais da metade do peso preditivo [DADO MEDIDO].
5. Emoção de alta ativação (espanto, raiva, ansiedade) e utilidade prática aumentam o compartilhamento; tristeza diminui [DADO MEDIDO, artigos do NYT, não vídeo].
6. **Duração: as fontes discordam** (ver Contradições). O YouTube oficial diz que não existe "duração mágica" [DOC OFICIAL].
7. **Legendas**: no teste interno do Facebook, legenda aumentou o tempo de visualização em 12% em anúncios [DADO MEDIDO, sem n publicado]. 69% dos adultos dos EUA assistem sem som em público (n=5.616) [DADO MEDIDO, autodeclarado].
8. **Tela dividida com gameplay**: não achei dado de retenção em plataforma. Em laboratório, a gameplay não ajudou a memória e reduziu o interesse autodeclarado (n=100) [DADO MEDIDO].
9. **Originalidade é risco de distribuição**: Instagram tira de recomendação contas que mais repostam do que criam [DOC OFICIAL]. O YouTube não monetiza "clipes com pouca ou nenhuma narrativa" [DOC OFICIAL]. Isso afeta diretamente um app de cortes.
10. **Nenhuma ferramenta publica validação do seu "virality score"**. Os critérios documentados (gancho, fluxo, valor, tendência) são descritivos, sem taxa de acerto [DOC DE FERRAMENTA].

---

## 1. MOMENTO: que trecho pegar

### 1.1 O que as plataformas medem (o alvo do seletor)

- **"Shown in feed" e "Viewed (vs. swiped away)"** existem no YouTube Analytics para Shorts. O "viewed" é "a porcentagem de vezes em que espectadores viram seus Shorts versus arrastaram" [DOC OFICIAL, YouTube Help 12942217].
- Todd Sherman (produto de Shorts do YouTube) explicou que a maior parte das views de Shorts vem do feed, sem escolha consciente do espectador. O sistema acha uma "audiência semente" e, conforme ela reage, amplia ou corta a distribuição [DOC OFICIAL, entrevista Creator Insider via MediaPost e YouTube Blog].
- **Desde 31/03/2025, o YouTube conta uma view a cada início ou replay do Short**, sem tempo mínimo. A métrica antiga continua como "engaged views", que é a usada para monetização [DOC OFICIAL, noticiado por Sprout Social, gHacks e MediaPost]. Consequência: a view virou métrica de alcance, e o sinal de qualidade passa a ser "viewed vs swiped" e retenção.
- **O "average percentage viewed" pode passar de 100%** em Shorts por causa do loop/replay [OPINIÃO/blogs; não achei a frase exata no YouTube Help].
- Galloway & Gileta (abril/2023) estudaram **5.400 Shorts de 33 canais, somando 3,3 bi de views** [DADO MEDIDO]:
  - VVSA (viewed vs swiped) abaixo de 60%: raramente performou; os melhores ficaram entre 70–90%; VVSA alto sozinho não garante sucesso.
  - Não acharam relação forte entre likes, comentários ou compartilhamentos e o desempenho.
  - Ressalva: dado de 2023, anterior à mudança na contagem de views e aos Shorts de 3 min.
- **SnapUGC (ECCV 2024): 90.000 vídeos curtos do Snapchat Spotlight, 10–60 s, cada um com mais de 2.000 views** [DADO MEDIDO]:
  - Os autores definem "Engagement Continuation Rate" como a fração de espectadores que assistiu **pelo menos 5 segundos**, ou seja, a abertura é tratada como métrica própria.
  - As distribuições são bimodais "por causa do design de UI que incentiva arrastar".
  - Nota de qualidade técnica (MOS) de datasets de VQA correlaciona fraco com engajamento (0,073–0,305). **Qualidade de imagem não explica engajamento.**
  - Somar som de fundo, título e texto e descrições textuais do conteúdo melhorou a predição (SRCC de 0,625 para 0,696).

### 1.2 Critérios de seleção com dado

| Critério | Evidência | Etiqueta |
|---|---|---|
| **Gancho imediato** (1–3 s) | Meta/Nielsen: 47% do valor de campanha nos 3 primeiros s, 74% até 10 s (anúncios, Facebook) | [DADO MEDIDO, n não publicado] |
| Gancho imediato | TikTok: "apresente a proposta nos primeiros 3 segundos"; "priorize o gancho nos primeiros 6 segundos" | [DOC OFICIAL] |
| Gancho imediato | Jenny Hoyos no blog do YouTube: "você tem um segundo para fisgar"; fórmula chocar, intrigar, satisfazer | [OPINIÃO de criadora, publicada em canal oficial] |
| **Emoção de alta ativação** | Berger & Milkman: artigos do NYT durante 3 meses; conteúdo de espanto, raiva ou ansiedade é mais compartilhado, tristeza é menos. O efeito vale controlando surpresa, interesse e utilidade prática, e os três também se associam positivamente a viralizar | [DADO MEDIDO, texto e não vídeo; tamanho exato não confirmado por mim: o PDF não abriu] |
| **Utilidade prática / surpresa** | Mesmo estudo | [DADO MEDIDO] |
| **Tipos de abertura** | 9.654 TikToks de 30 contas de marcas na Estônia. Frequência: pergunta ou afirmação provocativa 29,3%; *in medias res* (começa no meio da ação) 25,7%; imagem surpreendente 22,3%. Variáveis de gancho aparecem entre os preditores fortes, e gancho dirigido a nicho se associa a *saves*. Tamanho de efeito por tipo não publicado | [DADO MEDIDO] |
| **Pessoa na tela / close** | TikTok, 400 vídeos rotulados: número de seguidores é o preditor mais forte; plano fechado ou médio, texto sobreposto e ponto de vista também pesam | [DADO MEDIDO, n pequeno] |
| Pessoa na tela | Estudo da Estônia: conteúdo centrado em pessoa tem efeito positivo em likes | [DADO MEDIDO] |
| **Trecho auto-contido com desfecho** | Opus: "Flow: flui logicamente, com conclusão satisfatória"; Descript: "cortes curtos e auto-contidos" | [DOC DE FERRAMENTA] |
| **Pico de áudio / emoção vocal** | Rhapsody (COLM 2025): 13 mil episódios de podcast, destaques = "mais repetidos" do YouTube. Transcrição sozinha é insuficiente; áudio + texto melhora; GPT-4o e Gemini zero-shot "têm dificuldade" | [DADO MEDIDO] |
| **Risada (humor)** | FunnyNet-W define momento engraçado como "clipe de n s seguido de risada". Áudio sozinho 84,5% F1 contra texto 77,8% e visual 73,2% (Friends); tudo junto 88,2% | [DADO MEDIDO, séries de TV e TED] |

**Implicação para o detector (inferência minha, não fonte):** o Rhapsody é o análogo mais próximo do problema do app, porque o rótulo "mais repetidos" é sinal real de audiência em podcast. Ele mostra que só um LLM sobre a transcrição não basta. Use energia e prosódia do áudio, risada e mudança de falante como sinais junto com o texto.

### 1.3 O que as ferramentas documentam publicamente

| Ferramenta | Critério documentado | Duração | Validação pública |
|---|---|---|---|
| **Opus Clip** (help center) | Score de 0 a 99, com 4 eixos. **Hook**: a introdução prende e se liga ao tema? **Flow**: progressão lógica e conclusão satisfatória? **Value**: oferece valor, ressoa emocionalmente, cria conexão? **Trend**: alinhado a tendências e interesses atuais? No ClipAnything, também avalia aderência ao prompt | Blog da Opus: janelas de ~25–60 s [DOC DE FERRAMENTA, via snippet de busca] | **Nenhuma**: sem taxa de acerto, sem metodologia [DOC DE FERRAMENTA] |
| **Vizard** | "Estrutura semântica, mudanças emocionais", "momentos de alta tensão, frases perspicazes, expressões emocionais fortes, pontos controversos" | "Destaques de 30–90 s" | Nenhuma |
| **Klap** | "Insights citáveis, revelações surpreendentes, trocas emocionais, momentos de debate, frases de rir alto"; score de 0 a 100 | Ajustável | Nenhuma |
| **Descript** | Só "os momentos mais engajadores"; o usuário pode dar tema ou critério | 10 s a 5 min | Critério não publicado |
| **Munch** | Descrições de terceiros dizem que ele cruza com tendências de Google, Meta e TikTok e pontua por palavra-chave e tema | não achado | Não achei doc oficial [NÃO VERIFICADO] |
| **Submagic** | Magic Clips extrai "momentos de maior engajamento"; o foco documentado é legenda | não achado | Nenhuma |

**Leitura crítica:** todos convergem em quatro critérios: gancho, emoção ou tensão, frase citável ou polêmica, e trecho completo. Esses critérios batem com a literatura acadêmica (arousal, utilidade, pessoa, abertura forte). Nenhuma ferramenta publica acurácia. Resenhas de terceiros dizem que o Vizard seleciona por "energia de áudio, troca de falante e densidade de palavras-chave" e que erra o sentido do trecho [OPINIÃO].

### 1.4 Não achado

- Estudo com dado sobre **"número no gancho"** (ex.: "R$ 1 milhão"). Um snippet citou "front-loaded numeric hooks" como alavanca num dataset de 4.983 ganchos do TikTok, mas não consegui abrir a fonte primária [NÃO VERIFICADO].
- Estudo com dado sobre **"polêmica" em corte de podcast** especificamente. O mais próximo é o efeito de raiva/ansiedade de Berger & Milkman.

---

## 2. EDIÇÃO: o que é seguro fazer

### 2.1 Duração

| Fonte | Achado | Etiqueta |
|---|---|---|
| YouTube (Sherman, 2023) | Não existe "duração mágica"; conte a história no tempo que ela pede | [DOC OFICIAL] |
| YouTube (out/2024) | Shorts de até **3 min** a partir de 15/10/2024, formato quadrado ou vertical | [DOC OFICIAL] |
| Galloway (n=5.400, 2023) | A maioria dos Shorts tinha 20–40 s; os mais longos foram melhor na média; AVD acima de 50 s deu média de 4,1 mi de views | [DADO MEDIDO; confunde duração com qualidade] |
| Socialinsider (111 mil vídeos, jan–jun/2026) | **IG Reels**: pico em 45–60 s (0,35% de ER, 10.374 views) contra menos de 30 s (0,28%, 4.700); queda acima de 180 s. **TikTok**: ER mais alto abaixo de 30 s (6,0%), views com pico em 120–180 s (12.000) | [DADO MEDIDO, contas de marca] |
| Finfluencers UK (13.215 TikToks) | Correlação **mínima** entre duração e engajamento | [DADO MEDIDO] |
| Opus Clip blog | 15–30 s com "retenção acima de 80%" | [DOC DE FERRAMENTA, sem n nem método] |
| Guo et al. 2014 (6,9 mi de sessões, edX) | Vídeo mais curto engaja mais; talking head informal engaja mais que aula filmada | [DADO MEDIDO, contexto MOOC e não feed] |

### 2.2 Primeiros 3 segundos

- O TikTok manda apresentar a proposta em 3 s e o gancho em até 6 s [DOC OFICIAL].
- O Instagram (Mosseri) diz que os 3 primeiros segundos são o gancho e não exigem clickbait [DOC OFICIAL, citado por Inman; não abri o vídeo original].
- Números como "50–60% de quem sai sai nos 3 primeiros segundos" e "80% de retenção nos 3 s" vêm de blogs (Opus e outros) sem n [DOC DE FERRAMENTA/OPINIÃO].
- O "65% de quem vê 3 s continua até 10 s" é atribuído ao Facebook via 3Play Media [NÃO VERIFICADO na fonte primária].

### 2.3 Legendas

| Fonte | Achado | Etiqueta |
|---|---|---|
| Facebook (testes internos) | Legenda aumenta o tempo de visualização em **12%** em média; A&W Canada teve +25%; 41% dos anúncios em vídeo eram "sem sentido sem som" | [DADO MEDIDO, anúncios, n não publicado] |
| Verizon Media/Publicis (abr/2019, n=5.616 adultos EUA) | 69% assistem sem som em público; 80% dizem ser mais propensos a terminar o vídeo com legenda | [DADO MEDIDO, **autodeclarado**] |
| SnapUGC | Somar texto (título e descrições) melhora a predição de engajamento | [DADO MEDIDO; "captions" ali são descrições do conteúdo, **não** legenda queimada, então não prova efeito de legenda] |
| TikTok, 400 vídeos | Texto sobreposto está entre os traços dos virais | [DADO MEDIDO, n pequeno] |
| Eye-tracking em vídeo vertical (Applied Cognitive Psychology, 2026, n=211, webcam) | Legenda de 2 linhas atrai mais fixação, mais revisitas e menos pulos que a de 1 linha, mesmo controlando o nº de caracteres. **Implicação: 2 linhas roubam mais atenção do rosto** | [DADO MEDIDO; abstract via snippet, a página deu 403] |
| TikTok Ads | "5–10 palavras por segundo" de texto; manter o texto dentro da safe zone da UI | [DOC OFICIAL] |
| Submagic | Legenda palavra a palavra, com destaque e animação sincronizada à voz | [DOC DE FERRAMENTA] |
| "Palavra a palavra dá 2,3x de conclusão" | Não achei a fonte primária | [NÃO VERIFICADO] |
| "Legenda queimada dá +15–25% de retenção" (Opus) | "Testei dezenas de variações" | [DOC DE FERRAMENTA, sem método] |
| Safe zone "evite os 20% de baixo e os 10% da direita" | Aparece em blogs; a página oficial só diz "dentro da safe zone" | [NÃO VERIFICADO] |

**Não achado:** estudo controlado comparando legenda palavra a palavra com frase inteira, ou legenda no centro com legenda embaixo, medindo retenção em plataforma.

### 2.4 Layout / reenquadramento

- As ferramentas documentam como padrão: 9:16 com o falante centralizado (Vizard); tela dividida para 2 pessoas, 3 ou 4 quadros para painel e picture-in-picture para convidado remoto, com rastreio automático de falante (Klap); presets 9:16 e 1:1 (Descript) [DOC DE FERRAMENTA]. Nenhuma publica dado de retenção por layout.
- O TikTok recomenda pessoas na tela e estilo "DIY, não polido demais" [DOC OFICIAL].
- **Plano fechado ou médio** está associado a virais (TikTok, n=400) [DADO MEDIDO]. Isso sustenta reenquadrar no falante em vez de manter o quadro aberto com blur.
- **Gameplay embaixo (split/"sludge")**: em dois experimentos pré-registrados (n=75 e n=100), a gameplay não mudou a memória do conteúdo (efeitos de d ≤ 0,09). No estudo 2, **o interesse autodeclarado caiu** (4,02 contra 4,25, p=0,03). Os estudos não mediram tempo de tela nem preferência em feed [DADO MEDIDO, laboratório].
- **Quadro 16:9 com fundo borrado**: não achei nenhum dado.
- **B-roll**: o Vizard oferece "AI B-roll" [DOC DE FERRAMENTA]. Não achei dado de efeito.

### 2.5 Ritmo de cortes, zoom, título fixo, loop

- **Ritmo**: "um corte a cada 2–4 s" aparece no blog da Opus, sem n [DOC DE FERRAMENTA]. O TikTok recomenda "transições, stickers e gráficos" para reter [DOC OFICIAL, sem dado]. **Não achei estudo medido** sobre frequência de corte ou zoom em vídeo curto.
- **Zoom / punch-in**: sem dado. Só opinião.
- **Título fixo na tela**: sem dado específico. Os indícios indiretos são o texto sobreposto no n=400 e o dado de 41% sem som.
- **Loop**: o YouTube conta replay como view desde 03/2025 [DOC OFICIAL], então o loop agora infla as views diretamente. Não achei dado medido de que "final que emenda no início" aumenta retenção [OPINIÃO].
- **Áudio**: no SnapUGC, o modelo com áudio (VideoLLaMA2) superou o modelo só visual (Qwen2.5-VL) em predição de engajamento [DADO MEDIDO]. Um número do vidIQ ("áudio em tendência dá 2,5x views") não teve a fonte aberta [NÃO VERIFICADO]. Para corte de podcast, a fala é o áudio.

### 2.6 Originalidade (restrição dura para um app de cortes)

- **YouTube (política de conteúdo reutilizado)**:
  - Não é monetizável: "clipes de momentos do seu programa favorito editados juntos com pouca ou nenhuma narrativa" e conteúdo "sem modificações substanciais".
  - É monetizável: material de outros criadores editado "com storyline e comentário", e clipes para análise crítica.
  - Desde jul/2025, conteúdo "repetitivo ou produzido em massa", ou feito "com template com pouca ou nenhuma variação", é "inautêntico".
  [DOC OFICIAL]
- **Instagram**:
  - Contas que postam **majoritariamente conteúdo de terceiros** (avaliação mensal) saem das recomendações. Valia para Reels e foi estendido a fotos e carrosséis em 30/04/2026.
  - Marca d'água, corte leve, **legenda** ou crédito sobre obra alheia **não** contam como originalidade.
  [DOC OFICIAL, via Social Media Today e RouteNote]
- Os números atribuídos a Mosseri ("sends valem 3–5x likes", "original tem 40–60% mais distribuição", "marca d'água do TikTok reduz 15%") vêm de blogs [NÃO VERIFICADO]. O oficial é: watch time, sends e likes são sinais, e originalidade conta.
- **Implicação:** cortes do podcast do próprio usuário não têm problema. Para canal de cortes de terceiros, o template idêntico em massa é justamente o que as duas plataformas penalizam.

---

## 3. Específico de finanças e humor

### Finanças (PT-BR)

- **ANBIMA FInfluence** monitora semestralmente os finfluencers brasileiros no X, YouTube, Instagram e Facebook [DOC OFICIAL/DADO MEDIDO].
- **8ª edição (2º sem/2024)**: 741 influenciadores, 394.558 posts. Média de 2.965 interações por post; no **YouTube, 10.816**; no Instagram, 2.130.
- **6ª edição (2º sem/2023)**: 305 mil posts, 534 influenciadores.
  - Temas mais citados: ações (23,4%), ações brasileiras (11,6%), cripto (11%).
  - Temas com **mais interação por post**: fundos (5.916), CDB (5.876), FII (5.692) e produtos bancários (5.539). O YouTube teve média de 18.029 interações por vídeo sobre fundos.
  - **O tema mais falado não é o que mais engaja**: renda fixa e fundos concretos, próximos do bolso, engajam mais que "mercado".
- **Influenciadoras**: 21% mais engajamento (3.686 contra 3.041), com abordagem educativa ("aprenda", "aula") [DADO MEDIDO, ANBIMA 7ª ed. via snippet].
- **Finfluencers UK** (13.215 TikToks, 71 criadores, abr–set/2024) [DADO MEDIDO]:
  - Quatro temas: empreendedorismo/renda extra, imóveis, trading ativo, poupança/orçamento.
  - Correlação mínima entre duração e engajamento.
  - Aviso de risco é raro e se concentra em trading.
- **Risco regulatório**:
  - A CVM não regula o finfluencer como categoria, mas quem faz análise ou recomendação de valor mobiliário cai nas Resoluções CVM 19/20 [DOC OFICIAL, via Conjur/Suno].
  - A CVM estudou recomendar a divulgação obrigatória de conteúdo pago [DOC OFICIAL].
  - **Inferência minha:** um corte que isola "compra X" sem o contexto vira recomendação fora de contexto. O seletor deveria sinalizar trechos com recomendação de ativo específico.
- **Ponte com a literatura**: utilidade prática e ansiedade aumentam compartilhamento (Berger & Milkman) [DADO MEDIDO, texto]. Isso sustenta priorizar trechos do tipo "número concreto + consequência para o bolso" ou "erro que custa dinheiro". Não achei estudo específico de corte de podcast de finanças.

### Humor

- **Risada como detector**: FunnyNet-W usa risada como rótulo e o áudio pesa mais que texto e imagem [DADO MEDIDO]. Existem modelos abertos de segmentação de risada (ex.: LaughterSegmentation, Interspeech 2024; MultiLinguahah, multilíngue).
- **Emoção positiva de alta ativação** aumenta compartilhamento (Berger & Milkman) [DADO MEDIDO].
- Klap e Vizard listam "risadas" e "laugh-out-loud quotes" como gatilho [DOC DE FERRAMENTA].
- **Não achado**: estudo com dado sobre duração ou estrutura ideal de corte de humor (ex.: setup mais punchline, cortar logo após a risada). Existe um dataset de timing de stand-up (TIC-TALK, arXiv 2603.21803), mas não li os resultados.

---

## 4. Contradições entre fontes

1. **Duração ideal**. As fontes apontam em direções opostas:
   - Galloway (2023): mais longo foi melhor, 50–60 s.
   - Blog da Opus: 15–30 s.
   - Socialinsider 2026: 45–60 s no IG; no TikTok o ER é maior abaixo de 30 s, mas as views são maiores em 2–3 min.
   - Finfluencers UK: duração quase irrelevante.
   - YouTube: "não existe duração mágica".

   Resolução provável: o que manda é a retenção, e o vídeo longo só ganha quando segura. **Decisão prática:** a duração sai do conteúdo (trecho completo), não de um alvo fixo.
2. **Sherman em 2023** falava em "vídeos de um minuto ou menos". Em **out/2024** o YouTube liberou 3 min. Qualquer dado anterior a 2024 sobre duração está parcialmente obsoleto.
3. **O que é uma view**. Em 2023 era uma escolha deliberada ("deliberately watching"); desde 03/2025 conta cada início ou replay. Estudos antigos de "views" não são comparáveis aos novos.
4. **Likes importam?**
   - Galloway: likes, comentários e compartilhamentos sem relação forte com desempenho.
   - Blog do YouTube (2025): acompanhe a razão likes/views na primeira hora.
   - Instagram: sends e likes por alcance são sinais.

   As fontes não se reconciliam totalmente. Provavelmente o peso difere por plataforma.
5. **Tamanho do efeito da legenda**:
   - +12% (Facebook, anúncios).
   - +15–25% (Opus, sem método).
   - 2,3x (Submagic, segundo blog não verificado).

   Só o 12% tem fonte primária de plataforma.
6. **Gameplay em tela dividida**. As ferramentas oferecem como recurso de retenção. O único estudo controlado mostra **nenhum ganho de memória e menos interesse**, sem medir tempo de tela. Pelas regras de originalidade, o formato também pode parecer "template em massa".
7. **Virality score** é vendido como preditivo. O Rhapsody mostra que LLMs de ponta sem ajuste erram muito nessa tarefa, e nenhuma ferramenta publica acurácia.

---

## 5. Fontes

### Oficiais (YouTube, Meta, TikTok, reguladores)

- YouTube Help: dicas de analytics de Shorts: https://support.google.com/youtube/answer/12942217?hl=en-GB&co=YOUTUBE._YTVideoType%3Dshorts
- YouTube Community: métrica Viewed vs Swiped Away: https://support.google.com/youtube/community-video/273390203/new-youtube-shorts-metric-viewed-vs-swiped-away?hl=en
- YouTube Blog: Shorts deep dive (Todd Sherman e Jenny Hoyos): https://blog.youtube/creator-and-artist-stories/youtube-shorts-deep-dive/
- YouTube Blog: Five tips to master Shorts: https://blog.youtube/creator-and-artist-stories/five-tips-to-master-shorts/
- YouTube Blog: Tall updates coming to Shorts (3 min): https://blog.youtube/news-and-events/tall-updates-coming-to-shorts/
- MediaPost: Todd Sherman, insights: https://www.mediapost.com/publications/article/388588/youtube-shorts-product-lead-offers-insights-for-cr.html
- Mudança na contagem de views (mar/2025): https://support.sproutsocial.com/hc/en-us/articles/35874991211533-YouTube-Shorts-View-Count-Update-March-2025 e https://www.ghacks.net/2025/03/27/youtube-updates-shorts-view-count-methodology-to-align-with-industry-standards/
- YouTube: políticas de monetização (reused/inauthentic): https://support.google.com/youtube/answer/1311392?hl=en
- Related links entre Short e vídeo longo: https://www.tubefilter.com/2023/09/01/youtube-related-links-multi-format-creators-shorts-live-long-form/
- TikTok Ads: creative best practices: https://ads.tiktok.com/help/article/creative-best-practices?lang=en
- Meta: updated features for video ads (legenda +12%, Nielsen 47%/74%): https://www.facebook.com/business/news/updated-features-for-video-ads
- Instagram, originalidade (30/04/2026): https://www.socialmediatoday.com/news/instagram-updates-algorithm-to-benefit-original-creators/819016/ e https://routenote.com/blog/instagram-tightens-rules-reposted-content/
- Mosseri, dicas de Reels: https://www.inman.com/2025/03/07/head-of-instagram-reveals-secrets-to-social-media-success/
- ANBIMA FInfluence 8: https://www.anbima.com.br/pt_br/noticias/finfluence-8-engajamento-do-publico-com-finfluencers-e-o-maior-da-historia.htm
- ANBIMA FInfluence 6 (fundos): https://www.anbima.com.br/pt_br/noticias/finfluence-posts-sobre-fundos-sao-campeoes-em-engajamento-nas-redes-sociais.htm
- ANBIMA FInfluence 7 (relatório): https://www.anbima.com.br/data/files/18/24/20/24/655239102C02B139B82BA2A8/Relatorio-FInFluence-7ed.pdf
- B3 Bora Investir, sobre a ANBIMA: https://borainvestir.b3.com.br/noticias/finfluencers-estudo-da-anbima-traca-qual-o-perfil-e-temas-que-mais-engajam/
- CVM, estudo sobre influenciadores (2023): https://www.gov.br/cvm/pt-br/centrais-de-conteudo/publicacoes/estudos/20230418-air-influenciadores.pdf
- Conjur, influenciadores e investimentos: https://www.conjur.com.br/2025-dez-08/influenciadores-digitais-podem-falar-sobre-investimentos-em-redes-sociais/

### Estudos com dados e acadêmicos

- Galloway & Gileta, 3,3 bi de views (thread): https://threadreaderapp.com/thread/1646898356419981315.html
- SnapUGC, "Delving Deep into Engagement Prediction of Short Videos" (ECCV 2024): https://arxiv.org/abs/2410.00289
- Engagement Prediction com LMMs (VQualA 2025): https://arxiv.org/abs/2508.02516
- Rhapsody, detecção de destaques em podcasts (COLM 2025): https://arxiv.org/abs/2505.19429
- FunnyNet-W: https://arxiv.org/html/2401.04210v1
- Understanding Indicators of Virality in TikTok (n=400): https://arxiv.org/abs/2111.02452
- TikToks de marcas na Estônia (n=9.654): https://arxiv.org/html/2606.16053
- Finfluencers no TikTok UK (n=13.215): https://arxiv.org/abs/2607.05203
- Rubric/VLM para viralidade em edutainment: https://arxiv.org/abs/2512.21402
- Berger & Milkman, What Makes Online Content Viral?: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1528077
- Split-screen distraction (sludge), Cognitive Research 2026: https://pmc.ncbi.nlm.nih.gov/articles/PMC13018501/
- Eye-tracking de legenda de 1 contra 2 linhas em vídeo vertical: https://onlinelibrary.wiley.com/doi/10.1002/acp.70262
- Guo, Kim & Rubin 2014 (edX): https://www.cs.rochester.edu/hci/pubs/pdfs/edX-MOOC-video-production-and-engagement_LAS-2014.pdf
- Verizon Media/Publicis (sem som, legenda): https://www.forbes.com/sites/tjmccue/2019/07/31/verizon-media-says-69-percent-of-consumers-watching-video-with-sound-off/
- Socialinsider, estatísticas de vídeo 2026: https://www.socialinsider.io/social-media-benchmarks/social-media-video-statistics

### Documentação de ferramentas

- Opus Clip, Virality Score: https://help.opus.pro/docs/article/virality-score
- Opus Clip, ClipAnything: https://help.opus.pro/docs/article/9947095-clip-anything
- Opus Clip blog, duração ideal (sem método): https://www.opus.pro/blog/ideal-youtube-shorts-length-format-retention
- Vizard, AI Viral Clip Maker: https://vizard.ai/tools/ai-viral-clip-maker
- Klap, Podcast Clip Maker: https://klap.app/tools/podcast-clip-maker
- Descript, Create clips: https://help.descript.com/hc/en-us/articles/10119670449293-Create-clips-from-your-content
- Submagic, legendas: https://www.submagic.co/ai-caption
- Munch (só descrição de terceiros): https://contentcreators.com/tools/getmunch

### Opinião e blogs (usados só como indício, marcados no texto)

- vidIQ, algoritmo de Shorts: https://vidiq.com/blog/post/youtube-shorts-algorithm/
- 3Play Media, legendas no Facebook: https://www.3playmedia.com/blog/captions-increase-viewership-for-facebook-video-ads/
- Resenha do Vizard (limitações): https://fluxnote.io/guides/vizard-ai-video-review-2026
