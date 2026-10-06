-- Papel que o agente usa. Só enxerga o schema sem, só lê, e com tempo limite.
-- A senha é de desenvolvimento local. Em qualquer outro ambiente, troque.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'agente_ro') THEN
        CREATE ROLE agente_ro LOGIN PASSWORD 'agente_ro';
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO agente_ro', current_database());
END $$;

REVOKE ALL ON SCHEMA bruto FROM agente_ro;
REVOKE ALL ON ALL TABLES IN SCHEMA bruto FROM agente_ro;

GRANT USAGE ON SCHEMA sem TO agente_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA sem TO agente_ro;

-- Cinto no próprio servidor. Vale mesmo que o código Python tenha um erro.
ALTER ROLE agente_ro SET default_transaction_read_only = on;
ALTER ROLE agente_ro SET statement_timeout = '5s';
ALTER ROLE agente_ro SET search_path = sem;
