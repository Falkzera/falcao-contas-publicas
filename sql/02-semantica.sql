-- ============================================================================
--  CAMADA SEMÂNTICA (schema sem)
--
--  A única superfície que o agente enxerga. Cada view tem uma linha por capital
--  e ano, com as contas do SICONFI já traduzidas em colunas com nome de gente.
--
--  O COMMENT de cada view e de cada coluna é o mesmo texto que vai para o
--  modelo (catalogo.py lê do banco). Documentar aqui é ensinar o agente, e não
--  existe uma segunda cópia do esquema para sair de sincronia.
--
--  Regras de negócio que moram aqui, e não no prompt:
--    - despesa e receita "exceto intra-orçamentárias", para não contar duas
--      vezes o dinheiro que circula dentro da própria prefeitura;
--    - situação diante dos limites da LRF comparada em reais, não no
--      percentual arredondado;
--    - valor por habitante com a população que o próprio demonstrativo traz.
-- ============================================================================

DROP SCHEMA IF EXISTS sem CASCADE;
CREATE SCHEMA sem;


-- ── capital ─────────────────────────────────────────────────────────────────

CREATE VIEW sem.capital AS
SELECT capital, uf, regiao, cod_ibge
FROM bruto.capital;

COMMENT ON VIEW sem.capital IS
'As 26 capitais estaduais da base, com UF e região. Brasília não está: o DF presta contas como ente distrital, não como município. Exercícios disponíveis: 2023, 2024 e 2025.';


-- ── despesa com pessoal e limites da LRF (RGF Anexo 1, Poder Executivo) ────

CREATE VIEW sem.despesa_pessoal AS
WITH p AS (
    SELECT
        s.cod_ibge,
        s.exercicio AS ano,
        max(s.valor) FILTER (WHERE s.cod_conta = 'DespesaComPessoalTotal' AND s.coluna = 'Valor') AS despesa_pessoal,
        max(s.valor) FILTER (WHERE s.cod_conta = 'ReceitaCorrenteLiquidaAjustada' AND s.coluna = 'Valor') AS rcl_ajustada,
        max(s.valor) FILTER (WHERE s.cod_conta = 'DespesaComPessoalTotal' AND s.coluna = '% sobre a RCL Ajustada') AS percentual_rcl,
        max(s.valor) FILTER (WHERE s.cod_conta = 'LimiteDeAlertaDespesaComPessoalTotal' AND s.coluna = 'Valor') AS limite_alerta,
        max(s.valor) FILTER (WHERE s.cod_conta = 'LimitePrudencialDespesaComPessoalTotal' AND s.coluna = 'Valor') AS limite_prudencial,
        max(s.valor) FILTER (WHERE s.cod_conta = 'LimiteMaximoDespesaComPessoalTotal' AND s.coluna = 'Valor') AS limite_maximo,
        max(s.valor) FILTER (WHERE s.cod_conta = 'LimiteDeAlertaDespesaComPessoalTotal' AND s.coluna = '% sobre a RCL Ajustada') AS percentual_limite_alerta,
        max(s.valor) FILTER (WHERE s.cod_conta = 'LimitePrudencialDespesaComPessoalTotal' AND s.coluna = '% sobre a RCL Ajustada') AS percentual_limite_prudencial,
        max(s.valor) FILTER (WHERE s.cod_conta = 'LimiteMaximoDespesaComPessoalTotal' AND s.coluna = '% sobre a RCL Ajustada') AS percentual_limite_maximo
    FROM bruto.siconfi s
    WHERE s.anexo = 'RGF-Anexo 01'
    GROUP BY s.cod_ibge, s.exercicio
)
SELECT
    c.capital, c.uf, c.regiao, p.ano,
    p.despesa_pessoal, p.rcl_ajustada, p.percentual_rcl,
    CASE
        WHEN p.despesa_pessoal > p.limite_maximo     THEN 'acima do limite máximo'
        WHEN p.despesa_pessoal > p.limite_prudencial THEN 'acima do limite prudencial'
        WHEN p.despesa_pessoal > p.limite_alerta     THEN 'acima do limite de alerta'
        ELSE 'abaixo do limite de alerta'
    END AS situacao,
    p.limite_alerta, p.limite_prudencial, p.limite_maximo,
    p.percentual_limite_alerta, p.percentual_limite_prudencial, p.percentual_limite_maximo,
    p.limite_alerta - p.despesa_pessoal         AS folga_ate_limite_alerta,
    p.limite_prudencial - p.despesa_pessoal     AS folga_ate_limite_prudencial,
    p.limite_maximo - p.despesa_pessoal         AS folga_ate_limite_maximo,
    p.percentual_limite_alerta - p.percentual_rcl     AS pontos_ate_limite_alerta,
    p.percentual_limite_prudencial - p.percentual_rcl AS pontos_ate_limite_prudencial,
    p.percentual_limite_maximo - p.percentual_rcl     AS pontos_ate_limite_maximo,
    c.cod_ibge
FROM p
JOIN bruto.capital c USING (cod_ibge);

COMMENT ON VIEW sem.despesa_pessoal IS
'Despesa total com pessoal do Poder Executivo da capital no ano, contra os limites da LRF (art. 19, 20, 22 e 59). Fonte: RGF Anexo 1, 3º quadrimestre (12 meses). Limites do Executivo municipal: máximo 54%, prudencial 51,3% e alerta 48,6% da RCL ajustada.';
COMMENT ON COLUMN sem.despesa_pessoal.despesa_pessoal IS 'Despesa total com pessoal (DTP) em 12 meses, em reais';
COMMENT ON COLUMN sem.despesa_pessoal.rcl_ajustada IS 'Receita corrente líquida ajustada para o cálculo dos limites da despesa com pessoal, em reais. Não é a mesma RCL de sem.receita_corrente_liquida';
COMMENT ON COLUMN sem.despesa_pessoal.percentual_rcl IS 'Despesa com pessoal como % da RCL ajustada, como publicado no demonstrativo';
COMMENT ON COLUMN sem.despesa_pessoal.situacao IS 'Faixa diante dos limites, comparada em reais: abaixo do limite de alerta, acima do limite de alerta, acima do limite prudencial ou acima do limite máximo';
COMMENT ON COLUMN sem.despesa_pessoal.folga_ate_limite_maximo IS 'Quanto falta, em reais, para atingir o limite máximo. Negativo quer dizer acima do limite';
COMMENT ON COLUMN sem.despesa_pessoal.pontos_ate_limite_maximo IS 'Quanto falta, em pontos percentuais da RCL ajustada, para atingir o limite máximo. Negativo quer dizer acima do limite';


-- ── despesa por função de governo (RREO Anexo 2) ───────────────────────────

CREATE VIEW sem.despesa_funcao AS
WITH f AS (
    SELECT
        s.cod_ibge,
        s.exercicio AS ano,
        s.conta AS funcao,
        max(s.populacao) AS populacao,
        max(s.valor) FILTER (WHERE s.coluna LIKE 'DOTAÇÃO ATUALIZADA%') AS dotacao_atualizada,
        -- função com orçamento e sem execução vem com a coluna em branco: é zero
        coalesce(max(s.valor) FILTER (WHERE s.coluna LIKE 'DESPESAS EMPENHADAS ATÉ O BIMESTRE%'), 0) AS empenhada,
        coalesce(max(s.valor) FILTER (WHERE s.coluna LIKE 'DESPESAS LIQUIDADAS ATÉ O BIMESTRE%'), 0) AS liquidada
    FROM bruto.siconfi s
    WHERE s.anexo = 'RREO-Anexo 02'
      AND s.rotulo = 'Total das Despesas Exceto Intra-Orçamentárias'
    GROUP BY s.cod_ibge, s.exercicio, s.conta
),
total AS (
    SELECT cod_ibge, ano, empenhada AS total_empenhada, liquidada AS total_liquidada
    FROM f
    WHERE funcao = 'DESPESAS (EXCETO INTRA-ORÇAMENTÁRIAS) (I)'
)
SELECT
    c.capital, c.uf, c.regiao, f.ano, f.funcao,
    f.dotacao_atualizada, f.empenhada, f.liquidada,
    round(f.empenhada / nullif(f.populacao, 0), 2) AS empenhada_por_habitante,
    round(f.liquidada / nullif(f.populacao, 0), 2) AS liquidada_por_habitante,
    round(100 * f.empenhada / nullif(t.total_empenhada, 0), 2) AS percentual_do_total_empenhado,
    round(100 * f.liquidada / nullif(t.total_liquidada, 0), 2) AS percentual_do_total_liquidado,
    f.populacao,
    c.cod_ibge
FROM f
JOIN total t USING (cod_ibge, ano)
JOIN bruto.capital c USING (cod_ibge)
-- As 28 funções de governo da Portaria MOG 42/1999. O anexo mistura função e
-- subfunção na mesma coluna, e o nome exato separa as duas. Conferido na carga
-- de 06/10/2026: a soma das funções bate com o total do anexo em todas as
-- capitais e anos.
WHERE f.funcao IN (
    'Legislativa', 'Judiciária', 'Essencial à Justiça', 'Administração', 'Defesa Nacional',
    'Segurança Pública', 'Relações Exteriores', 'Assistência Social', 'Previdência Social',
    'Saúde', 'Trabalho', 'Educação', 'Cultura', 'Direitos da Cidadania', 'Urbanismo',
    'Habitação', 'Saneamento', 'Gestão Ambiental', 'Ciência e Tecnologia', 'Agricultura',
    'Organização Agrária', 'Indústria', 'Comércio e Serviços', 'Comunicações', 'Energia',
    'Transporte', 'Desporto e Lazer', 'Encargos Especiais'
);

COMMENT ON VIEW sem.despesa_funcao IS
'Despesa da capital no ano por função de governo (Saúde, Educação, Urbanismo...), sem as intra-orçamentárias. Fonte: RREO Anexo 2, 6º bimestre (ano fechado). Empenhada é o valor comprometido; liquidada é o que foi entregue e reconhecido, e é a medida padrão de quanto se gastou. Este anexo não traz a despesa paga por função. Função que a capital não executou no ano não aparece, ou aparece com zero.';
COMMENT ON COLUMN sem.despesa_funcao.funcao IS 'Nome da função de governo, com acento e maiúscula inicial, como Saúde, Educação, Segurança Pública, Urbanismo, Assistência Social';
COMMENT ON COLUMN sem.despesa_funcao.liquidada IS 'Despesa liquidada no ano, em reais. A medida padrão de quanto se gastou';
COMMENT ON COLUMN sem.despesa_funcao.empenhada IS 'Despesa empenhada no ano, em reais';
COMMENT ON COLUMN sem.despesa_funcao.percentual_do_total_liquidado IS 'Fatia da função na despesa liquidada total da capital no ano, em %';
COMMENT ON COLUMN sem.despesa_funcao.populacao IS 'População informada no próprio demonstrativo do ano';


-- ── balanço orçamentário (RREO Anexo 1) ────────────────────────────────────

CREATE VIEW sem.balanco AS
WITH b AS (
    SELECT
        s.cod_ibge,
        s.exercicio AS ano,
        max(s.valor) FILTER (WHERE s.cod_conta = 'ReceitasExcetoIntraOrcamentarias' AND s.coluna = 'PREVISÃO INICIAL') AS receita_prevista_inicial,
        max(s.valor) FILTER (WHERE s.cod_conta = 'ReceitasExcetoIntraOrcamentarias' AND s.coluna LIKE 'PREVISÃO ATUALIZADA%') AS receita_prevista_atualizada,
        max(s.valor) FILTER (WHERE s.cod_conta = 'ReceitasExcetoIntraOrcamentarias' AND s.coluna LIKE 'Até o Bimestre%') AS receita_realizada,
        max(s.valor) FILTER (WHERE s.cod_conta = 'DespesasExcetoIntraOrcamentarias' AND s.coluna LIKE 'DOTAÇÃO INICIAL%') AS dotacao_inicial,
        max(s.valor) FILTER (WHERE s.cod_conta = 'DespesasExcetoIntraOrcamentarias' AND s.coluna LIKE 'DOTAÇÃO ATUALIZADA%') AS dotacao_atualizada,
        max(s.valor) FILTER (WHERE s.cod_conta = 'DespesasExcetoIntraOrcamentarias' AND s.coluna LIKE 'DESPESAS EMPENHADAS ATÉ O BIMESTRE%') AS despesa_empenhada,
        max(s.valor) FILTER (WHERE s.cod_conta = 'DespesasExcetoIntraOrcamentarias' AND s.coluna LIKE 'DESPESAS LIQUIDADAS ATÉ O BIMESTRE%') AS despesa_liquidada,
        max(s.valor) FILTER (WHERE s.cod_conta = 'DespesasExcetoIntraOrcamentarias' AND s.coluna LIKE 'DESPESAS PAGAS ATÉ O BIMESTRE%') AS despesa_paga
    FROM bruto.siconfi s
    WHERE s.anexo = 'RREO-Anexo 01'
    GROUP BY s.cod_ibge, s.exercicio
)
SELECT
    c.capital, c.uf, c.regiao, b.ano,
    b.receita_prevista_inicial, b.receita_prevista_atualizada, b.receita_realizada,
    round(100 * b.receita_realizada / nullif(b.receita_prevista_atualizada, 0), 2) AS percentual_receita_realizada,
    b.dotacao_inicial, b.dotacao_atualizada,
    b.despesa_empenhada, b.despesa_liquidada, b.despesa_paga,
    b.receita_realizada - b.despesa_empenhada AS resultado_orcamentario,
    CASE WHEN b.receita_realizada >= b.despesa_empenhada THEN 'superávit' ELSE 'déficit' END AS resultado,
    c.cod_ibge
FROM b
JOIN bruto.capital c USING (cod_ibge);

COMMENT ON VIEW sem.balanco IS
'Balanço orçamentário da capital no ano fechado, sem as intra-orçamentárias: receita prevista contra realizada e despesa autorizada contra empenhada, liquidada e paga. Fonte: RREO Anexo 1, 6º bimestre.';
COMMENT ON COLUMN sem.balanco.receita_prevista_atualizada IS 'Receita prevista no orçamento, com as atualizações do ano, em reais';
COMMENT ON COLUMN sem.balanco.receita_realizada IS 'Receita efetivamente arrecadada no ano, em reais';
COMMENT ON COLUMN sem.balanco.percentual_receita_realizada IS 'Receita realizada como % da prevista atualizada. Acima de 100 quer dizer que arrecadou mais que o previsto';
COMMENT ON COLUMN sem.balanco.dotacao_atualizada IS 'Despesa autorizada no orçamento, com os créditos adicionais do ano, em reais';
COMMENT ON COLUMN sem.balanco.resultado_orcamentario IS 'Receita realizada menos despesa empenhada, em reais. Positivo é superávit, negativo é déficit';


-- ── receita corrente líquida (RREO Anexo 3) ────────────────────────────────

CREATE VIEW sem.receita_corrente_liquida AS
SELECT
    c.capital, c.uf, c.regiao, s.exercicio AS ano,
    max(s.valor) AS rcl,
    round(max(s.valor) / nullif(max(s.populacao), 0), 2) AS rcl_por_habitante,
    max(s.populacao) AS populacao,
    c.cod_ibge
FROM bruto.siconfi s
JOIN bruto.capital c USING (cod_ibge)
WHERE s.anexo = 'RREO-Anexo 03'
  AND s.cod_conta = 'RREO3ReceitaCorrenteLiquida'
  AND s.coluna LIKE 'TOTAL (ÚLTIMOS 12 MESES)%'
GROUP BY c.capital, c.uf, c.regiao, s.exercicio, c.cod_ibge;

COMMENT ON VIEW sem.receita_corrente_liquida IS
'Receita corrente líquida (RCL) da capital, total dos 12 meses do ano. É a base de cálculo dos limites da LRF. Fonte: RREO Anexo 3, 6º bimestre.';
COMMENT ON COLUMN sem.receita_corrente_liquida.rcl IS 'Receita corrente líquida em 12 meses, em reais';
