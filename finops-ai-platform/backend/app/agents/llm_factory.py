"""
LLM Factory — creates the correct LangChain chat model
based on the configured provider.
"""
from app.config import settings


def get_llm(temperature: float = 0):
    """
    Create a LangChain chat model based on settings.llm_provider.

    Supports:
        - "groq"   → ChatOpenAI (Groq uses OpenAI-compatible API, FREE tier)
        - "gemini" → ChatGoogleGenerativeAI
        - "openai" → ChatOpenAI
        - "grok"   → ChatOpenAI (xAI uses OpenAI-compatible API)
    """
    if settings.llm_provider == "groq":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=temperature,
        )
    elif settings.llm_provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            temperature=temperature,
        )
    elif settings.llm_provider == "grok":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.grok_api_key,
            base_url="https://api.x.ai/v1",
            temperature=temperature,
        )
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
        )
