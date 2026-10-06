"""A garantia vale mesmo com um modelo que inventa número.

O FunctionModel do PydanticAI faz o papel do LLM: chama a ferramenta, recebe o
dado certo e escreve a resposta que o teste mandar. Sem rede, sem banco e sem
LLM de verdade, o teste prova o que o agente faz quando o modelo erra.
"""

import asyncio
from decimal import Decimal

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from contas import agente, catalogo, metricas

FONTE = "SICONFI/Tesouro Nacional · RGF Anexo 1 · Recife · 2025"


@pytest.fixture(autouse=True)
def sem_banco(monkeypatch):
    async def cartao_vazio():
        return catalogo.Catalogo({"despesa_pessoal": "teste"}, {"despesa_pessoal": []})

    async def pessoal_de_recife(capital, ano=None):
        linha = {"capital": "Recife", "ano": 2025, "percentual_rcl": Decimal("44.09")}
        return metricas.Resultado([linha], FONTE, "SELECT ...")

    monkeypatch.setattr(catalogo, "carregar", cartao_vazio)
    monkeypatch.setattr(metricas, "despesa_com_pessoal", pessoal_de_recife)


def modelo_que_responde(texto: str, consulta: bool = True) -> FunctionModel:
    """Consulta a ferramenta na primeira volta (se `consulta`) e depois responde `texto`."""

    def responder(mensagens, info: AgentInfo) -> ModelResponse:
        if consulta and len(mensagens) == 1:
            args = {"capital": "Recife", "ano": 2025}
            return ModelResponse(parts=[ToolCallPart("despesa_com_pessoal", args)])
        return ModelResponse(parts=[TextPart(texto)])

    return FunctionModel(responder, model_name="modelo-de-teste")


def perguntar(modelo):
    return asyncio.run(agente.perguntar("pergunta", modelo))


def test_numero_que_veio_do_banco_passa_com_a_fonte():
    e = perguntar(modelo_que_responde("Foi 44,09% da RCL."))
    assert e.resposta == agente.Resposta("Foi 44,09% da RCL.", "respondida")
    assert e.reprovacoes == 0
    assert [p.fonte for p in e.passos] == [FONTE]


def test_numero_inventado_nunca_chega_ao_usuario():
    # O modelo insiste no número errado. A conferência devolve a resposta três vezes
    # e, no fim, quem perguntou recebe uma recusa, nunca o 41,2%.
    e = perguntar(modelo_que_responde("Foi 41,2% da RCL."))
    assert e.resposta == agente.RECUSA_SEGURA
    assert e.reprovacoes == 3


def test_numero_sem_consulta_nenhuma_tambem_e_barrado():
    e = perguntar(modelo_que_responde("Recife gastou R$ 3 bilhões.", consulta=False))
    assert e.resposta == agente.RECUSA_SEGURA


def test_desfecho_e_decidido_pelo_codigo():
    assert perguntar(modelo_que_responde("Não há dado de 2021.", consulta=False)).resposta == (
        agente.Resposta("Não há dado de 2021.", "recusada")
    )
    pergunta_de_volta = "Você quer a despesa liquidada ou a empenhada?"
    assert perguntar(modelo_que_responde(pergunta_de_volta, consulta=False)).resposta == (
        agente.Resposta(pergunta_de_volta, "esclarecimento")
    )
