"""Roda a suíte de avaliação contra o agente e devolve o placar.

    uv run python evals/rodar.py                                  # modelo do .env
    uv run python evals/rodar.py --modelo openai:gpt-4.1-mini
    uv run python evals/rodar.py --so recusa_brasilia,entidade_bh
    uv run python evals/rodar.py --grupo sql

Sem isto não há como saber se uma mudança no prompt, no modelo ou numa view
melhorou ou piorou. E uma rodada só não é medida: rode pelo menos duas.
O resultado completo (pergunta, resposta, fonte, tempo, custo) fica em
evals/resultados/.
"""

import argparse
import asyncio
import json
import statistics
import sys
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from contas import agente, ancoragem, banco, config  # noqa: E402


def _normal(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


async def _valor(sql: str) -> Decimal:
    linhas = await banco.buscar(sql)
    return Decimal(str(next(iter(linhas[0].values()))))


async def avaliar(caso: dict, modelo: str) -> dict:
    try:
        e = await agente.perguntar(caso["pergunta"], modelo)
    except Exception as ex:  # erro do provedor conta como falha, não derruba a suíte
        return {
            "id": caso["id"],
            "grupo": caso["grupo"],
            "ok": False,
            "falhas": [f"exceção: {type(ex).__name__}: {ex}"],
            "segundos": 0,
        }

    texto, desfecho = e.resposta.texto, e.resposta.desfecho
    aceitos = caso.get("desfecho", "respondida")
    aceitos = [aceitos] if isinstance(aceitos, str) else aceitos
    falhas = []
    if desfecho not in aceitos:
        falhas.append(f"desfecho '{desfecho}', esperado {aceitos}")

    usadas = [p.ferramenta for p in e.passos]
    if desfecho == "respondida":
        esperadas = set(caso.get("ferramentas", []))
        if esperadas and not esperadas & set(usadas):
            falhas.append(f"ferramenta: usou {usadas or 'nenhuma'}, esperava {sorted(esperadas)}")
        for sql in caso.get("verdades", []):
            if not ancoragem.cita(texto, v := await _valor(sql)):
                falhas.append(f"não citou o valor certo ({v})")
        if alguma := caso.get("alguma"):
            valores = [await _valor(sql) for sql in alguma]
            if not any(ancoragem.cita(texto, v) for v in valores):
                falhas.append(f"não citou nenhum de {valores}")
    for trecho in caso.get("contem", []):
        if _normal(trecho) not in _normal(texto):
            falhas.append(f"faltou '{trecho}'")
    for trecho in caso.get("nao_contem", []):
        if _normal(trecho) in _normal(texto):
            falhas.append(f"citou '{trecho}'")

    uso = e.uso
    return {
        "id": caso["id"],
        "grupo": caso["grupo"],
        "pergunta": caso["pergunta"],
        "resposta": texto,
        "desfecho": desfecho,
        "ok": not falhas,
        "falhas": falhas,
        "rota": "sql" if "consultar_sql" in usadas else ("metrica" if usadas else "nenhuma"),
        "passos": [vars(p) for p in e.passos],
        "segundos": round(e.segundos, 1),
        "tokens": (uso.input_tokens + uso.output_tokens) if uso else None,
        "tokens_em_cache": uso.cache_read_tokens if uso else None,
        "usd": float(uso.cost) if uso and uso.cost is not None else None,
        "conferencia_reprovou": e.reprovacoes,
        "erro": e.erro,
    }


def _placar(modelo: str, resultados: list[dict]) -> dict:
    n = len(resultados)
    acertos = sum(r["ok"] for r in resultados)
    tempos = [r["segundos"] for r in resultados if r["segundos"]]
    custos = [r["usd"] for r in resultados if r.get("usd") is not None]
    grupos = {}
    for r in resultados:
        g = grupos.setdefault(r["grupo"], [0, 0])
        g[0] += r["ok"]
        g[1] += 1
    return {
        "modelo": modelo,
        "acertos": acertos,
        "total": n,
        "acuracia": round(100 * acertos / n, 1) if n else 0,
        "por_grupo": {g: f"{a}/{t}" for g, (a, t) in grupos.items()},
        "latencia_mediana_s": round(statistics.median(tempos), 1) if tempos else None,
        "custo_total_usd": round(sum(custos), 4) if len(custos) == n else None,
        "custo_por_pergunta_usd": round(sum(custos) / n, 5) if len(custos) == n else None,
        "rotas": {
            k: sum(r.get("rota") == k for r in resultados) for k in ("metrica", "sql", "nenhuma")
        },
        "respostas_barradas_pela_conferencia": sum(
            r.get("conferencia_reprovou", 0) for r in resultados
        ),
        "recusas_de_seguranca": sum(1 for r in resultados if r.get("erro")),
    }


async def principal() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default=config.LLM_MODELO)
    ap.add_argument("--so", help="ids separados por vírgula")
    ap.add_argument("--grupo")
    args = ap.parse_args()

    casos = yaml.safe_load((RAIZ / "evals" / "perguntas.yaml").read_text(encoding="utf-8"))
    if args.so:
        casos = [c for c in casos if c["id"] in args.so.split(",")]
    if args.grupo:
        casos = [c for c in casos if c["grupo"] == args.grupo]

    print(f"avaliação · {args.modelo} · {len(casos)} casos\n")
    resultados = []
    try:
        for i, caso in enumerate(casos, 1):
            r = await avaliar(caso, args.modelo)
            resultados.append(r)
            marca = "ok   " if r["ok"] else "FALHA"
            print(f"{marca} {i:>2}/{len(casos)} {r['segundos']:>5.1f}s  {caso['id']}")
            for f in r["falhas"]:
                print(f"         → {f}")
    finally:
        await banco.fechar()

    placar = _placar(args.modelo, resultados)
    print("\n" + json.dumps(placar, ensure_ascii=False, indent=2))

    pasta = RAIZ / "evals" / "resultados"
    pasta.mkdir(exist_ok=True)
    carimbo = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    arquivo = pasta / f"{carimbo}-{args.modelo.replace(':', '_').replace('/', '_')}.json"
    arquivo.write_text(
        json.dumps({"placar": placar, "casos": resultados}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nresultado completo em {arquivo.relative_to(RAIZ)}")
    return 0 if placar["acertos"] == placar["total"] else 1


if __name__ == "__main__":
    with agente.precos_atualizados():
        raise SystemExit(asyncio.run(principal()))
