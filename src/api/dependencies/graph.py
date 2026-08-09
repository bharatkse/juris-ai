"""
LLM dependencies.
"""

from src.clients.llm.groq import GroqClient
from src.core.config import settings

_groq_client = GroqClient(
    api_key=settings.GROQ_API_KEY,
    model=settings.GROQ_MODEL,
)


def get_groq_client() -> GroqClient:
    """
    Return the shared Groq client.
    """

    return _groq_client
