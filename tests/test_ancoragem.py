"""A conferência numérica: o que passa, o que é barrado e por quê."""

from decimal import Decimal as D

from contas import ancoragem as a

# O que uma ferramenta devolveu (formatado em pt-BR, como o modelo recebe).
RETORNO = {
    "linhas": [
        {
            "capital": "Maceió",
            "despesa_pessoal": "R$ 1.766.677.855,01",
            "percentual_rcl": "40,75%",
            "folga_ate_limite_maximo": "R$ 574.396.876,87",
            "pontos_ate_limite_maximo": "13,25 p.p.",
            "populacao": "994.952",
        }
    ],
    "linhas_retornadas": 1,
    "total_que_atende": "3",
}
VISTOS = a.valores_em(RETORNO)


def test_le_numero_em_formato_brasileiro():
    assert a.para_decimal("1.766.677.855,01") == (D("1766677855.01"), D("0.01"))
    assert a.para_decimal("1,77") == (D("1.77"), D("0.01"))
    assert a.para_decimal("1.766") == (D("1766"), D("1"))  # ponto de milhar
    assert a.para_decimal("1,234.56") == (D("1234.56"), D("0.01"))  # formato americano


def test_valor_exato_e_arredondamento_certo_passam():
    assert a.orfaos("Gastou R$ 1.766.677.855,01, ou 40,75% da RCL.", VISTOS) == []
    assert a.orfaos("Cerca de R$ 1,77 bilhão, 40,8% da RCL.", VISTOS) == []
    assert a.orfaos("R$ 1,8 bi, com 13,25 pontos percentuais de folga.", VISTOS) == []
    assert a.orfaos("Folga de R$ 574 milhões.", VISTOS) == []


def test_arredondamento_errado_e_numero_inventado_sao_barrados():
    assert a.orfaos("Cerca de R$ 1,76 bilhão.", VISTOS) == ["R$ 1,76 bilhão"]
    assert a.orfaos("A despesa foi de 41,2% da RCL.", VISTOS) == ["41,2%"]


def test_magnitude_abreviada_nao_vira_cinco_reais():
    # "R$ 5,286 bilhões" lido sem a magnitude viraria R$ 5,29 e reprovaria por engano;
    # lido com a magnitude, é um valor que o banco não devolveu.
    assert a.orfaos("R$ 5,286 bilhões", VISTOS) == ["R$ 5,286 bilhões"]
    assert a.orfaos("R$ 5,286 bilhões", {D("5286362866.93")}) == []


def test_contagem_e_conferida():
    assert a.orfaos("3 capitais passaram do alerta.", VISTOS) == []
    assert a.orfaos("4 capitais passaram do alerta.", VISTOS) == ["4 capitais"]


def test_ano_constantes_da_lei_e_sinal_passam():
    assert a.orfaos("Em 2023 e 2025 a base tem dados.", VISTOS) == []
    assert a.orfaos("Abaixo do alerta (48,6%) e do máximo (54%).", VISTOS) == []
    assert a.orfaos("Déficit de R$ 574.396.876,87.", VISTOS) == []  # valor negativo no banco


def test_soma_e_diferenca_de_dois_resultados_passam():
    vistos = {D("100.50"), D("40.25")}
    assert a.orfaos("A diferença foi de R$ 60,25.", vistos) == []
    assert a.orfaos("Juntas, R$ 140,75.", vistos) == []


def test_numero_da_pergunta_pode_voltar():
    vistos = a.numeros_da_pergunta("Quais gastaram mais de 45% da RCL?")
    assert a.orfaos("Duas passaram de 45% da RCL.", vistos) == []


def test_cita_compara_com_a_precisao_escrita():
    assert a.cita("Gastou R$ 1,77 bilhão", D("1766677855.01"))
    assert a.cita("foram 3 capitais", D("3"))
    assert not a.cita("Gastou R$ 1,9 bilhão", D("1766677855.01"))


def test_numero_certo_com_formato_quebrado_e_barrado():
    # Casos reais da avaliação: o valor estava certo, a pontuação não.
    certo = {D("2274859448.85"), D("6534985935.64"), D("48.6")}
    assert a.orfaos("Empenhou R$ 2,274,859,448,85.", certo) == ["R$ 2,274,859,448,85"]
    assert a.orfaos("Gastaram R$ 6,534.985.935,64.", certo) == ["R$ 6,534.985.935,64"]
    assert a.orfaos("O alerta é 48.6%.", certo) == ["48.6%"]
    assert a.orfaos("Empenhou R$ 2.274.859.448,85, ou R$ 2,27 bilhões.", certo) == []


def test_contagem_por_extenso_e_conferida():
    # Caso real da avaliação (DeepSeek): "Quatro capitais ficaram acima do alerta".
    assert a.orfaos("Três capitais passaram do alerta.", VISTOS) == []
    assert a.orfaos("Quatro capitais passaram do alerta.", VISTOS) == ["Quatro capitais"]
    assert a.cita("Quatro capitais ficaram acima do limite de alerta.", D(4))
    assert a.cita("Foram vinte e duas capitais abaixo do alerta.", D(22))
