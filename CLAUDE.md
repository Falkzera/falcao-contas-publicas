# CLAUDE.md · falcao-contas-publicas

Agente de IA, agnóstico de modelo, que responde em português perguntas sobre as contas públicas das 26 capitais estaduais (2023 a 2025), com dados do SICONFI (Tesouro Nacional). Todo número da resposta é conferido por código contra o que o banco devolveu, e toda resposta cita o demonstrativo de origem. Repositório **público**, peça de portfólio: o README é vitrine.

Leia antes de mexer: [`docs/ESPECIFICACAO.md`](docs/ESPECIFICACAO.md) (o contrato) e [`docs/DECISOES.md`](docs/DECISOES.md) (os porquês).

## Stack

| Peça | Versão |
|---|---|
| Python | 3.12 (uv) |
| PydanticAI (`pydantic-ai-slim[openai,anthropic,google]`) | 2.54 |
| sqlglot | 30.21 |
| asyncpg | 0.31 |
| PostgreSQL | 18 (Docker, porta 5437) |
| pytest, ruff | 9.1, 0.16 |

## Comandos

```bash
docker compose up -d --wait                       # Postgres local
uv sync
uv run contas-dados carregar                      # dados/ -> bruto -> views sem -> papel agente_ro
uv run contas-dados baixar                        # atualiza dados/ pela API do Tesouro (~5 min)
uv run contas "pergunta"                          # --modelo provedor:modelo, --sql
uv run pytest -q                                  # sem rede, sem banco, sem LLM
uv run ruff check . && uv run ruff format --check .
uv run python evals/rodar.py --modelo <provedor:modelo>   # gasta API: perguntar antes
```

Modelo e chave: `LLM_MODELO=provedor:modelo` e `LLM_API_KEY` (uma chave só, qualquer provedor). Modelo local: `ollama create qwen3-contas -f Modelfile`, `LLM_MODELO=ollama:qwen3-contas` e `LLM_BASE_URL=http://localhost:11434/v1`.

## Estrutura

```
src/contas/   o pacote: agente, métricas, guarda de SQL, conferência numérica, entidades, carga
sql/          schema bruto, camada semântica (views + COMMENT) e papel somente leitura
evals/        perguntas.yaml (verdade em SQL), rodar.py, resultados/ (rodadas publicadas)
tests/        testes unitários das garantias
dados/        recorte do SICONFI versionado (capitais.csv, siconfi.csv.gz)
docs/         especificação e decisões
```

## Regras de código

1. **Nenhuma ferramenta escreve.** O agente usa só o papel `agente_ro`. O admin (`DATABASE_URL_ADMIN`) é exclusivo da carga.
2. **O modelo só vê o schema `sem`.** Campo novo para o agente = view ou coluna em `sql/02-semantica.sql`, com `COMMENT`. O comentário vira contexto do modelo; não há cópia em Python.
3. **Valor de usuário nunca entra no SQL por concatenação.** Métrica usa `$1, $2...`; o que muda a forma da consulta sai de dicionário fechado (`_SITUACAO`, `_MEDIDA`, `_ORDEM`).
4. **Mudou `ancoragem.py`, `guarda_sql.py` ou `entidades.py`: rode `pytest` antes e depois.** Mudou prompt, ferramenta ou view: rode a avaliação, pelo menos duas vezes.
5. **Não peça ao modelo o que o código faz melhor** (formatar moeda, calcular folga, resolver nome de capital, registrar fonte).
6. Identificadores em português, como o domínio. Texto sem travessão.
7. **Este repositório é público.** Nada de cliente, empregador, órgão contratante, dado pessoal ou segredo. Exemplos com dado público do SICONFI.

## Documentação por pasta (agent.md)

Toda pasta com código deste projeto tem um `agent.md` que outra LLM lê antes de mexer ali. Ver regras completas em `~/.claude/skills/falcao-default/SKILL.md` (seção "agent.md").

Resumo: ao entrar numa pasta pra trabalhar, leia o `agent.md`; ao sair com mudanças significativas, atualize-o.

## Fases

- **v1 (06/10/2026):** sete métricas, SQL guardado, conferência numérica, 39 perguntas de avaliação, CI.
- **v1.1:** servidor MCP com as mesmas ferramentas.
- **v1.2:** rastro de execução em OpenTelemetry.
- **v2:** RAG sobre o Manual de Demonstrativos Fiscais, só para pergunta conceitual.

## Skills relevantes

- `falcao-default`: fluxo Git (branch, PR, squash), Conventional Commits **sem coautoria de IA**, agent.md.
- `falcao-ci`: repositório público roda no runner do GitHub. Rodar o passo zero quando o remoto existir.
