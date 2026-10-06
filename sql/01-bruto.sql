-- Dado bruto do SICONFI, do jeito que a API entrega: uma linha por anexo,
-- conta e coluna. Só a carga escreve aqui. O agente não enxerga este schema.
-- Recriar do zero a cada carga apaga também as views de sem (CASCADE), que a
-- carga recria em seguida.

DROP SCHEMA IF EXISTS bruto CASCADE;
CREATE SCHEMA bruto;

CREATE TABLE bruto.capital (
    cod_ibge integer PRIMARY KEY,
    capital  text    NOT NULL,
    uf       char(2) NOT NULL,
    regiao   text    NOT NULL
);

CREATE TABLE bruto.siconfi (
    exercicio     smallint NOT NULL,
    demonstrativo text     NOT NULL,
    periodo       smallint NOT NULL,
    cod_ibge      integer  NOT NULL REFERENCES bruto.capital,
    populacao     integer,
    anexo         text     NOT NULL,
    rotulo        text     NOT NULL,
    coluna        text     NOT NULL,
    cod_conta     text     NOT NULL,
    conta         text     NOT NULL,
    valor         numeric
);

CREATE INDEX ON bruto.siconfi (anexo, cod_ibge, exercicio);
