"""
LLM dependencies.
"""

from src.clients.groq import GroqClient

_groq_client = GroqClient()


def get_groq_client() -> GroqClient:
    """
    Return the shared Groq client.
    """

    return _groq_client
