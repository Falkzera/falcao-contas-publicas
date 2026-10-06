"""Pool de conexões somente leitura, sobre o schema `sem`.

O papel `agente_ro` já é somente leitura no servidor. Aqui a leitura é imposta de
novo, na sessão e na transação, para que um erro de configuração do papel não
abra escrita.
"""

import asyncpg

from . import config

_pool: asyncpg.Pool | None = None


async def _abrir() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            config.DATABASE_URL,
            min_size=1,
            max_size=4,
            command_timeout=config.SQL_TIMEOUT_MS / 1000,
            server_settings={
                "default_transaction_read_only": "on",
                "statement_timeout": str(config.SQL_TIMEOUT_MS),
                "search_path": "sem",
                "application_name": "contas-agente",
            },
        )
    return _pool


async def buscar(sql: str, *args) -> list[dict]:
    pool = await _abrir()
    async with pool.acquire() as con, con.transaction(readonly=True):
        return [dict(r) for r in await con.fetch(sql, *args)]


async def explicar(sql: str) -> None:
    """EXPLAIN sem ANALYZE: valida tabela, coluna e tipo sem executar a consulta."""
    pool = await _abrir()
    async with pool.acquire() as con, con.transaction(readonly=True):
        await con.fetch(f"EXPLAIN {sql}")


async def fechar() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
