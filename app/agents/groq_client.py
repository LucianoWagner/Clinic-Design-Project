"""
LLM client usando ChatGroq de LangChain.
build_llm() está cacheada: se instancia una sola vez durante el ciclo de vida del proceso.
"""
from functools import lru_cache

from langchain_groq import ChatGroq

from app.core.config import settings


@lru_cache(maxsize=1)
def build_llm() -> ChatGroq:
    """
    Devuelve el LLM configurado con Groq.
    Cacheado con lru_cache para evitar reinstanciación por request.
    """
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0.2,
    )
