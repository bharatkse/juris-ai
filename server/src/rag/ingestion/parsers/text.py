"""
Text parser.

Accepts text that is already available in memory and exposes it through
the generic parser contract.

TextParser does not perform cleaning, sanitization, validation,
chunking, embedding, indexing, persistence, or application-level
orchestration.
"""

from __future__ import annotations

from collections.abc import Iterator

from rag.ingestion.models import ParsedBlock
from rag.ingestion.parsers.protocol import ParserProtocol


class TextParser(ParserProtocol[str]):
    """
    Parser for sources that already provide plain text.

    A text source represents one logical source, therefore the parser
    yields a single ParsedBlock.
    """

    def parse(
        self,
        *,
        source: str,
    ) -> Iterator[ParsedBlock]:
        """
        Expose the supplied text as a ParsedBlock.

        Args:
            source:
                Raw source text already available in memory.

        Yields:
            A single ParsedBlock containing the supplied text.
        """

        if not source:
            return

        yield ParsedBlock(
            text=source,
            source="text",
            mime_type="text/plain",
            sequence=0,
        )
