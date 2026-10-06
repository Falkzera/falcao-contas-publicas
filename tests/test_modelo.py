"""Agnóstico de verdade: uma chave só (LLM_API_KEY) chega a qualquer provedor.

Monta o modelo de cada provedor com a mesma chave e confere que ela chegou ao
cliente. Nenhuma chamada de rede.
"""

import pytest

from contas import agente, config


@pytest.mark.parametrize(
    "nome",
    [
        "openai:gpt-4.1-mini",
        "anthropic:claude-opus-5-5",
        "deepseek:deepseek-chat",
        "google:gemini-2.5-flash",
        "openrouter:qwen/qwen3-14b",
    ],
)
def test_uma_chave_serve_para_qualquer_provedor(nome, monkeypatch):
    monkeypatch.setattr(config, "LLM_API_KEY", "chave-de-teste")
    cliente = agente._modelo(nome).client
    chave = getattr(cliente, "api_key", None) or cliente._api_client.api_key
    assert chave == "chave-de-teste"
