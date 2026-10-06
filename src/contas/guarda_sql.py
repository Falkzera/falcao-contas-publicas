"""Validação do SQL que o modelo escreve, antes de chegar ao banco.

É a terceira de três camadas, e as outras duas não dependem deste arquivo:
o papel do banco só lê e só enxerga o schema sem, e a conexão abre transação
somente leitura com tempo limite. Aqui o SQL é barrado cedo, com uma mensagem
que o modelo consegue usar para se corrigir.
"""

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from . import config


class SQLRecusado(Exception):
    """A mensagem volta para o modelo como instrução de correção."""


# Nós que não podem aparecer em nenhuma profundidade da árvore.
_PROIBIDOS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Copy,
    exp.Grant,
    exp.Revoke,
    exp.Command,
    exp.Set,
    exp.Transaction,
    exp.Commit,
    exp.Use,
    exp.Pragma,
    exp.Kill,
    exp.Into,  # SELECT ... INTO cria tabela
    exp.Lock,  # SELECT ... FOR UPDATE
)

# Funções perigosas mesmo dentro de um SELECT legítimo.
_PREFIXOS_BLOQUEADOS = ("pg_", "lo_", "dblink")
_FUNCOES_BLOQUEADAS = {
    "current_setting",
    "set_config",
    "query_to_xml",
    "table_to_xml",
    "cursor_to_xml",
    "query_to_xml_and_xmlschema",
    "txid_current",
}


@dataclass(frozen=True)
class SQLAprovado:
    sql: str
    views: tuple[str, ...]


def validar(sql: str, views_permitidas: set[str]) -> SQLAprovado:
    texto = (sql or "").strip().rstrip(";").strip()
    if not texto:
        raise SQLRecusado("SQL vazio.")
    try:
        arvores = sqlglot.parse(texto, dialect="postgres")
    except sqlglot.errors.ParseError as e:
        raise SQLRecusado(f"SQL inválido: {e}") from e
    if len(arvores) != 1 or arvores[0] is None:
        raise SQLRecusado("Envie uma única instrução SELECT.")
    raiz = arvores[0]

    if not isinstance(raiz, exp.Query):
        raise SQLRecusado("Só SELECT. Esta base é somente leitura.")
    for tipo in _PROIBIDOS:
        if raiz.find(tipo):
            raise SQLRecusado(f"{tipo.__name__.upper()} não é permitido. Só SELECT de leitura.")

    ctes = {c.alias_or_name.lower() for c in raiz.find_all(exp.CTE)}
    usadas = set()
    for tabela in raiz.find_all(exp.Table):
        nome, schema = tabela.name.lower(), tabela.db.lower()
        if nome in ctes and not schema:
            continue
        if schema not in ("", "sem") or nome not in views_permitidas:
            raise SQLRecusado(
                f"'{tabela.sql()}' não existe para você. Use só as views de sem: "
                f"{', '.join(sorted(views_permitidas))}."
            )
        usadas.add(nome)
    if not usadas:
        raise SQLRecusado("A consulta precisa ler pelo menos uma view de sem.")

    for f in raiz.find_all(exp.Anonymous):
        nome = str(f.this).lower()
        if nome in _FUNCOES_BLOQUEADAS or nome.startswith(_PREFIXOS_BLOQUEADOS):
            raise SQLRecusado(f"A função {nome} não é permitida.")

    # Teto de linhas: mantém um LIMIT menor que o teto, impõe o teto se faltar ou passar.
    teto = config.SQL_MAX_LINHAS
    limite = raiz.args.get("limit") if isinstance(raiz, exp.Select) else None
    atual = limite.expression if isinstance(limite, exp.Limit) else None
    if not (isinstance(atual, exp.Literal) and atual.is_int and int(atual.this) <= teto):
        if isinstance(raiz, exp.Select):
            raiz = raiz.limit(teto)
        else:  # UNION e afins: embrulha numa subconsulta
            raiz = exp.select("*").from_(raiz.subquery("q")).limit(teto)

    return SQLAprovado(raiz.sql(dialect="postgres"), tuple(sorted(usadas)))
