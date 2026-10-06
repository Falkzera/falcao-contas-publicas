"""Pergunte pelo terminal.

uv run contas "A despesa com pessoal de Recife está dentro do limite da LRF?"
uv run contas --modelo ollama:qwen3-contas --sql "Quanto BH gastou com saúde em 2025?"
"""

import argparse
import asyncio

from . import agente, banco


def _rodape(e: agente.Execucao) -> str:
    partes = [e.modelo, e.resposta.desfecho, f"{e.segundos:.1f} s"]
    if e.uso:
        partes.append(f"{e.uso.input_tokens + e.uso.output_tokens} tokens")
        custo = e.uso.cost
        partes.append("custo sem preço conhecido" if custo is None else f"US$ {custo:.4f}")
    if e.reprovacoes:
        partes.append(f"{e.reprovacoes} resposta(s) barrada(s) pela conferência")
    return "[" + " · ".join(partes) + "]"


async def _rodar(pergunta: str, modelo: str | None, mostrar_sql: bool) -> None:
    try:
        e = await agente.perguntar(pergunta, modelo)
    finally:
        await banco.fechar()
    print(e.resposta.texto)
    fontes = list(dict.fromkeys((p.fonte, p.sql) for p in e.passos))
    if fontes:
        print("\nFonte:")
        for fonte, sql in fontes:
            print(f"  • {fonte}")
            if mostrar_sql and sql:
                print(f"    {sql}")
    print("\n" + _rodape(e))


def main() -> None:
    p = argparse.ArgumentParser(
        prog="contas", description="Pergunte sobre as contas públicas das capitais."
    )
    p.add_argument("pergunta", nargs="+")
    p.add_argument("--modelo", help="provedor:modelo (padrão: LLM_MODELO do .env)")
    p.add_argument("--sql", action="store_true", help="mostra o SQL de cada consulta")
    a = p.parse_args()
    with agente.precos_atualizados():
        asyncio.run(_rodar(" ".join(a.pergunta), a.modelo, a.sql))


if __name__ == "__main__":
    main()
