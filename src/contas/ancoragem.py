"""Conferência numérica da resposta: todo número tem que ter vindo do banco.

O modelo pode chamar a ferramenta certa, receber o dado certo e mesmo assim
escrever outro número, às vezes copiado de um exemplo do próprio prompt.
Instrução não resolve isso, porque instrução é sugestão. Aqui a checagem é
código comparando a resposta com o que as ferramentas devolveram.

O que é conferido: valores em R$, percentuais, pontos percentuais e contagens
de capitais. Cada número é comparado com a precisão com que foi escrito.
"R$ 1,77 bilhão" é aceito para 1.766.677.855,01 porque arredonda certo, e
"R$ 1,76 bilhão" não é.

Ponytail: número solto sem unidade (ex.: "art. 20", "2º lugar") não é
conferido. O teto é um número inventado sem unidade passar. Ampliar o padrão
de contagem resolve se aparecer na avaliação.
"""

import re
from decimal import Decimal, InvalidOperation
from itertools import combinations
from typing import NamedTuple

_MAGNITUDE = {
    "bilhao": 9,
    "bilhoes": 9,
    "bilhão": 9,
    "bilhões": 9,
    "bi": 9,
    "milhao": 6,
    "milhoes": 6,
    "milhão": 6,
    "milhões": 6,
    "mi": 6,
    "mil": 3,
}
_NUM = r"-?\d[\d.,]*\d|-?\d"
_RE_REAIS = re.compile(
    rf"R\$\s*({_NUM})(?:\s*(bilh(?:ão|ões|ao|oes)|bi|milh(?:ão|ões|ao|oes)|mi|mil)\b)?",
    re.IGNORECASE,
)
_RE_PERCENTUAL = re.compile(rf"({_NUM})\s*(?:%|por\s*cento|p\.\s?p\.|pontos?\s+percentua(?:l|is))")
# Contagem também por extenso: "Quatro capitais ficaram acima do alerta" é como o
# modelo escreve, e sem isto "cinco capitais" passaria sem conferência.
_EXTENSO = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3, "tres": 3, "quatro": 4,
    "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11,
    "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14, "quinze": 15,
    "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20,
}  # fmt: skip
_PALAVRA = "|".join(sorted(_EXTENSO, key=len, reverse=True))
_RE_CONTAGEM = re.compile(
    rf"(?<![\d.,\w])(\d{{1,3}}|vinte\s+e\s+(?:{_PALAVRA})|{_PALAVRA})\s+"
    r"(?:das\s+\d+\s+)?(?:capitais|cidades|munic[ií]pios|prefeituras)\b",
    re.IGNORECASE,
)


def _contagem(texto: str) -> Decimal:
    """'4' -> 4 · 'quatro' -> 4 · 'vinte e duas' -> 22."""
    palavras = texto.lower().split()
    if palavras[0].isdigit():
        return Decimal(palavras[0])
    return Decimal(sum(_EXTENSO[p] for p in palavras if p != "e"))


# Formato brasileiro: 1.234.567,89 · 1234,5 · 54. Valor em R$ ou % fora disso é
# número certo com formatação quebrada ("R$ 2,274,859,448,85"), a primeira coisa
# que quem lê percebe. A avaliação pegou o modelo local fazendo isso três vezes.
_RE_FORMATO_BR = re.compile(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?")

# Constantes da lei e da própria base, que podem ser citadas sem consulta:
# limites da LRF para o Executivo municipal (54%, 51,3%, 48,6%), as frações
# que os definem (95% e 90% do máximo) e o tamanho da base (26 capitais).
CONSTANTES = {Decimal(v) for v in ("54", "51.3", "48.6", "95", "90", "26")}


def para_decimal(texto: str) -> tuple[Decimal, Decimal] | None:
    """'1.766.677.855,01' -> (1766677855.01, 0.01). O segundo valor é o passo da
    última casa escrita, que define a tolerância da comparação."""
    t = texto.strip()
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):  # 1.234,56 (pt-BR)
            t = t.replace(".", "").replace(",", ".")
        else:  # 1,234.56 (en-US)
            t = t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    elif t.count(".") > 1 or re.fullmatch(r"-?\d{1,3}\.\d{3}", t):
        t = t.replace(".", "")  # ponto de milhar
    try:
        valor = Decimal(t)
    except InvalidOperation:
        return None
    casas = len(t.split(".")[1]) if "." in t else 0
    return valor, Decimal(1).scaleb(-casas)


class Numero(NamedTuple):
    trecho: str
    valor: Decimal
    passo: Decimal  # a última casa escrita: define a tolerância da comparação
    contagem: bool = False


def numeros_citados(texto: str) -> list[Numero]:
    """Cada número conferível do texto: R$, percentual, pontos percentuais e contagem."""
    achados = []
    for m in _RE_REAIS.finditer(texto):
        lido = para_decimal(m.group(1))
        if lido:
            valor, passo = lido
            if m.group(2):
                escala = _MAGNITUDE[m.group(2).lower()]
                valor, passo = valor.scaleb(escala), passo.scaleb(escala)
            achados.append(Numero(m.group(0).strip(), valor, passo))
    sem_reais = _RE_REAIS.sub(" ", texto)
    for m in _RE_PERCENTUAL.finditer(sem_reais):
        if lido := para_decimal(m.group(1)):
            achados.append(Numero(m.group(0).strip(), *lido))
    for m in _RE_CONTAGEM.finditer(sem_reais):
        achados.append(Numero(m.group(0).strip(), _contagem(m.group(1)), Decimal(1), True))
    return achados


def valores_em(dado, saida: set[Decimal] | None = None) -> set[Decimal]:
    """Todo número de um retorno de ferramenta, em qualquer profundidade."""
    saida = set() if saida is None else saida
    if isinstance(dado, dict):
        for v in dado.values():
            valores_em(v, saida)
    elif isinstance(dado, (list, tuple, set)):
        for v in dado:
            valores_em(v, saida)
    elif isinstance(dado, bool) or dado is None:
        pass
    elif isinstance(dado, (int, float, Decimal)):
        saida.add(Decimal(str(dado)))
    elif isinstance(dado, str):
        saida.update(n.valor for n in numeros_citados(dado))
        if lido := para_decimal(dado.replace("R$", "").replace("%", "").strip()):
            saida.add(lido[0])
    return saida


def _combinados(base: set[Decimal]) -> set[Decimal]:
    """Base + somas e diferenças de pares, para o caso legítimo de comparar dois
    resultados ("Recife ficou R$ X acima de Salvador"). Não vale para contagem:
    com 3 e 1 na base, "4 capitais" passaria sem nenhuma consulta ter devolvido 4."""
    combinados = set(base)
    valores = sorted(v for v in base if v != 0)
    if len(valores) <= 80:  # ponytail: O(n²); acima disso só a base exata
        for a, b in combinations(valores, 2):
            combinados |= {a + b, abs(a - b)}
    return combinados


def _bate(valor: Decimal, passo: Decimal, permitidos: set[Decimal]) -> bool:
    meio = passo / 2 + Decimal("1e-9")
    return any(abs(valor - p) <= meio or abs(-valor - p) <= meio for p in permitidos)


def mal_formatados(texto: str) -> list[str]:
    """Valores em R$ ou % que não estão no formato brasileiro."""
    sem_reais = _RE_REAIS.sub(" ", texto)
    return [
        m.group(0).strip()
        for regex, alvo in ((_RE_REAIS, texto), (_RE_PERCENTUAL, sem_reais))
        for m in regex.finditer(alvo)
        if not _RE_FORMATO_BR.fullmatch(m.group(1))
    ]


def orfaos(texto: str, vistos: set[Decimal]) -> list[str]:
    """Trechos da resposta com número que não veio das ferramentas, ou que veio com
    a formatação quebrada."""
    exatos = vistos | CONSTANTES
    combinados = _combinados(vistos) | CONSTANTES
    ruins = mal_formatados(texto)
    return ruins + [
        n.trecho
        for n in numeros_citados(texto)
        if n.trecho not in ruins
        and not (1900 <= n.valor <= 2100 and n.passo == 1)  # ano
        and not _bate(n.valor, n.passo, exatos if n.contagem else combinados)
    ]


def _todos(texto: str) -> list[Numero]:
    """Os números com unidade e também os soltos ("top 5", "acima de 45")."""
    return numeros_citados(texto) + [
        Numero(m.group(0), *lido)
        for m in re.finditer(_NUM, texto)
        if (lido := para_decimal(m.group(0)))
    ]


def numeros_da_pergunta(pergunta: str) -> set[Decimal]:
    """Número que a própria pessoa escreveu pode voltar na resposta."""
    return {n.valor for n in _todos(pergunta or "")}


def cita(texto: str, esperado: Decimal) -> bool:
    """A resposta cita o valor esperado, com a precisão em que foi escrito?
    Usado pela avaliação para comparar com a verdade-terreno."""
    return any(_bate(n.valor, n.passo, {esperado}) for n in _todos(texto))
