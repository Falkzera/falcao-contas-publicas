# tests · agent.md

## Propósito
Testes das garantias: conferência numérica, guarda de SQL, resolução de entidade e o agente com um modelo falso. Rodam sem rede, sem banco e sem LLM, em menos de um segundo.

## Arquivos
- `test_agente.py` · o agente inteiro com um modelo falso (`FunctionModel`): o número que veio do banco passa com a fonte, e o número inventado é barrado três vezes e vira recusa. É a garantia principal provada sem LLM.
- `test_ancoragem.py` · o que passa e o que é barrado na conferência (arredondamento, magnitude, contagem, constantes da lei).
- `test_guarda_sql.py` · SELECT legítimo passa; escrita, outro schema, função perigosa e múltiplas instruções são barrados; LIMIT imposto.
- `test_entidades.py` · apelidos, sigla e nome de estado, erro de digitação, Brasília e cidade fora da base.

## Padrões
- Defeito achado na avaliação vira caso aqui antes da correção, para provar que o teste falhava.
- O comportamento do agente com modelo de verdade é medido em `evals/`, não aqui.

## Decisões recentes
- 2026-10-06: o caso "4 capitais" com 3 e 1 na base nasceu de uma falha real deste arquivo.

## Pendências conhecidas
- Nenhuma.
