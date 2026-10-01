# Cortes

App local que transforma episódios de podcast em Shorts. Spec em
`docs/superpowers/specs/2026-09-30-app-cortes-design.md`; planos em `docs/superpowers/plans/`.

## Check (rodar depois de cada mudança)

    .venv/Scripts/python -m ruff check src tests
    .venv/Scripts/python -m mypy src
    .venv/Scripts/python -m pytest -q

## Regras do projeto

- Toda decisão é função pura com teste; I/O pesado fica em funções finas com executor injetável.
- Nada de default silencioso: erro de download, LLM ou schema para o episódio com mensagem clara.
- Chamadas ao LLM usam a assinatura (`claude -p`), nunca API paga — ver `src/cortes/llm.py`.
- Regras de corte e edição citam a fonte na pesquisa (`pesquisa/0*.md`).

## Painel de contas

    .venv/Scripts/cortes painel          # http://127.0.0.1:8790

Spec em `docs/superpowers/specs/2026-10-01-painel-contas-design.md`. Usa a skill
`youtube-analytics` (export do Studio) por subprocesso; contas em `contas/contas.yaml`.
