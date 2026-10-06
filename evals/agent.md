# evals · agent.md

## Propósito
Medir o agente, por modelo, nas mesmas perguntas. Sem isto não há como saber se mexer no prompt, numa ferramenta ou numa view melhorou ou piorou.

## Arquivos
- `perguntas.yaml` · 39 casos em seis grupos (pessoal, função, balanço, SQL, entidade, recusa). A resposta certa é SQL rodado na hora.
- `rodar.py` · roda a suíte, imprime o placar (acerto por grupo, latência mediana, custo por pergunta, rotas, respostas barradas pela conferência) e grava tudo em `resultados/`.
- `resultados/` · uma rodada por arquivo (`AAAAMMDD-HHMMSS-provedor_modelo.json`), com pergunta, resposta, fonte, tempo e custo de cada caso. As rodadas citadas no README ficam versionadas.

## Padrões
- Caso novo: prefira `verdades` (SQL) a `contem`. Use `contem` para nome de capital e para o universo declarado ("liquidad", "2025").
- Pergunta ambígua aceita lista de desfechos (`[esclarecimento, respondida]`) e `alguma` em vez de `verdades`.
- Uma rodada só não é medida. Publique pelo menos duas por modelo.

## Decisões recentes
- 2026-10-06: a comparação com a verdade usa `ancoragem.cita()`, a mesma régua de precisão da conferência do agente.

## Pendências conhecidas
- Suíte rodada no CI só sob demanda (`workflow_dispatch`), porque gasta API.
