"""Configuração por variável de ambiente. Nenhum segredo no código."""

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]

# Exporta o .env para os.environ: cada provedor de LLM lê a própria chave de lá
# (ANTHROPIC_API_KEY, OPENAI_API_KEY...). O que já estiver no ambiente vence.
load_dotenv(RAIZ / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")  # o banner do PydanticAI polui a CLI

LLM_MODELO = os.getenv("LLM_MODELO", "anthropic:claude-opus-5-5")
# Uma chave só, a do provedor que estiver em LLM_MODELO, qualquer que seja.
LLM_API_KEY = os.getenv("LLM_API_KEY") or None
# Só para modelo local ou endpoint próprio compatível com a API da OpenAI.
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or None

# O agente usa sempre o papel somente leitura. O admin só serve para a carga.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agente_ro:agente_ro@127.0.0.1:5437/contas")
DATABASE_URL_ADMIN = os.getenv(
    "DATABASE_URL_ADMIN", "postgresql://contas:contas@127.0.0.1:5437/contas"
)

SQL_TIMEOUT_MS = int(os.getenv("SQL_TIMEOUT_MS", "5000"))
SQL_MAX_LINHAS = int(os.getenv("SQL_MAX_LINHAS", "100"))
