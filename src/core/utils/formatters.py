# """
# Stateless functions that format domain objects into API-friendly shapes.
# """

# from __future__ import annotations

# from datetime import UTC, datetime

# from src.models.retrieval import RAGResult, RetrievalDocument, RetrievalResult
# from src.schemas.conversation import AskResponse, ChunkOut, SearchResponse


# def format_chunk_out(doc: RetrievalDocument) -> ChunkOut:
#     return ChunkOut(
#         chunk_id=doc.chunk_id,
#         document_id=doc.document_id,
#         document_name=doc.document_name,
#         chunk_text=doc.chunk_text,
#         relevance_score=round(doc.relevance_score, 4),
#         sequence=doc.sequence,
#     )


# def format_search_response(
#     result: RetrievalResult,
#     cached: bool = False,
# ) -> SearchResponse:
#     return SearchResponse(
#         query=result.query,
#         chunks=[format_chunk_out(d) for d in result.documents],
#         count=len(result.documents),
#         cached=cached,
#     )


# def format_ask_response(result: RAGResult) -> AskResponse:
#     return AskResponse(
#         query=result.query,
#         answer=result.generated_answer,
#         chunks=[format_chunk_out(d) for d in result.documents],
#         source_documents=result.source_documents,
#         model_used=result.model_used,
#         cached=result.cached,
#     )


# def utcnow_iso() -> str:
#     """Current UTC time as ISO-8601 string."""
#     return datetime.now(tz=UTC).isoformat()


# def bytes_to_mb(size_bytes: int, decimals: int = 2) -> float:
#     return round(size_bytes / (1024 * 1024), decimals)


# def truncate(text: str, max_len: int = 100, suffix: str = "…") -> str:
#     """Truncate text to `max_len` chars with a trailing ellipsis."""
#     if len(text) <= max_len:
#         return text
#     return text[: max_len - len(suffix)] + suffix
