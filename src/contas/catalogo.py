"""Lê a camada semântica do próprio banco e monta o cartão de esquema do prompt.

A fonte única é o COMMENT de cada view e coluna em sql/02-semantica.sql.
Documentar a view no banco é a mesma ação que ensinar o modelo, e não existe
cópia do esquema em Python para sair de sincronia.
"""

from dataclasses import dataclass, field

from . import banco

_SQL = """
SELECT c.relname AS view,
       obj_description(c.oid, 'pg_class') AS descricao,
       a.attname AS coluna,
       col_description(c.oid, a.attnum) AS comentario
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
WHERE n.nspname = 'sem' AND c.relkind = 'v'
ORDER BY c.relname, a.attnum
"""


@dataclass
class Catalogo:
    descricoes: dict[str, str] = field(default_factory=dict)
    colunas: dict[str, list[tuple[str, str | None]]] = field(default_factory=dict)

    @property
    def nomes(self) -> set[str]:
        return set(self.descricoes)

    def cartao(self) -> str:
        blocos = []
        for view, descricao in self.descricoes.items():
            colunas = self.colunas[view]
            linhas = [f"### sem.{view}", descricao, "Colunas: " + ", ".join(c for c, _ in colunas)]
            linhas += [f"- {c}: {comentario}" for c, comentario in colunas if comentario]
            blocos.append("\n".join(linhas))
        return "\n\n".join(blocos)


_cache: Catalogo | None = None


async def carregar() -> Catalogo:
    global _cache
    if _cache is None:
        cat = Catalogo()
        for r in await banco.buscar(_SQL):
            cat.descricoes[r["view"]] = r["descricao"] or ""
            cat.colunas.setdefault(r["view"], []).append((r["coluna"], r["comentario"]))
        _cache = cat
    return _cache
