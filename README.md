# falcao-contas-publicas

Agente de IA que responde, em português, perguntas sobre as contas públicas das 26 capitais brasileiras, de 2023 a 2025, com os dados oficiais do SICONFI (Tesouro Nacional).

Duas garantias, nesta ordem: **todo número da resposta é conferido por código contra o que o banco devolveu**, e **toda resposta diz de qual demonstrativo veio**. O que a base não cobre vira recusa explícita, e nunca um número aproximado.

Funciona com **qualquer LLM** que saiba chamar ferramentas. Trocar de modelo é trocar duas linhas do `.env` (o modelo e a chave), e a mesma suíte de avaliação mede cada um nas mesmas perguntas.

```text
$ uv run contas "A despesa com pessoal de Recife em 2025 está dentro do limite da LRF?"

Sim. Em 2025, a despesa com pessoal do Executivo de Recife somou R$ 3.471.695.684,77, o
equivalente a 44,09% da RCL ajustada, o que fica abaixo do limite de alerta (48,6%). A folga
até o limite máximo (54%) é de R$ 779.864.543,68, ou 9,91 pontos percentuais.

Fonte:
  • SICONFI/Tesouro Nacional · RGF Anexo 1 (despesa com pessoal), 3º quadrimestre · Recife · 2025

[deepseek:deepseek-chat · respondida · 3.1 s · 8029 tokens · US$ 0.0002]
```

Saída real, sem edição. Todo número dela foi conferido contra o banco antes de aparecer.

## Como funciona

```
pergunta
   │
   ▼
agente (PydanticAI, qualquer modelo com chamada de ferramentas)
   │
   ├─ 1. MÉTRICA ··········· SQL escrito à mão. O modelo só escolhe qual chamar
   ├─ 2. SQL GUARDADO ······ último recurso. sqlglot + EXPLAIN + LIMIT + papel somente leitura
   └─ 3. RECUSA ············ quando nem uma nem outra responde
   │
   ▼
Postgres · schema sem (5 views em português; o COMMENT de cada uma é o contexto do modelo)
   │
   ▼
conferência numérica ······· R$, %, pontos percentuais e contagens precisam vir do banco
   │
   ▼
resposta + fonte (registrada pelo código quando a consulta roda, não pelo modelo)
```

| Camada | O que garante |
|---|---|
| Banco | o papel `agente_ro` só enxerga as views de `sem`, só lê e tem tempo limite de 5 s. Provado no CI: ler o dado bruto, criar tabela e `pg_sleep(6)` falham |
| SQL gerado | uma instrução `SELECT`, só views de `sem`, sem `INTO`, `FOR UPDATE` ou função perigosa, `LIMIT` imposto e `EXPLAIN` antes de rodar |
| Resposta | número que não veio das ferramentas devolve a resposta ao modelo. Na terceira falha, quem perguntou recebe uma recusa em vez de um número errado |
| Fonte | demonstrativo, anexo, capital e ano de cada consulta, registrados pelo código |
| Entidades | "BH", "Floripa", "capital do Ceará", "saude" e "Salvadro" viram o valor do banco dentro da ferramenta. Brasília e cidades que não são capital voltam com o motivo |

Os porquês de cada escolha, incluindo por que **não** há RAG, estão em [`docs/DECISOES.md`](docs/DECISOES.md). O contrato do projeto está em [`docs/ESPECIFICACAO.md`](docs/ESPECIFICACAO.md).

## Rodar

Precisa de Docker e [uv](https://docs.astral.sh/uv/).

```bash
docker compose up -d --wait          # Postgres local na porta 5437
uv sync                              # dependências
uv run contas-dados carregar         # recorte do SICONFI que vem no repositório -> banco
cp .env.example .env                 # escolha o modelo e ponha a chave
uv run contas "Quanto BH gastou com saúde em 2025?"
```

`--sql` mostra o SQL de cada consulta. `--modelo provedor:modelo` troca o modelo só naquela pergunta.

## Trocar de modelo

Duas linhas do `.env`, e só elas: o modelo e a chave dele. A chave é uma variável só, `LLM_API_KEY`, sirva o provedor que for.

```bash
LLM_MODELO=deepseek:deepseek-chat
LLM_API_KEY=sk-...
```

| Provedor | `LLM_MODELO` |
|---|---|
| Anthropic | `anthropic:claude-opus-5-5` |
| OpenAI | `openai:gpt-4.1-mini` |
| Google | `google:gemini-2.5-flash` |
| DeepSeek | `deepseek:deepseek-chat` |
| OpenRouter (centenas de modelos) | `openrouter:<modelo>` |
| Ollama, local e sem chave | `ollama:qwen3-contas`, com `LLM_BASE_URL=http://localhost:11434/v1` |
| Qualquer endpoint compatível com a API da OpenAI | `openai:<modelo>`, com `LLM_BASE_URL` |

O único requisito é o modelo saber chamar ferramentas. Para o modelo local: `ollama create qwen3-contas -f Modelfile`. O `Modelfile` aumenta o contexto, porque o padrão do Ollama é menor que as instruções do agente e o excesso é cortado em silêncio.

## Avaliação

A suíte em [`evals/perguntas.yaml`](evals/perguntas.yaml) tem 39 perguntas em seis grupos: despesa com pessoal, despesa por função, balanço e RCL, SQL guardado, resolução de entidade e recusa. A resposta certa de cada uma é um SQL rodado na hora sobre as mesmas views, e não um número escrito à mão. Cada caso diz o desfecho esperado, as ferramentas aceitas e o que a resposta precisa conter.

```bash
uv run python evals/rodar.py --modelo ollama:qwen3-contas
```

**Placar** (06/10/2026, código final, duas rodadas por modelo, 39 perguntas cada):

| Modelo | Onde roda | Acertos | Latência mediana | Custo por pergunta |
|---|---|---|---|---|
| DeepSeek V4.1 Flash (`deepseek:deepseek-chat`) | API | **39/39 e 38/39** | 2,5 s | US$ 0,0002 |
| Qwen3-14B (`ollama:qwen3-contas`) | notebook, local | **38/39 e 39/39** | 29 s | sem custo por token |

As duas falhas estão na tabela abaixo, nas rodadas 12 e 13: uma recusa de segurança e uma consulta derivada que respondeu outra pergunta.

**Como o placar chegou aqui.** Cada rodada achou algo que teste unitário não pega, e a correção foi no código, nunca no prompt para "passar":

| Rodadas | Modelo | Acertos | O que a rodada achou | O que mudou |
|---|---|---|---|---|
| 1 e 2 | Qwen3-14B | 32 e 22 | Toda falha era de formato: o modelo acertava a resposta e errava o JSON pedido, e a resposta certa virava recusa de segurança | Resposta em texto; o desfecho passou a ser decidido pelo código |
| 3 e 4 | Qwen3-14B | 37 e 36 | O ranking com quantidade 1 escondia a segunda capital; valor certo com pontuação quebrada ("R$ 2,274,859,448,85") escapava da conferência | Ranking com filtro devolve a lista inteira; formato brasileiro conferido |
| 5 e 6 | DeepSeek | 38 e 37 | Duas réguas da avaliação reprovavam respostas certas | Régua corrigida |
| 7 e 8 | DeepSeek | 39 e 38 | "Quatro capitais", por extenso, não era lido como número, nem pela régua nem pela conferência | Contagem por extenso conferida |
| 9 e 10 | DeepSeek | 39 e 39 | 24 das 39 respostas da rodada 10 usavam travessão, que este projeto não usa no texto | Instrução: responder sem travessão |
| 11 e 12 | DeepSeek | 39 e 38 | Nenhum travessão. A falha da 12 foi uma recusa de segurança: a resposta sobre a saúde das capitais do Sul foi barrada três vezes, e o agente preferiu não responder a arriscar o número | Nada. Recusar foi a garantia funcionando; a suíte conta como falha porque esperava resposta |
| 13 e 14 | Qwen3-14B | 38 e 39 | No código final, o modelo local chegou a 39. A falha da 13 foi uma consulta derivada que respondeu outra pergunta: Fortaleza (38,49%) no lugar de Boa Vista. Número do banco, consulta errada: o limite que só a avaliação pega | código final |

Ao longo das 14 rodadas, a conferência barrou 19 respostas com número que não veio do banco. Quase sempre o modelo refez com o valor certo; duas vezes, esgotadas as tentativas, o agente recusou em vez de responder. A mesma suíte, com o mesmo modelo e o mesmo código, foi de 82% a 56% de acerto nas duas primeiras rodadas: uma rodada só não é medida. Os porquês de cada mudança estão em [`docs/DECISOES.md`](docs/DECISOES.md), decisões 11 e 12.

Cada rodada fica inteira em [`evals/resultados/`](evals/resultados/), com pergunta, resposta, fonte, tempo e custo de cada caso. O custo vem do próprio PydanticAI (`genai-prices`); modelo local não tem preço por token.

## Dados

- **Fonte:** [SICONFI](https://siconfi.tesouro.gov.br), API de dados abertos do Tesouro Nacional.
- **Recorte:** as 26 capitais estaduais, exercícios 2023 a 2025, pelo fechamento do ano: RREO do 6º bimestre (Anexos 1, 2 e 3) e RGF do 3º quadrimestre do Poder Executivo (Anexo 1).
- **Brasília** não está: o DF presta contas como ente distrital, com outro demonstrativo.
- O recorte fica versionado em `dados/` (2,2 MB), para a avaliação não depender da API estar no ar. Para atualizar: `uv run contas-dados baixar` e depois `carregar`.

## Estrutura

```
src/contas/   agente, métricas, guarda de SQL, conferência numérica, entidades, carga, CLI
sql/          dado bruto, camada semântica (views + COMMENT) e papel somente leitura
evals/        perguntas, executor e rodadas publicadas
tests/        testes das garantias (sem rede, sem banco e sem LLM)
docs/         especificação e decisões
```

## Limites conhecidos

- Número sem unidade ("art. 20", "2º lugar") não passa pela conferência. Valores em reais, percentuais e contagens de capitais passam.
- A resposta pode trazer o número certo de uma consulta errada (a capital certa no ano errado, por exemplo). A conferência não pega isso; quem pega é a avaliação e a fonte exposta em cada resposta.
- Sem histórico de conversa: cada pergunta é independente.
- Modelo local pequeno é lento (dezenas de segundos por pergunta) e, numa rodada, estourou o tempo numa pergunta ambígua.

## In English

An LLM-agnostic agent that answers questions, in Portuguese, about the public accounts of Brazil's 26 state capitals (2023 to 2025), using official Treasury data (SICONFI). Every number in an answer is checked by code against what the database returned before it reaches the user, and every answer cites its source report. Hand-written SQL metrics come first; model-written SQL is a guarded last resort (sqlglot validation, EXPLAIN, read-only role); anything the data doesn't cover becomes an explicit refusal. Any tool-calling model works through PydanticAI, and a 39-question suite with SQL ground truth measures each one.

## Licença

MIT. Os dados são públicos, do Tesouro Nacional.
