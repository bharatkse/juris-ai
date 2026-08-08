"""
Runtime validation composition.

Creates response validation services.
"""

from __future__ import annotations

from src.validation.response import ResponseValidator


def create_response_validator() -> ResponseValidator:
    """
    Create the response validator.
    """

    return ResponseValidator()
