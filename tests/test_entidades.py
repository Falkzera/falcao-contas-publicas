"""O que a pessoa fala vira o valor do banco, ou vira pergunta, nunca filtro vazio."""

import pytest

from contas import entidades


@pytest.mark.parametrize(
    "termo, capital",
    [
        ("Recife", "Recife"),
        ("maceio", "Maceió"),
        ("BH", "Belo Horizonte"),
        ("Floripa", "Florianópolis"),
        ("capital do Ceará", "Fortaleza"),
        ("Pernambuco", "Recife"),
        ("PE", "Recife"),
        ("prefeitura de Maceió", "Maceió"),
        ("Salvadro", "Salvador"),  # erro de digitação com um candidato claro
    ],
)
def test_capital_resolvida(termo, capital):
    assert entidades.capital(termo).valor == capital


@pytest.mark.parametrize(
    "termo, trecho",
    [
        ("Brasília", "ente distrital"),
        ("Campinas", "só as capitais"),
    ],
)
def test_fora_da_base_explica_o_motivo(termo, trecho):
    r = entidades.capital(termo)
    assert r.valor is None and trecho in r.motivo


@pytest.mark.parametrize(
    "termo, funcao",
    [
        ("saude", "Saúde"),
        ("Educação", "Educação"),
        ("segurança", "Segurança Pública"),
        ("esportes", "Desporto e Lazer"),
        ("saneamento basico", "Saneamento"),
    ],
)
def test_funcao_resolvida(termo, funcao):
    assert entidades.funcao(termo).valor == funcao


def test_funcao_desconhecida_lista_as_validas():
    r = entidades.funcao("obras")
    assert r.valor is None and "Urbanismo" in r.motivo
