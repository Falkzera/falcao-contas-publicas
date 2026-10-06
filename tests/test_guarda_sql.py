"""A guarda do SQL que o modelo escreve: o que entra e o que é barrado."""

import pytest

from contas.guarda_sql import SQLRecusado, validar

VIEWS = {"capital", "despesa_pessoal", "despesa_funcao", "balanco", "receita_corrente_liquida"}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT capital, percentual_rcl FROM sem.despesa_pessoal WHERE ano = 2025",
        "select regiao, avg(percentual_rcl) from despesa_pessoal group by 1",
        "WITH x AS (SELECT capital, rcl FROM sem.receita_corrente_liquida) SELECT * FROM x",
        "SELECT capital FROM sem.capital UNION SELECT capital FROM sem.balanco",
    ],
)
def test_select_sobre_as_views_passa(sql):
    assert validar(sql, VIEWS).views


@pytest.mark.parametrize(
    "sql, motivo",
    [
        ("DELETE FROM sem.capital", "Só SELECT"),
        ("UPDATE sem.balanco SET rcl = 0", "Só SELECT"),
        ("COPY sem.capital TO '/tmp/x'", "Só SELECT"),
        ("SELECT 1; DROP TABLE sem.capital", "única"),
        ("SELECT * INTO nova FROM sem.capital", "INTO"),
        ("SELECT * FROM sem.capital FOR UPDATE", "LOCK"),
        ("SELECT * FROM bruto.siconfi", "não existe"),
        ("SELECT * FROM pg_catalog.pg_roles", "não existe"),
        ("SELECT * FROM information_schema.tables", "não existe"),
        ("SELECT pg_sleep(10) FROM sem.capital", "pg_sleep"),
        ("SELECT current_setting('is_superuser') FROM sem.capital", "current_setting"),
        ("SELECT 1", "pelo menos uma view"),
    ],
)
def test_escrita_outro_schema_e_funcao_perigosa_sao_barrados(sql, motivo):
    with pytest.raises(SQLRecusado, match=motivo):
        validar(sql, VIEWS)


def test_limit_e_imposto_e_o_menor_e_mantido():
    assert validar("SELECT * FROM despesa_pessoal", VIEWS).sql.endswith("LIMIT 100")
    assert validar("SELECT * FROM despesa_pessoal LIMIT 5000", VIEWS).sql.endswith("LIMIT 100")
    assert validar("SELECT * FROM despesa_pessoal LIMIT 3", VIEWS).sql.endswith("LIMIT 3")
    union = validar("SELECT capital FROM capital UNION SELECT capital FROM balanco", VIEWS)
    assert union.sql.endswith("LIMIT 100")
