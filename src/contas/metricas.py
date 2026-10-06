"""Métricas com SQL escrito à mão. O modelo só escolhe qual chamar e com que argumento.

O SQL daqui foi escrito e conferido por gente, e nenhum valor do usuário entra
por concatenação: capital, função e ano vão por parâmetro ($1, $2...), e o que
muda a forma da consulta (ordem, filtro, medida) sai de dicionário fechado.

Os valores saem formatados em pt-BR para o modelo copiar. Pedir ao modelo que
formate moeda é pedir para errar a vírgula.
"""

from dataclasses import dataclass
from decimal import Decimal

from . import banco, catalogo, entidades
from .guarda_sql import validar

ANOS = (2023, 2024, 2025)
FONTE = "SICONFI/Tesouro Nacional"
RGF_1 = f"{FONTE} · RGF Anexo 1 (despesa com pessoal), 3º quadrimestre"
RREO_1 = f"{FONTE} · RREO Anexo 1 (balanço orçamentário), 6º bimestre"
RREO_2 = f"{FONTE} · RREO Anexo 2 (despesa por função), 6º bimestre"
RREO_3 = f"{FONTE} · RREO Anexo 3 (receita corrente líquida), 6º bimestre"


class SemDados(Exception):
    """Pergunta fora do que a base cobre. A mensagem diz o porquê, em português."""


@dataclass
class Resultado:
    linhas: list[dict]
    fonte: str
    sql: str
    nota: str | None = None

    def para_o_modelo(self) -> dict:
        r = {
            "fonte": self.fonte,
            "linhas_retornadas": len(self.linhas),
            "linhas": [{k: _formatar(k, v) for k, v in linha.items()} for linha in self.linhas],
        }
        if self.nota:
            r["nota"] = self.nota
        return r


# ── Formatação pt-BR ────────────────────────────────────────────────────────

_DINHEIRO = (
    "despesa",
    "receita",
    "rcl",
    "limite",
    "folga",
    "dotacao",
    "empenhad",
    "liquidad",
    "paga",
    "resultado",
    "reais",
    "valor",
    "gasto",
    "habitante",
)
_INTEIROS = ("populacao", "total_que_atende", "quantidade", "qtd", "numero_de")


def _br(v, casas: int) -> str:
    return f"{Decimal(str(v)):,.{casas}f}".translate(str.maketrans(",.", ".,"))


def _formatar(coluna: str, v):
    if isinstance(v, bool) or not isinstance(v, (int, float, Decimal)):
        return v
    c = coluna.lower()
    if c in ("ano", "cod_ibge"):
        return v
    if c.startswith("pontos"):
        return f"{_br(v, 2)} p.p."
    if "percentual" in c:
        return f"{_br(v, 2)}%"
    if c.startswith(_INTEIROS):
        return _br(v, 0)
    if any(k in c for k in _DINHEIRO):
        return f"R$ {_br(v, 2)}"
    return _br(v, 0) if Decimal(str(v)) == int(v) else _br(v, 2)


# ── Validação de argumento ──────────────────────────────────────────────────


def _ano(ano: int | None) -> int | None:
    if ano is not None and ano not in ANOS:
        raise SemDados(
            f"{ano} está fora da base, que cobre os anos fechados de {ANOS[0]} a {ANOS[-1]}."
        )
    return ano


def _capital(termo: str) -> str:
    r = entidades.capital(termo)
    if r.valor is None:
        raise SemDados(r.motivo)
    return r.valor


def _funcao(termo: str) -> str:
    r = entidades.funcao(termo)
    if r.valor is None:
        raise SemDados(r.motivo)
    return r.valor


def _escolha(valor: str, opcoes: dict, nome: str):
    if valor not in opcoes:
        raise SemDados(f"{nome} inválido: '{valor}'. Use um de: {', '.join(opcoes)}.")
    return opcoes[valor]


def _periodo(ano: int | None) -> str:
    return str(ano) if ano else "2023 a 2025"


# ── Métricas ────────────────────────────────────────────────────────────────


async def listar_capitais() -> Resultado:
    sql = "SELECT capital, uf, regiao FROM sem.capital ORDER BY uf"
    return Resultado(
        await banco.buscar(sql),
        f"{FONTE} · cadastro de entes",
        sql,
        nota="Anos na base: 2023, 2024 e 2025. Brasília não está: o DF presta contas "
        "como ente distrital.",
    )


async def despesa_com_pessoal(capital: str, ano: int | None = None) -> Resultado:
    capital, ano = _capital(capital), _ano(ano)
    sql = """
        SELECT capital, uf, ano, despesa_pessoal, rcl_ajustada, percentual_rcl, situacao,
               limite_alerta, limite_prudencial, limite_maximo,
               percentual_limite_alerta, percentual_limite_prudencial, percentual_limite_maximo,
               folga_ate_limite_alerta, folga_ate_limite_prudencial, folga_ate_limite_maximo,
               pontos_ate_limite_alerta, pontos_ate_limite_prudencial, pontos_ate_limite_maximo
        FROM sem.despesa_pessoal
        WHERE capital = $1 AND ($2::int IS NULL OR ano = $2)
        ORDER BY ano"""
    return Resultado(
        await banco.buscar(sql, capital, ano),
        f"{RGF_1} · {capital} · {_periodo(ano)}",
        sql,
        nota="Folga negativa quer dizer acima do limite.",
    )


_SITUACAO = {
    "todas": "TRUE",
    "acima_do_alerta": "despesa_pessoal > limite_alerta",
    "acima_do_prudencial": "despesa_pessoal > limite_prudencial",
    "acima_do_maximo": "despesa_pessoal > limite_maximo",
    "abaixo_do_alerta": "despesa_pessoal <= limite_alerta",
}
_ORDEM = {"maior": "DESC", "menor": "ASC"}


async def ranking_despesa_com_pessoal(
    ano: int = 2025, situacao: str = "todas", ordem: str = "maior", quantidade: int = 5
) -> Resultado:
    ano = _ano(ano)
    filtro = _escolha(situacao, _SITUACAO, "situacao")
    direcao = _escolha(ordem, _ORDEM, "ordem")
    sql = f"""
        SELECT capital, uf, percentual_rcl, situacao, despesa_pessoal,
               count(*) OVER () AS total_que_atende
        FROM sem.despesa_pessoal
        WHERE ano = $1 AND {filtro}
        ORDER BY percentual_rcl {direcao}
        LIMIT $2"""
    # Com filtro de situação, a resposta é a lista inteira. A avaliação pegou o modelo
    # pedindo quantidade=1 para "alguma capital estourou o limite?" e omitindo a segunda.
    teto = 26 if situacao != "todas" else max(1, min(quantidade, 26))
    linhas = await banco.buscar(sql, ano, teto)
    nota = None if linhas else f"Nenhuma capital atende ao filtro '{situacao}' em {ano}."
    return Resultado(linhas, f"{RGF_1} · 26 capitais · {ano}", sql, nota)


async def despesa_por_funcao(capital: str, funcao: str, ano: int | None = None) -> Resultado:
    capital, funcao, ano = _capital(capital), _funcao(funcao), _ano(ano)
    sql = """
        SELECT capital, uf, ano, funcao, liquidada, empenhada, dotacao_atualizada,
               liquidada_por_habitante, percentual_do_total_liquidado, populacao
        FROM sem.despesa_funcao
        WHERE capital = $1 AND funcao = $2 AND ($3::int IS NULL OR ano = $3)
        ORDER BY ano"""
    linhas = await banco.buscar(sql, capital, funcao, ano)
    nota = (
        "Liquidada é a medida padrão de quanto se gastou. Diga na resposta que é a liquidada."
        if linhas
        else f"{capital} não registrou despesa na função {funcao} em {_periodo(ano)}: "
        "o demonstrativo não traz a função quando não há despesa."
    )
    return Resultado(linhas, f"{RREO_2} · {capital} · {funcao} · {_periodo(ano)}", sql, nota)


_MEDIDA = {
    "total": "liquidada",
    "por_habitante": "liquidada_por_habitante",
    "fatia_do_orcamento": "percentual_do_total_liquidado",
}


async def ranking_por_funcao(
    funcao: str,
    ano: int = 2025,
    medida: str = "total",
    ordem: str = "maior",
    quantidade: int = 5,
) -> Resultado:
    funcao, ano = _funcao(funcao), _ano(ano)
    coluna = _escolha(medida, _MEDIDA, "medida")
    direcao = _escolha(ordem, _ORDEM, "ordem")
    sql = f"""
        SELECT capital, uf, liquidada, liquidada_por_habitante, percentual_do_total_liquidado,
               count(*) OVER () AS total_que_atende
        FROM sem.despesa_funcao
        WHERE funcao = $1 AND ano = $2
        ORDER BY {coluna} {direcao}
        LIMIT $3"""
    linhas = await banco.buscar(sql, funcao, ano, max(1, min(quantidade, 26)))
    return Resultado(
        linhas,
        f"{RREO_2} · {funcao} · {ano}",
        sql,
        nota="Valores de despesa liquidada. Diga na resposta que é a liquidada.",
    )


async def balanco_orcamentario(capital: str, ano: int | None = None) -> Resultado:
    capital, ano = _capital(capital), _ano(ano)
    sql = """
        SELECT capital, uf, ano, receita_prevista_inicial, receita_prevista_atualizada,
               receita_realizada, percentual_receita_realizada, dotacao_inicial,
               dotacao_atualizada, despesa_empenhada, despesa_liquidada, despesa_paga,
               resultado_orcamentario, resultado
        FROM sem.balanco
        WHERE capital = $1 AND ($2::int IS NULL OR ano = $2)
        ORDER BY ano"""
    return Resultado(
        await banco.buscar(sql, capital, ano),
        f"{RREO_1} · {capital} · {_periodo(ano)}",
        sql,
        nota="Resultado orçamentário = receita realizada menos despesa empenhada.",
    )


async def receita_corrente_liquida(capital: str, ano: int | None = None) -> Resultado:
    capital, ano = _capital(capital), _ano(ano)
    sql = """
        SELECT capital, uf, ano, rcl, rcl_por_habitante, populacao
        FROM sem.receita_corrente_liquida
        WHERE capital = $1 AND ($2::int IS NULL OR ano = $2)
        ORDER BY ano"""
    return Resultado(
        await banco.buscar(sql, capital, ano), f"{RREO_3} · {capital} · {_periodo(ano)}", sql
    )


async def consulta_sql(sql: str) -> Resultado:
    """Rota 2: SQL escrito pelo modelo, validado, provado com EXPLAIN e só então executado."""
    aprovado = validar(sql, (await catalogo.carregar()).nomes)
    await banco.explicar(aprovado.sql)
    return Resultado(
        await banco.buscar(aprovado.sql),
        f"{FONTE} · consulta SQL sobre {', '.join('sem.' + v for v in aprovado.views)}",
        aprovado.sql,
        nota="Consulta derivada, não é métrica conferida. Diga isso na resposta.",
    )
