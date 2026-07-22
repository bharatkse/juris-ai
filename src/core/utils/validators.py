# """
# Pure-function input validators used by services and API layers.
# Raise app-specific exceptions — never HTTPException directly.
# """

# from __future__ import annotations

# import re
# from pathlib import Path

# from src.core.constants import ALLOWED_EXTENSIONS, MAX_FILENAME_LENGTH, MAX_QUERY_LENGTH
# from src.core.exceptions import FileTooLargeError, UnsupportedFileTypeError, ValidationError


# def validate_pdf_filename(filename: str) -> str:
#     """
#     Return the validated filename or raise UnsupportedFileTypeError.
#     Also enforces length limit.
#     """
#     if not filename:
#         raise ValidationError("Filename must not be empty")

#     if len(filename) > MAX_FILENAME_LENGTH:
#         raise ValidationError(
#             f"Filename too long ({len(filename)} chars, max {MAX_FILENAME_LENGTH})"
#         )

#     suffix = Path(filename).suffix.lower()
#     if suffix not in ALLOWED_EXTENSIONS:
#         raise UnsupportedFileTypeError(
#             f"File type {suffix!r} is not supported. Accepted: {sorted(ALLOWED_EXTENSIONS)}"
#         )
#     return filename


# def validate_file_size(size_bytes: int, max_mb: int) -> None:
#     """Raise FileTooLargeError if size exceeds limit."""
#     max_bytes = max_mb * 1024 * 1024
#     if size_bytes > max_bytes:
#         raise FileTooLargeError(f"File is {size_bytes / (1024*1024):.1f} MB (max {max_mb} MB)")


# def validate_query(query: str) -> str:
#     """
#     Strip whitespace, check length, and return the cleaned query.
#     Raises ValidationError if empty or too long.
#     """
#     cleaned = query.strip()
#     if not cleaned:
#         raise ValidationError("Query must not be empty")
#     if len(cleaned) > MAX_QUERY_LENGTH:
#         raise ValidationError(f"Query too long ({len(cleaned)} chars, max {MAX_QUERY_LENGTH})")
#     return cleaned


# def validate_pagination(skip: int, limit: int) -> tuple[int, int]:
#     """Return validated (skip, limit) or raise ValidationError."""
#     if skip < 0:
#         raise ValidationError("skip must be >= 0")
#     if limit < 1 or limit > 100:
#         raise ValidationError("limit must be between 1 and 100")
#     return skip, limit


# def validate_document_id(document_id: str) -> str:
#     """Basic UUID-format check."""
#     pattern = re.compile(
#         r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
#         re.IGNORECASE,
#     )
#     if not pattern.match(document_id):
#         raise ValidationError(f"Invalid document ID format: {document_id!r}")
#     return document_id


# def validate_top_k(top_k: int) -> int:
#     """Return validated top_k or raise ValidationError."""
#     if top_k < 1 or top_k > 50:
#         raise ValidationError("top_k must be between 1 and 50")
#     return top_k
