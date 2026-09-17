from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, TypeVar

from rag.ingestion.models import ParsedBlock

SourceT = TypeVar("SourceT")


class ParserProtocol(Protocol[SourceT]):
    """
    Contract for incrementally converting a source into parsed blocks.

    Parsers must expose content lazily and must not construct a
    complete extracted-document representation.
    """

    def parse(
        self,
        *,
        source: SourceT,
    ) -> Iterator[ParsedBlock]:
        """
        Incrementally extract logical content blocks from a source.
        """
        ...
