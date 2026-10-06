# Decisões · falcao-contas-publicas

Cada decisão com o porquê e o que a faria mudar. A especificação está em [`ESPECIFICACAO.md`](ESPECIFICACAO.md).

## 1. Métrica primeiro, SQL gerado por último

As perguntas frequentes têm resposta numa métrica com SQL escrito à mão, e o modelo só escolhe qual chamar e com que argumento. O risco de número errado nessa rota é perto de zero. O SQL gerado pelo modelo existe para o que nenhuma métrica cobre (filtro por região, média, variação entre anos), passa por validação de árvore com sqlglot, por `EXPLAIN` antes de rodar e por um papel do banco que só lê.

Só métrica pronta não cobre pergunta composta. Só SQL livre erra muito em esquema real. As duas rotas juntas, nessa ordem, cobrem a pergunta comum com segurança e a incomum com contenção.

## 2. Camada semântica em views, com o COMMENT como fonte do prompt

O SICONFI entrega os demonstrativos em formato longo (anexo, conta, coluna, valor), com nomes de conta que mudam de rótulo entre anos. O agente nunca vê isso. Ele vê cinco views em português, uma linha por capital e ano, com as regras de negócio já resolvidas: despesa sem as intra-orçamentárias, situação diante dos limites da LRF comparada em reais e valor por habitante com a população do próprio demonstrativo.

O `COMMENT` de cada view e coluna é o mesmo texto que vai para o modelo (`catalogo.py` lê do banco). Não existe segunda cópia do esquema em Python para sair de sincronia.

## 3. Conferência numérica por código, não por outro modelo

O modelo pode chamar a ferramenta certa, receber o dado certo e escrever outro número. Instrução não resolve, porque instrução é sugestão. A resposta só sai depois que `ancoragem.py` confere cada valor em reais, percentual e contagem contra o que as ferramentas devolveram. Se um número não bate, a resposta volta ao modelo; na terceira falha, quem perguntou recebe uma recusa em vez de um número errado.

A comparação respeita a precisão escrita: "R$ 1,77 bilhão" vale para 1.766.677.855,01 porque arredonda certo, e "R$ 1,76 bilhão" não vale. Somas e diferenças de dois resultados são aceitas para valores, para permitir comparações legítimas, mas não para contagens (com 3 e 1 na base, "4 capitais" passaria sem que nenhuma consulta tivesse devolvido 4; o teste que pegou isso está em `tests/test_ancoragem.py`).

Um modelo auditando outro modelo erra junto. Código comparando com o retorno do banco não erra assim.

Duas extensões vieram da avaliação. **Formato:** valor em reais ou percentual fora do padrão brasileiro é barrado, porque o modelo local escreveu "R$ 2,274,859,448,85" com o número certo, e quem lê percebe a pontuação quebrada antes de tudo. **Contagem por extenso:** "quatro capitais" é conferido como 4, porque é assim que os modelos escrevem, e sem isso "cinco capitais" passaria sem checagem.

## 4. A fonte é registrada pelo código

Toda resposta diz de qual demonstrativo, anexo, capital e ano veio o número. Esse registro é feito quando a consulta roda (`Deps.passos`), e não pedido ao modelo, que poderia inventar a própria fonte.

## 5. Quem resolve "BH" é o código, dentro da ferramenta

"BH", "Floripa", "capital do Ceará" e "saude" sem acento viram o valor exato do banco dentro de cada ferramenta (`entidades.py`). Se o modelo esquece de normalizar, não importa. O que não resolve volta como mensagem para o modelo perguntar ou recusar, e nunca como filtro vazio, porque zero linhas viraria "não há dados", uma mentira com cara de resposta.

## 6. Não pedir ao modelo o que o código faz melhor

Valores saem formatados em pt-BR das ferramentas. Situação diante do limite, folga em reais e em pontos percentuais e resultado (superávit ou déficit) já vêm calculados. Filtros usam palavras (`acima_do_alerta`, `por_habitante`) e não booleanos, que têm duas leituras possíveis. O modelo escolhe e copia.

## 7. Agnóstico de modelo pelo PydanticAI

`LLM_MODELO=provedor:modelo` e `LLM_API_KEY` bastam. A chave é uma variável só, sirva o provedor que for: o código entrega a mesma chave ao construtor do provedor que o nome indicar (`agente._modelo`), sem tabela de mapeamento. O PydanticAI 2.54 já fala com OpenAI, Anthropic, Google, DeepSeek, Groq, Mistral, Ollama, OpenRouter e qualquer endpoint compatível com a API da OpenAI, e já ajusta o que muda entre provedores (os modelos Claude mais novos não aceitam forçar chamada de ferramenta, por exemplo). Escrever um adaptador por provedor seria código a manter sem ganho.

O único requisito é o modelo suportar chamada de ferramentas. Modelo local pelo Ollama precisa de contexto maior que o padrão (`Modelfile`), senão o prompt é cortado em silêncio e o modelo responde outra pergunta.

O custo de cada pergunta vem do próprio PydanticAI (`usage.cost`, pelo `genai-prices`), sem tabela de preço mantida à mão.

## 8. Sem RAG na v1

As perguntas são numéricas e a resposta está em tabela. Recuperar trecho de texto não ajudaria e adicionaria um ponto de falha (trecho errado, contexto errado, resposta errada). O esquema inteiro cabe no prompt com cerca de mil tokens.

O gatilho para RAG é pergunta conceitual ("o que entra na RCL ajustada?"), respondida a partir do Manual de Demonstrativos Fiscais, com citação. Está no roteiro como v2.

## 9. Dado versionado e verdade-terreno em SQL

O recorte baixado da API fica em `dados/` (2,2 MB). A avaliação e o CI não dependem da API do Tesouro estar no ar, e a resposta certa não muda entre uma rodada e outra. A verdade de cada pergunta da suíte é um SQL rodado na hora sobre as mesmas views, e não um número escrito à mão, que envelheceria a cada carga.

## 10. Recortes de domínio

- **Brasília fica fora.** O DF presta contas como ente distrital, com outro demonstrativo. O agente explica isso em vez de procurar.
- **Intra-orçamentárias fora.** É dinheiro que circula dentro da própria prefeitura (contribuição ao regime próprio de previdência, por exemplo). Somar contaria duas vezes.
- **Liquidada é o padrão de "quanto gastou".** Empenhada é compromisso, paga depende do caixa. O agente diz qual usou.
- **Ano fechado.** RREO do 6º bimestre e RGF do 3º quadrimestre, para 2023, 2024 e 2025. A soma das 28 funções de governo bate com o total do Anexo 2 em todas as capitais e anos (conferido na carga de 06/10/2026).

## 11. Resposta em texto, desfecho decidido pelo código

A primeira versão pedia ao modelo uma saída estruturada, um JSON com o texto e o desfecho (respondida, recusada ou esclarecimento). A avaliação derrubou essa escolha. Nas duas primeiras rodadas com o Qwen3-14B local, o agente acertou 32 e depois 22 das 39 perguntas, e **todas** as falhas tinham a mesma causa: o formato. A conferência numérica não barrou nada. O agente caiu na recusa de segurança 11 e 17 vezes porque o modelo respondia certo, mas em texto ou com a chamada da ferramenta escrita como texto, e esgotava as tentativas.

O rastro de um desses casos ("Quanto Floripa gastou com educação em 2024?") mostra o modelo acertando R$ 849,88 milhões, 24,45% do total e R$ 1.480,11 por habitante, e a resposta sendo descartada por não vir no formato pedido.

A correção foi tirar do modelo o que o código sabe decidir. A resposta passa a ser texto, que todo modelo produz, e o desfecho é calculado a partir do que aconteceu na consulta (`agente._desfecho`): houve consulta com dados, é resposta; não houve e o texto termina em pergunta, é esclarecimento; senão, é recusa. É a mesma regra da fonte (decisão 4) aplicada ao desfecho.

A variação entre as duas rodadas (82% e 56%, mesmo modelo, mesmo código, mesmas perguntas) é o outro lado do achado. Uma rodada só não é medida, e é por isso que o README publica pelo menos duas.


## 12. A régua da avaliação também erra

Antes de mexer no agente por causa de uma falha, a resposta é lida. Em três casos a falha era da régua, e não do agente:

- a pergunta sobre capitais do Nordeste acima de 45% reprovava qualquer menção a Recife ou Salvador, mesmo quando a resposta dizia, certo, que elas estavam abaixo;
- os casos de recusa só aceitavam "recusada", e o modelo recusou oferecendo o que existe ("a base cobre 2023 a 2025, quer qual?"), o que termina em pergunta;
- a contagem "Quatro capitais" não era lida como 4.

Cada correção de régua está comentada em `evals/perguntas.yaml` ou coberta por teste em `tests/test_ancoragem.py`. Corrigir a régua para o agente passar seria trapaça; corrigir a régua que reprovava resposta certa é a avaliação medindo o que diz medir.
