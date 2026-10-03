# f9 Ilustrado — a coisa citada aparece na tela

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Um formato novo, f9 "Ilustrado". Quando a pessoa fala de uma coisa concreta, aparece na tela uma imagem dela enquanto ela fala; por exemplo, "Vans" mostra o tênis e "camisa do Corinthians" mostra a camisa (pedido do Davi, 2026-10-02). A base é o f7: tela cheia no rosto, corte seco na troca de câmera e legenda embaixo. A imagem entra como um **cartão** na metade de cima.

**Architecture:** a ilustração é uma etapa do projeto do corte, rodada só para o f9, em quatro passos:
1. **Deixas:** o `claude -p` lê a fala do corte e devolve, com schema obrigatório, a lista `{inicio_palavra, fim_palavra, coisa, busca}`, só com coisas concretas e visuais.
2. **Busca:** para cada deixa, a busca de imagens do DuckDuckGo (biblioteca `ddgs`, sem chave) traz até 4 candidatas, que são baixadas e normalizadas com o ffmpeg.
3. **Conferência:** uma **folha** com as candidatas de todas as deixas, numeradas, vai para **um** `claude -p` com `Read` liberado só na pasta da folha. Ele devolve, para cada deixa, o número da imagem que mostra a coisa, ou nenhuma.
4. **Montagem:** a deixa que sobrou com imagem vira um cartão no template `ilustrado.tpl`, e a deixa sem imagem fica registrada como "sem imagem". Nunca entra uma imagem qualquer (mesma regra do B-roll, spec §6).

Tudo fica em cache em `cortes/<n>/ilustracao/`. A ilustração só é refeita quando início ou fim mudam.

**Decisões tomadas sem o Davi (ele estava dormindo; registrar na spec):**
- **Fonte: busca na web (DuckDuckGo), não geração de imagem.** Testado em 2026-10-02: "tênis Vans Old Skool", "camisa do Corinthians" e "carro Fiat Uno" trouxeram o produto exato, de loja ou da Nike. A Wikimedia, por ser gratuita e licenciada, foi testada e errou produto ("Vans Old Skool" deu uma garagem de ônibus). A geração (FlowPool) gasta crédito e erra marca. **Risco:** fotos de terceiros, como o B-roll do YouTube (spec §10). Gravar `fonte_url` por imagem e marcar `licenca: desconhecida`.
- **Dependência nova `ddgs`:** é a única forma testada de busca de imagem sem chave; não há chave de Pexels, Bing ou Serp no ambiente. Entra em `pyproject.toml` com um comentário dizendo isso.
- **Conferência por folha numa chamada só por corte:** são cerca de 3,7 mil tokens fixos por chamada (`llm.py`). Uma chamada por deixa custaria 5–8 vezes mais cota da assinatura.
- **Cartão sem flash e sem zoom:** só uma entrada curta de opacidade (0,15 s) e a saída igual. O Davi pediu tirar flash e zoom das transições; o cartão é conteúdo, e não pode "piscar".
- **Editor:** nesta versão, mostra as deixas com a miniatura da imagem escolhida, só para leitura. Trocar ou tirar uma ilustração fica para depois.

**Check (worktree `../Cortes-formato`):** `PY="../Cortes/.venv/Scripts/python"`, depois `PYTHONPATH=src $PY -m ruff check src tests && PYTHONPATH=src $PY -m mypy src && PYTHONPATH=src $PY -m pytest -q`. A dependência nova se instala com `$PY -m pip install ddgs` (o `.venv` é compartilhado com a pasta principal; registrar no relatório).

## Fatos verificados

- **`cortes.llm`:**
  - `chamar(prompt, schema, sistema, modelo, executar)` monta `claude -p` com `--tools ""`, `--json-schema` e `--output-format json`, valida o `structured_output` com jsonschema e levanta `ErroLLM`.
  - Para a conferência é preciso liberar o `Read` numa pasta. Acrescente a `montar_comando` parâmetros opcionais explícitos, `ferramentas: str = ""` e `pastas: list[Path]`, que viram `--tools Read --allowedTools Read --add-dir <pasta>`. **Confirme as flags reais com `claude --help` antes de escrever**; não invente flag.
- **`ddgs`** (testado num venv descartável): `DDGS().images(q, max_results=n, region="br-pt", safesearch="moderate")` devolve dicts com `image` (URL), `width`, `height`, `title` e `url` (página de origem). A largura pode vir vazia.
- **Pipeline atual (plano C):** `montar_projeto(pasta_ep, c, raiz, dep)` faz `preparar_trecho` (segmentos sem pausa, trecho, rosto, `recorte.json`) e depois `_html`. As palavras do corte são `palavras_editadas`, depois `palavras_do_corte`, depois `palavras_sem_pausa`, já no tempo do trecho sem pausas. `montagem.valores` devolve um superconjunto de placeholders. Os formatos e templates estão em `montagem.FORMATOS`/`_TEMPLATES`, já com f6, f5 e f8 do plano anterior; o f9 entra no fim.
- **Template base:** `render/formatos/conversa.tpl` (f7, sem flash nem zoom).

---

### Task 1: Deixas pelo Claude (puro + chamada injetável)

- [ ] **`src/cortes/render/ilustracao.py`:**
  - `Deixa(inicio: float, fim: float, coisa: str, busca: str)`, com os tempos no trecho sem pausas.
  - `SCHEMA_DEIXAS`: `{"deixas": [{"inicio_palavra": int, "fim_palavra": int, "coisa": str, "busca": str}]}`, com `maxItems` 12.
  - `prompt_deixas(palavras_numeradas) -> str` (puro). As palavras vão numeradas (`[12] Vans`).
  - **Regras do prompt:**
    - só coisas concretas que dá para fotografar: produto, marca com objeto, lugar, veículo, comida, animal, roupa ou objeto;
    - nada abstrato, como "dinheiro" no sentido genérico, "sucesso" ou "ideia";
    - `busca` em português, específica, com marca e modelo quando forem ditos;
    - no máximo uma deixa a cada 3 s, e nada no primeiro 1 s, que é o gancho com o rosto.
  - `deixas_do_corte(palavras, chamar) -> list[Deixa]` converte índice em tempo e aplica as regras **também no código**, com teste:
    - índices válidos e `inicio <= fim`;
    - duração entre 1,2 e 3,0 s (estica até 1,2 s e corta em 3,0 s);
    - descarta a deixa que começa antes de 1,0 s ou a menos de 3 s da anterior;
    - ordena por início.
  - `ChamarLLM` injetável (o mesmo tipo do detector).
- [ ] **Testes:** o prompt numera as palavras; a conversão de índice em tempo; as regras de espaçamento e duração; uma resposta com índice fora do intervalo dá `ErroLLM` ou `ErroRender` com a causa.
- [ ] Commit `feat: deixas do Ilustrado — o Claude marca as coisas concretas da fala`.

### Task 2: Busca, download e folha de conferência

- [ ] **Busca e download:**
  - `Candidata(url: str, origem: str, largura: int | None, altura: int | None)`.
  - `buscar(busca, n, ddgs) -> list[Candidata]`, com o `ddgs` injetável (protocolo com `.images(...)`). Descarta o que tem `width`/`height` menor que 400 quando informado.
  - `baixar(url, destino, rodar)`: `ffmpeg -y -i <url> -frames:v 1 -vf "scale=1080:1080:force_original_aspect_ratio=decrease" <destino.jpg>`. O ffmpeg lê HTTP e normaliza qualquer formato, sem precisar de Pillow; use `-user_agent` de navegador. Grava em `.parcial.jpg` e confere o arquivo. Falha numa candidata não para as outras: registre a causa e siga, com a lista de falhas no relatório da deixa.
- [ ] **Folha:** `folha_args(imagens, destino)`, função pura que monta o ffmpeg de mosaico. Cada linha é uma deixa e cada coluna uma candidata, em tiles de 320×320, com o número `D<k>-<j>` escrito com `drawtext` (fonte do Windows `C:/Windows/Fonts/arial.ttf`; conferir que existe). Uma linha por deixa; deixa sem candidata não entra.
- [ ] **Conferência:**
  - `SCHEMA_CONFERENCIA`: `{"escolhas": [{"deixa": int, "imagem": int | null, "motivo": str}]}`.
  - `conferir(folha, deixas, chamar_com_read)` exige uma escolha por deixa da folha, e a imagem tem que ser uma candidata existente daquela deixa. `null` quer dizer "nenhuma bate".
  - Se a deixa sumir da resposta, ela fica **sem imagem** e o motivo diz isso.
- [ ] **`llm.montar_comando`:** parâmetros opcionais de ferramenta e pasta (ver Fatos), com teste dos args.
- [ ] **Testes com falsos** (nada de rede no check): busca filtrando tamanho; download que falha numa candidata; args da folha; conferência que recusa índice inexistente; deixa ausente vira "sem imagem".
- [ ] Commit `feat: busca de imagens e conferência visual do Ilustrado`.

### Task 3: Etapa de ilustração, template f9 e pipeline

- [ ] **`ilustrar(pasta_ep, c, raiz, dep) -> list[Ilustracao]`**, em `ilustracao.py` ou num `ilustracao_etapa.py` se o arquivo passar de 300 linhas:
  - `Ilustracao(deixa, imagem: Path | None, fonte_url: str | None, motivo: str)`.
  - Cache em `cortes/<n>/ilustracao/ilustracao.json`, com o início e o fim do corte. Vale enquanto não mudarem; nesse caso só copia as imagens para `projeto/assets/ilus-<k>.jpg`.
  - Quando o trecho é refeito (cache do `recorte.json` inválido), a pasta `ilustracao/` é apagada, como `miniaturas/`.
- [ ] **`DepRender`:** ganha `chamar_llm`, `chamar_llm_com_read` e `ddgs`, todos injetáveis e com padrão real. O servidor e a fila usam o padrão real.
- [ ] **`render/formatos/ilustrado.tpl`:**
  - É uma cópia do `conversa.tpl` mais `{{IMAGENS}}`.
  - Cada cartão é `<div class="clip ilus" data-start data-duration data-track-index="15"><img src="assets/ilus-k.jpg"></div>`, com 860×860 de área útil, centralizado, `top: 220px`, `object-fit: contain`, fundo branco arredondado e sombra.
  - Animação GSAP: opacidade de 0 a 1 em 0,15 s no começo e de 1 a 0 em 0,15 s no fim. Sem scale e sem flash.
- [ ] **`montagem`:**
  - `FORMATOS` ganha `"f9"` e `_TEMPLATES["f9"] = "ilustrado"`.
  - `valores` aceita `ilustracoes` e gera `IMAGENS` (vazio quando não é f9 ou não há ilustração). Use `html.escape` nos atributos.
- [ ] **`pipeline.montar_projeto`:** se `c.formato == "f9"`, chama `ilustrar` antes do `_html`. Erro de LLM ou de rede vira `ErroRender` com a causa, e o corte fica em erro, visível. Nunca um f9 sem imagem nenhuma sem aviso: se **nenhuma** deixa ganhou imagem, `ErroRender("nenhuma coisa concreta ilustrável neste corte — use outro formato")`.
- [ ] **`contas/formatos.yaml`:** entra `f9` (nome "Ilustrado", com obs/descrição curta: "a coisa citada aparece num cartão enquanto a pessoa fala"; `no_app: "plano B"`). Confira o formato do arquivo e as validações em `painel/dados.py`.
- [ ] **Editor (`rotas_editor.estado_editor` + `editor.js`):** para f9, uma lista só de leitura com as ilustrações (início, coisa, miniatura servida por rota nova `GET .../ilustracao/<k>`, ou "sem imagem" com o motivo). Rota protegida como a de miniatura de rosto.
- [ ] **Testes:**
  - o pipeline f9 com falsos chama deixas, busca, download e conferência uma vez e reaproveita o cache na segunda versão;
  - "nenhuma imagem" dá erro;
  - o template real monta sem sobra;
  - o `IMAGENS` é escapado.
- [ ] Commit `feat: f9 Ilustrado — imagem da coisa citada num cartão`.

### Task 4: Conferência real

- [ ] **Render real de um corte em f9** no episódio `wxCto9WSZcI` ("Como se estabilizar com 3 mil de salário"), que fala de tênis, camisa e bota. O controlador passa o caminho.
  - Fazer pelo teste lento com `CORTES_EP_REF` e um candidato que cite produtos, ou por um script de conferência no scratchpad. **Nunca gravar em `../Cortes/episodios`.**
  - Copiar o MP4, a folha de conferência e o `ilustracao.json` para a pasta indicada.
- [ ] **Spec:** registrar o f9 e as decisões acima (§3, §4.1, §4.3, §6 ou uma seção nova "Ilustrado").
- [ ] Commit `test/docs: Ilustrado real e spec`.
