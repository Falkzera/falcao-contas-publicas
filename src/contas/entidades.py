"""O que a pessoa fala vira o valor que existe no banco.

"BH" vira Belo Horizonte, "capital do Ceará" vira Fortaleza, "saude" vira Saúde.
Quando isso falha em silêncio, o SQL sai perfeito e volta vazio, e vazio vira
"não há dados", que é uma mentira com cara de resposta. Por isso quem resolve é
o código, dentro de cada ferramenta, e o que não resolve volta para o modelo
como pergunta a fazer, nunca como filtro vazio.
"""

import difflib
import unicodedata
from dataclasses import dataclass

# capital -> (UF, nome do estado)
CAPITAIS = {
    "Rio Branco": ("AC", "Acre"),
    "Maceió": ("AL", "Alagoas"),
    "Manaus": ("AM", "Amazonas"),
    "Macapá": ("AP", "Amapá"),
    "Salvador": ("BA", "Bahia"),
    "Fortaleza": ("CE", "Ceará"),
    "Vitória": ("ES", "Espírito Santo"),
    "Goiânia": ("GO", "Goiás"),
    "São Luís": ("MA", "Maranhão"),
    "Belo Horizonte": ("MG", "Minas Gerais"),
    "Campo Grande": ("MS", "Mato Grosso do Sul"),
    "Cuiabá": ("MT", "Mato Grosso"),
    "Belém": ("PA", "Pará"),
    "João Pessoa": ("PB", "Paraíba"),
    "Recife": ("PE", "Pernambuco"),
    "Teresina": ("PI", "Piauí"),
    "Curitiba": ("PR", "Paraná"),
    "Rio de Janeiro": ("RJ", "Rio de Janeiro"),
    "Natal": ("RN", "Rio Grande do Norte"),
    "Porto Velho": ("RO", "Rondônia"),
    "Boa Vista": ("RR", "Roraima"),
    "Porto Alegre": ("RS", "Rio Grande do Sul"),
    "Florianópolis": ("SC", "Santa Catarina"),
    "Aracaju": ("SE", "Sergipe"),
    "São Paulo": ("SP", "São Paulo"),
    "Palmas": ("TO", "Tocantins"),
}

# As 28 funções de governo (Portaria MOG 42/1999), com o nome exato do demonstrativo.
FUNCOES = (
    "Legislativa",
    "Judiciária",
    "Essencial à Justiça",
    "Administração",
    "Defesa Nacional",
    "Segurança Pública",
    "Relações Exteriores",
    "Assistência Social",
    "Previdência Social",
    "Saúde",
    "Trabalho",
    "Educação",
    "Cultura",
    "Direitos da Cidadania",
    "Urbanismo",
    "Habitação",
    "Saneamento",
    "Gestão Ambiental",
    "Ciência e Tecnologia",
    "Agricultura",
    "Organização Agrária",
    "Indústria",
    "Comércio e Serviços",
    "Comunicações",
    "Energia",
    "Transporte",
    "Desporto e Lazer",
    "Encargos Especiais",
)

# Apelidos que as pessoas usam e que nenhuma similaridade de texto acertaria.
# Ampliar esta lista é o ajuste de maior retorno quando aparece erro real.
APELIDOS_CAPITAL = {
    "bh": "Belo Horizonte",
    "beaga": "Belo Horizonte",
    "sampa": "São Paulo",
    "rio": "Rio de Janeiro",
    "poa": "Porto Alegre",
    "floripa": "Florianópolis",
    "jampa": "João Pessoa",
    "sao luis do maranhao": "São Luís",
}
APELIDOS_FUNCAO = {
    "seguranca": "Segurança Pública",
    "assistencia": "Assistência Social",
    "previdencia": "Previdência Social",
    "transportes": "Transporte",
    "esporte": "Desporto e Lazer",
    "esportes": "Desporto e Lazer",
    "lazer": "Desporto e Lazer",
    "meio ambiente": "Gestão Ambiental",
    "ambiental": "Gestão Ambiental",
    "ciencia": "Ciência e Tecnologia",
    "tecnologia": "Ciência e Tecnologia",
    "moradia": "Habitação",
    "divida": "Encargos Especiais",
    "justica": "Judiciária",
    "saneamento basico": "Saneamento",
}

FORA_DA_BASE = {
    "brasilia": "Brasília não está na base: o DF presta contas como ente distrital, "
    "e não como município, então não há RREO nem RGF municipal de Brasília.",
    "distrito federal": "O Distrito Federal não está na base, que cobre as 26 capitais "
    "estaduais. O DF presta contas como ente distrital.",
}

_PREFIXOS = (
    "prefeitura municipal de ",
    "prefeitura de ",
    "prefeitura do ",
    "prefeitura da ",
    "municipio de ",
    "cidade de ",
    "capital do estado de ",
    "capital do estado do ",
    "capital do estado da ",
    "capital de ",
    "capital do ",
    "capital da ",
    "funcao ",
)


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", (texto or "").strip().lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = " ".join(t.replace("-", " ").split())
    for p in _PREFIXOS:
        if t.startswith(p):
            t = t[len(p) :]
    return t


@dataclass(frozen=True)
class Resolucao:
    valor: str | None
    motivo: str | None = None  # por que não resolveu, em português, para o modelo repassar


# Índices construídos uma vez: forma normalizada -> valor do banco.
_CAPITAL = {normalizar(c): c for c in CAPITAIS}
_CAPITAL |= {normalizar(estado): c for c, (_, estado) in CAPITAIS.items()}
_CAPITAL |= {uf.lower(): c for c, (uf, _) in CAPITAIS.items()}
_CAPITAL |= APELIDOS_CAPITAL
_FUNCAO = {normalizar(f): f for f in FUNCOES} | APELIDOS_FUNCAO


def _resolver(termo: str, indice: dict[str, str], o_que: str) -> Resolucao:
    alvo = normalizar(termo)
    if alvo in indice:
        return Resolucao(indice[alvo])
    # erro de digitação: só aceita quando há um candidato claro
    perto = difflib.get_close_matches(alvo, indice, n=3, cutoff=0.8)
    valores = list(dict.fromkeys(indice[p] for p in perto))
    if len(valores) == 1:
        return Resolucao(valores[0])
    if valores:
        return Resolucao(None, f"'{termo}' pode ser {' ou '.join(valores)}. Pergunte qual.")
    return Resolucao(None, f"'{termo}' não é {o_que} desta base.")


def capital(termo: str) -> Resolucao:
    alvo = normalizar(termo)
    if alvo in FORA_DA_BASE or alvo == "df":
        return Resolucao(None, FORA_DA_BASE.get(alvo, FORA_DA_BASE["distrito federal"]))
    r = _resolver(termo, _CAPITAL, "uma das 26 capitais estaduais")
    if r.valor is None and r.motivo and "não é" in r.motivo:
        return Resolucao(
            None,
            r.motivo + " A base cobre só as capitais dos estados; "
            "outros municípios não estão nela.",
        )
    return r


def funcao(termo: str) -> Resolucao:
    r = _resolver(termo, _FUNCAO, "uma função de governo")
    if r.valor is None and r.motivo and "não é" in r.motivo:
        return Resolucao(None, r.motivo + " Funções válidas: " + ", ".join(FUNCOES) + ".")
    return r
