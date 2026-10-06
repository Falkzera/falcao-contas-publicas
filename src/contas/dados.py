"""Baixa o recorte do SICONFI e carrega no Postgres.

    uv run contas-dados baixar     API do Tesouro -> dados/ (versionado no repositório)
    uv run contas-dados carregar   dados/ -> bruto.* -> views sem.* -> papel somente leitura

A avaliação e o CI leem dados/, nunca a API ao vivo. Assim a resposta certa de
cada pergunta não muda entre uma rodada e outra.
"""

import argparse
import asyncio
import csv
import gzip
import io
import time
from decimal import Decimal

import asyncpg
import httpx

from . import config

API = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
ANOS = (2023, 2024, 2025)

# Fechamento do ano: RREO do 6º bimestre e RGF do 3º quadrimestre do Executivo.
_RREO = {"nr_periodo": 6, "co_tipo_demonstrativo": "RREO"}
_RGF = {"in_periodicidade": "Q", "nr_periodo": 3, "co_tipo_demonstrativo": "RGF", "co_poder": "E"}
DEMONSTRATIVOS = (
    ("rreo", {**_RREO, "no_anexo": "RREO-Anexo 01"}),
    ("rreo", {**_RREO, "no_anexo": "RREO-Anexo 02"}),
    ("rreo", {**_RREO, "no_anexo": "RREO-Anexo 03"}),
    ("rgf", {**_RGF, "no_anexo": "RGF-Anexo 01"}),
)

REGIOES = {"NO": "Norte", "NE": "Nordeste", "CO": "Centro-Oeste", "SE": "Sudeste", "SU": "Sul"}

COLUNAS = (
    "exercicio",
    "demonstrativo",
    "periodo",
    "cod_ibge",
    "populacao",
    "anexo",
    "rotulo",
    "coluna",
    "cod_conta",
    "conta",
    "valor",
)

DIR_DADOS = config.RAIZ / "dados"
ARQ_CAPITAIS = DIR_DADOS / "capitais.csv"
ARQ_SICONFI = DIR_DADOS / "siconfi.csv.gz"
DIR_SQL = config.RAIZ / "sql"


# ── Baixar ──────────────────────────────────────────────────────────────────


def _consultar(cliente: httpx.Client, endpoint: str, params: dict) -> list[dict]:
    """Todas as páginas de uma consulta, com nova tentativa em 429 e 5xx."""
    itens, offset = [], 0
    while True:
        for tentativa in range(4):
            r = cliente.get(f"{API}/{endpoint}", params={**params, "offset": offset})
            if r.status_code != 429 and r.status_code < 500:
                break
            time.sleep(2**tentativa)
        r.raise_for_status()
        pagina = r.json()
        itens += pagina["items"]
        if not pagina.get("hasMore"):
            return itens
        offset += pagina["limit"]


def baixar() -> None:
    DIR_DADOS.mkdir(exist_ok=True)
    faltas = []
    with httpx.Client(timeout=60) as cliente:
        # Brasília fica de fora: o DF presta contas como ente distrital, não como município.
        capitais = sorted(
            (
                e
                for e in _consultar(cliente, "entes", {})
                if str(e["capital"]).strip() == "1" and e["uf"] != "DF"
            ),
            key=lambda e: e["uf"],
        )
        with ARQ_CAPITAIS.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(("cod_ibge", "capital", "uf", "regiao"))
            for e in capitais:
                w.writerow((e["cod_ibge"], e["ente"], e["uf"], REGIOES[e["regiao"]]))

        # mtime=0 deixa o arquivo idêntico byte a byte quando o dado não mudou,
        # e baixar de novo não suja o diff do git.
        with gzip.GzipFile(ARQ_SICONFI, "wb", mtime=0) as bruto:
            f = io.TextIOWrapper(bruto, encoding="utf-8", newline="")
            w = csv.writer(f)
            w.writerow(COLUNAS)
            for e in capitais:
                for ano in ANOS:
                    for endpoint, params in DEMONSTRATIVOS:
                        itens = _consultar(
                            cliente,
                            endpoint,
                            {**params, "an_exercicio": ano, "id_ente": e["cod_ibge"]},
                        )
                        if not itens:
                            faltas.append(f"{e['ente']} {ano} {params['no_anexo']}")
                        # o item do RGF não traz o campo "demonstrativo"; vem da consulta
                        tipo = {"demonstrativo": params["co_tipo_demonstrativo"]}
                        w.writerows([{**i, **tipo}[c] for c in COLUNAS] for i in itens)
                print(f"  {e['ente']}")
            f.flush()

    print(f"✓ {len(capitais)} capitais em {ARQ_SICONFI.relative_to(config.RAIZ)}")
    for falta in faltas:
        print(f"  sem dado no SICONFI: {falta}")


# ── Carregar ────────────────────────────────────────────────────────────────


def _int(v: str) -> int | None:
    return int(v) if v else None


def _registro(linha: dict) -> tuple:
    return (
        int(linha["exercicio"]),
        linha["demonstrativo"],
        int(linha["periodo"]),
        int(linha["cod_ibge"]),
        _int(linha["populacao"]),
        linha["anexo"],
        linha["rotulo"],
        linha["coluna"],
        linha["cod_conta"],
        linha["conta"],
        Decimal(linha["valor"]) if linha["valor"] else None,
    )


async def _carregar() -> None:
    con = await asyncpg.connect(config.DATABASE_URL_ADMIN)
    try:
        await con.execute((DIR_SQL / "01-bruto.sql").read_text(encoding="utf-8"))
        with ARQ_CAPITAIS.open(encoding="utf-8") as f:
            capitais = [
                (int(c["cod_ibge"]), c["capital"], c["uf"], c["regiao"]) for c in csv.DictReader(f)
            ]
        with gzip.open(ARQ_SICONFI, "rt", encoding="utf-8", newline="") as f:
            registros = [_registro(linha) for linha in csv.DictReader(f)]
        await con.copy_records_to_table(
            "capital",
            schema_name="bruto",
            records=capitais,
            columns=("cod_ibge", "capital", "uf", "regiao"),
        )
        await con.copy_records_to_table(
            "siconfi", schema_name="bruto", records=registros, columns=COLUNAS
        )
        await con.execute((DIR_SQL / "02-semantica.sql").read_text(encoding="utf-8"))
        await con.execute((DIR_SQL / "03-papel-leitura.sql").read_text(encoding="utf-8"))

        print(f"✓ {len(registros):,} linhas brutas de {len(capitais)} capitais".replace(",", "."))
        for (view,) in await con.fetch(
            "SELECT table_name FROM information_schema.views WHERE table_schema = 'sem' ORDER BY 1"
        ):
            n = await con.fetchval(f"SELECT count(*) FROM sem.{view}")
            print(f"  sem.{view:<26} {n:>5} linhas")
    finally:
        await con.close()


def main() -> None:
    p = argparse.ArgumentParser(prog="contas-dados", description=__doc__.splitlines()[0])
    p.add_argument("acao", choices=("baixar", "carregar"))
    acao = p.parse_args().acao
    if acao == "baixar":
        baixar()
    else:
        asyncio.run(_carregar())


if __name__ == "__main__":
    main()
