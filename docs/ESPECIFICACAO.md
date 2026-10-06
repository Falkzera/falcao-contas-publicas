# Especificação · falcao-contas-publicas v1

**Data** 06/10/2026 · **Estado** v1 em construção · **Decisões e porquês** em [`DECISOES.md`](DECISOES.md)

## Objetivo

Um agente de IA que responde, em português, perguntas sobre as contas públicas das capitais brasileiras. A garantia é uma só. Todo número da resposta vem de uma consulta ao banco e é conferido por código antes de chegar a quem perguntou. O que a base não cobre vira recusa explícita.

O agente é **agnóstico de modelo**. Trocar de LLM é trocar uma variável de ambiente, e a mesma suíte de avaliação mede cada modelo nas mesmas perguntas.

## Perguntas que ele responde

- A despesa com pessoal de Recife em 2025 ficou dentro do limite da LRF?
- Quais capitais passaram do limite de alerta em 2024?
- Quanto São Paulo gastou com saúde em 2025, e quanto isso dá por habitante?
- Belo Horizonte arrecadou o que previa em 2025?
- Quais capitais do Nordeste gastam mais de 45% da receita com pessoal?

E recusa, dizendo o porquê, o que não está nos dados (Brasília, cidade que não é capital, ano fora da base, pagamento a fornecedor, salário de prefeito).

## Dados

| Item | Escolha |
|---|---|
| Fonte | SICONFI, do Tesouro Nacional, pela API pública de dados abertos |
| Entes | As 26 capitais estaduais. Brasília fica fora porque o DF presta contas como ente distrital, e não como município |
| Exercícios | 2023, 2024 e 2025, pelo fechamento do ano |
| RREO, 6º bimestre | Anexo 1 (balanço orçamentário), Anexo 2 (despesa por função) e Anexo 3 (receita corrente líquida) |
| RGF, 3º quadrimestre, Poder Executivo | Anexo 1 (despesa com pessoal e limites da LRF) |
| Reprodutibilidade | O recorte baixado fica versionado em `dados/`. A avaliação e o CI não dependem da API estar no ar |

## Arquitetura

```
pergunta
   │
   ▼
agente (PydanticAI, qualquer modelo com chamada de ferramentas)
   │
   ├─ 1. MÉTRICA ··········· SQL escrito à mão, parametrizado. O modelo só escolhe qual chamar
   ├─ 2. SQL GUARDADO ······ último recurso. sqlglot + EXPLAIN + LIMIT + papel somente leitura
   └─ 3. RECUSA ············ quando nem uma nem outra responde
   │
   ▼
Postgres · schema `sem` (views em português, com COMMENT que vira o contexto do modelo)
   │
   ▼
conferência dos números ···· todo R$, % e contagem da resposta precisa estar no que o banco devolveu
   │
   ▼
resposta + fonte (demonstrativo, anexo, capital, ano), registrada pelo código e não pelo modelo
```

## Ferramentas

| Ferramenta | Responde | Fonte |
|---|---|---|
| `listar_capitais` | quais capitais e anos existem na base | cadastro do SICONFI |
| `despesa_com_pessoal` | despesa com pessoal de uma capital, % da RCL ajustada, os três limites e a folga até cada um | RGF Anexo 1 |
| `ranking_despesa_com_pessoal` | capitais ordenadas pelo % da RCL, com filtro por situação diante dos limites | RGF Anexo 1 |
| `despesa_por_funcao` | quanto uma capital empenhou ou liquidou numa função (saúde, educação…), por habitante e fatia do total | RREO Anexo 2 |
| `ranking_por_funcao` | capitais ordenadas pelo gasto numa função, total ou por habitante | RREO Anexo 2 |
| `balanco_orcamentario` | receita prevista e realizada, despesa autorizada, empenhada, liquidada e paga, resultado | RREO Anexo 1 |
| `receita_corrente_liquida` | RCL de uma capital, total e por habitante | RREO Anexo 3 |
| `consultar_sql` | o que nenhuma métrica cobre, só sobre as views de `sem` | as views |

Capital e função são resolvidas **pelo código** dentro de cada ferramenta ("BH", "Floripa", "capital do Ceará", "saude" sem acento). O que não resolve volta como pedido de esclarecimento, nunca como filtro vazio que viraria "não há dados".

## Garantias

| Camada | O que garante |
|---|---|
| Banco | papel `agente_ro` só enxerga o schema `sem`, em transação somente leitura e com `statement_timeout` |
| Conexão | pool com `default_transaction_read_only` e transação `READ ONLY` explícita |
| SQL gerado | uma instrução `SELECT`, sem escrita, sem função perigosa, só views de `sem`, `LIMIT` imposto, `EXPLAIN` antes de rodar |
| Resposta | conferência numérica por código. Número que não veio do banco devolve a resposta ao modelo, e na terceira falha o usuário recebe recusa em vez de número errado |
| Fonte | registrada pelo código quando a consulta roda. O modelo não consegue inventar a própria fonte |
| Desfecho | respondida, recusada ou esclarecimento, decidido pelo código a partir das consultas que rodaram, e não declarado pelo modelo |
| Formato | valores já saem formatados em pt-BR das ferramentas. O modelo copia, não calcula nem formata |

## Agnóstico de modelo

Duas variáveis bastam. `LLM_MODELO` recebe `provedor:modelo` (por exemplo `anthropic:claude-opus-5-5`, `openai:gpt-4.1-mini`, `google:gemini-2.5-flash`, `deepseek:deepseek-chat`, `ollama:qwen3-contas`), e `LLM_API_KEY` recebe a chave desse provedor, qualquer que seja. Modelo local ou endpoint próprio compatível com a API da OpenAI entra com `LLM_BASE_URL`. Requisito único do modelo é suportar chamada de ferramentas. Um teste monta cinco provedores com a mesma chave e confere que ela chegou a cada um.

Modelo local pelo Ollama precisa de contexto maior que o padrão (`Modelfile` na raiz). Sem isso o prompt é cortado em silêncio e o modelo responde outra pergunta.

## Avaliação

A suíte em `evals/perguntas.yaml` é a verdade-terreno. A resposta certa de cada pergunta é um SQL rodado na hora sobre as mesmas views, e não um número escrito à mão. Cada caso diz o desfecho esperado (`respondida`, `recusada` ou `esclarecimento`), as ferramentas aceitas e os trechos que a resposta precisa conter.

| Grupo | Casos | O que mede |
|---|---|---|
| Despesa com pessoal e limites da LRF | 9 | métrica certa, número certo, situação diante do limite, contagem |
| Despesa por função | 7 | estágio da despesa declarado, valor por habitante, fatia do total, ano omitido |
| Balanço e RCL | 6 | receita prevista contra realizada, resultado, RCL |
| SQL guardado | 4 | pergunta que nenhuma métrica cobre, resolvida com SQL validado |
| Resolução de entidade | 4 | apelido, nome de estado, erro de digitação |
| Recusa, segurança e ambiguidade | 9 | fora da base, fora do escopo, tentativa de escrita, pedido para inventar número, pergunta ambígua |

O placar sai por modelo, com acerto, latência média e custo por pergunta (calculado pelo `genai-prices`). Uma rodada só não é medida. O README publica pelo menos duas por modelo.

## Critérios de aceite da v1

1. Do zero à primeira resposta em cinco comandos (`docker compose up`, `uv sync`, carga, `.env`, pergunta).
2. Testes unitários passam sem rede, sem banco e sem LLM.
3. A suíte roda com pelo menos um modelo local e um por API, e o README traz o placar dos dois.
4. Nenhuma resposta da suíte chega ao usuário com número fora dos dados.
5. CI roda lint e testes em todo PR. A avaliação roda sob demanda, com a chave num secret.

## Fora da v1, e por quê

| Fica de fora | Motivo |
|---|---|
| RAG | as perguntas são numéricas e a resposta está em tabela. Recuperar trecho de texto não ajuda e adiciona um ponto de falha |
| Interface web, Telegram, voz | não medem a habilidade que o projeto quer mostrar. A CLI basta |
| Fine-tuning | o gargalo é a garantia do número, não o estilo do modelo |
| Demo pública no ar | chave paga exposta a estranhos. O vídeo e o `uv run` cumprem o papel |

## Próximas versões

- **v1.1** servidor MCP expondo as mesmas ferramentas, para qualquer cliente MCP usar.
- **v1.2** rastro de cada execução (ferramentas, tempos, tokens) exportado em OpenTelemetry.
- **v2** RAG sobre o Manual de Demonstrativos Fiscais, só para perguntas conceituais ("o que é RCL ajustada?"), com citação.
