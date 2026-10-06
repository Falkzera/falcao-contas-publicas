# src/contas · agent.md

## Propósito
O pacote do agente. Da pergunta em português até a resposta conferida, com a fonte de cada número.

## Arquivos
- `agente.py` · o agente PydanticAI: instruções, as oito ferramentas, o validador de saída que confere os números e a fachada `perguntar()`.
- `metricas.py` · as consultas com SQL escrito à mão, a formatação pt-BR dos valores e a rota de SQL guardado (`consulta_sql`).
- `guarda_sql.py` · valida o SQL que o modelo escreve (sqlglot): um SELECT, só views de `sem`, sem função perigosa, LIMIT imposto.
- `ancoragem.py` · lê os números de um texto com a precisão escrita e diz quais não vieram do banco. Usado pelo agente e pela avaliação.
- `entidades.py` · "BH", "capital do Ceará", "saude" → valor exato do banco, ou o motivo de não resolver.
- `catalogo.py` · lê views, colunas e COMMENTs do schema `sem` e monta o cartão de esquema do prompt.
- `banco.py` · pool asyncpg somente leitura, `buscar()` e `explicar()`.
- `dados.py` · `contas-dados baixar` (API do Tesouro → `dados/`) e `carregar` (`dados/` → banco).
- `config.py` · variáveis de ambiente: `LLM_MODELO`, `LLM_API_KEY` (uma chave, qualquer provedor), `LLM_BASE_URL`, banco.
- `cli.py` · `contas "pergunta"`.

## Padrões
- Ferramenta nova: função em `metricas.py` que devolve `Resultado` (com `fonte`), e um `@agente.tool` em `agente.py` que passa por `_consultar()`. É `_consultar()` que registra a fonte e alimenta a conferência.
- Pergunta fora da base vira `SemDados` com o motivo em português; nunca lista vazia silenciosa.
- Parâmetro que muda a forma do SQL é `Literal` no `@agente.tool` e dicionário fechado em `metricas.py`.

## Decisões recentes
- 2026-10-06: uma chave só (`LLM_API_KEY`) para qualquer provedor; `_modelo()` a entrega ao construtor do provedor do nome. Sem ela, vale a variável própria de cada provedor.
- 2026-10-06: `precos_atualizados()` liga a atualização ao vivo do genai-prices na CLI e na avaliação. O apelido deepseek-chat passou a servir o DeepSeek V4.1 Flash, que a tabela embutida não conhecia.
- 2026-10-06: a saída do agente é texto (`output_type=str`) e o desfecho sai de `_desfecho()`, pelo que as consultas devolveram. A saída estruturada derrubava o modelo local por formato, com a resposta certa (DECISOES, decisão 11). Não volte a pedir JSON ao modelo só para rotular.
- 2026-10-06: contagem ("4 capitais") só bate com valor exato do banco; somas e diferenças de pares valem só para valores. O teste pegou "3 + 1 = 4" passando.
- 2026-10-06: custo por pergunta lido de `usage.cost` do PydanticAI (genai-prices), sem tabela de preço própria.
- 2026-10-06: cache de instruções e ferramentas ligado para Anthropic por `model_settings`; os demais provedores ignoram as chaves.
- 2026-10-06: a regra 10 das instruções pede resposta sem travessão. Eram 24 respostas com travessão em 39 na rodada 10; nas rodadas 11 a 14, nenhuma.

## Pendências conhecidas
- Número sem unidade ("art. 20", "2º lugar") não é conferido. Ampliar `_RE_CONTAGEM` se a avaliação mostrar número inventado sem unidade.
- Servidor MCP (v1.1) deve expor as funções de `metricas.py`, não o agente.
- O Qwen3 ainda usa meia-risca (–) como marcador de lista numa resposta (`pessoal_alerta_2024`, rodadas 13 e 14). Se incomodar, a regra 10 pode citar os dois sinais, com nova rodada.
