"""Gemini API configuration — re-exports from llm_client for compatibility."""

from agents.llm_client import get_gemini_key, get_groq_key, require_llm_key

# Back-compat alias
get_api_key = get_gemini_key


def require_api_key() -> str:
    require_llm_key()
    key = get_gemini_key()
    if key:
        return key
    groq = get_groq_key()
    if groq:
        return groq
    raise RuntimeError("No API key configured")
