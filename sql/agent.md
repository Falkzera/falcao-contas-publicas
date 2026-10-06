# sql · agent.md

## Propósito
O banco do agente, em três passos que a carga (`contas-dados carregar`) executa nesta ordem, sempre do zero.

## Arquivos
- `01-bruto.sql` · schema `bruto`: `capital` e `siconfi` (o dado como a API entrega, formato longo). O agente não enxerga.
- `02-semantica.sql` · schema `sem`: cinco views em português, uma linha por capital e ano, com COMMENT em cada view e nas colunas que precisam de explicação. É a única superfície do agente.
- `03-papel-leitura.sql` · papel `agente_ro`: só `USAGE` em `sem`, `default_transaction_read_only`, `statement_timeout` de 5 s e `search_path = sem`.

## Padrões
- O COMMENT é contexto do modelo. Escreva como se explicasse a um analista: o que é, a fonte (demonstrativo e anexo) e a armadilha, se houver.
- Conta do SICONFI se identifica por `cod_conta` e prefixo de `coluna` (`LIKE 'DOTAÇÃO ATUALIZADA%'`): a letra entre parênteses no fim do rótulo muda de um ano para outro.
- Regra de negócio mora na view (intra-orçamentárias fora, situação pelo valor em reais), não no prompt.

## Decisões recentes
- 2026-10-06: função de governo separada da subfunção pelo nome exato das 28 funções da Portaria MOG 42/1999. A soma das funções bate com o total do Anexo 2 em todas as capitais e anos.
- 2026-10-06: função sem execução no ano vem com a coluna em branco no demonstrativo; a view devolve zero.
- 2026-10-06: resultado orçamentário = receita realizada menos despesa empenhada (sem intra-orçamentárias).

## Pendências conhecidas
- Nenhuma.
