from __future__ import annotations

import codecs
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, TextIO

from core.utils.resource_context_manager import ResourceContextManager
from rag.ingestion.exceptions import (
    FileDecodeError,
    FileReadError,
    FileSourceError,
)

logger = logging.getLogger(__name__)


class FileReader:
    """
    Low-level reader for local filesystem sources.

    FileReader owns file I/O and resource lifecycle only. It does not
    understand document formats, parsing, sanitization, validation,
    chunking, or RAG.

    Large-content operations are generator based and bounded by
    ``chunk_size`` wherever the underlying operation permits it.
    """

    DEFAULT_CHUNK_SIZE = 64 * 1024

    def __init__(
        self,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(
                "chunk_size must be greater than zero.",
            )

        self._chunk_size = chunk_size

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    def read_bytes(
        self,
        source: Path,
    ) -> Iterator[bytes]:
        """
        Lazily read a binary file in bounded byte chunks.

        Raises:
            FileSourceError:
                If the source is invalid.

            FileReadError:
                If the file cannot be read.
        """

        self._validate_source(source)

        bytes_read = 0

        logger.debug(
            "Starting binary file read: source=%s",
            source,
        )

        try:
            with ResourceContextManager() as resources:
                file_handle = resources.create(
                    lambda: source.open("rb"),
                )

                while True:
                    chunk = file_handle.read(
                        self._chunk_size,
                    )

                    if not chunk:
                        break

                    bytes_read += len(chunk)

                    yield chunk

        except FileReadError:
            raise

        except OSError as exc:
            logger.exception(
                "Failed to read binary file: source=%s, bytes_read=%d",
                source,
                bytes_read,
            )

            raise FileReadError(
                f"Failed to read file: {source}",
            ) from exc

        except Exception as exc:
            logger.exception(
                "Unexpected error while reading binary file: " "source=%s, bytes_read=%d",
                source,
                bytes_read,
            )

            raise FileReadError(
                f"Unexpected failure while reading file: {source}",
            ) from exc

        finally:
            logger.debug(
                "Completed binary file read: source=%s, bytes_read=%d",
                source,
                bytes_read,
            )

    def read_text(
        self,
        source: Path,
        *,
        encoding: str = "utf-8",
    ) -> Iterator[str]:
        """
        Lazily read a text file using an incremental decoder.

        Raises:
            FileSourceError:
                If the source is invalid.

            FileDecodeError:
                If the content cannot be decoded.

            FileReadError:
                For other read failures.
        """

        self._validate_source(source)

        bytes_read = 0

        logger.debug(
            "Starting text file read: source=%s, encoding=%s",
            source,
            encoding,
        )

        try:
            decoder = codecs.getincrementaldecoder(
                encoding,
            )(
                errors="strict",
            )

            with ResourceContextManager() as resources:
                file_handle = resources.create(
                    lambda: source.open("rb"),
                )

                while True:
                    raw_chunk = file_handle.read(
                        self._chunk_size,
                    )

                    if not raw_chunk:
                        break

                    bytes_read += len(raw_chunk)

                    text_chunk = decoder.decode(
                        raw_chunk,
                        final=False,
                    )

                    if text_chunk:
                        yield text_chunk

                remaining = decoder.decode(
                    b"",
                    final=True,
                )

                if remaining:
                    yield remaining

        except UnicodeDecodeError as exc:
            logger.exception(
                "Failed to decode text file: " "source=%s, encoding=%s, bytes_read=%d",
                source,
                encoding,
                bytes_read,
            )

            raise FileDecodeError(
                f"Failed to decode file '{source}' " f"using encoding '{encoding}'.",
            ) from exc

        except OSError as exc:
            logger.exception(
                "Failed to read text file: " "source=%s, encoding=%s, bytes_read=%d",
                source,
                encoding,
                bytes_read,
            )

            raise FileReadError(
                f"Failed to read file: {source}",
            ) from exc

        except Exception as exc:
            logger.exception(
                "Unexpected error while reading text file: "
                "source=%s, encoding=%s, bytes_read=%d",
                source,
                encoding,
                bytes_read,
            )

            raise FileReadError(
                f"Unexpected failure while reading file: {source}",
            ) from exc

        finally:
            logger.debug(
                "Completed text file read: " "source=%s, encoding=%s, bytes_read=%d",
                source,
                encoding,
                bytes_read,
            )

    def read_lines(
        self,
        source: Path,
        *,
        encoding: str = "utf-8",
    ) -> Iterator[str]:
        """
        Lazily read a text file line by line.
        """

        self._validate_source(source)

        line_count = 0

        logger.debug(
            "Starting line-based file read: source=%s, encoding=%s",
            source,
            encoding,
        )

        try:
            with ResourceContextManager() as resources:
                file_handle = resources.create(
                    lambda: source.open(
                        "r",
                        encoding=encoding,
                        errors="strict",
                    ),
                )

                for line in file_handle:
                    line_count += 1
                    yield line

        except UnicodeDecodeError as exc:
            logger.exception(
                "Failed to decode file: " "source=%s, encoding=%s, lines_read=%d",
                source,
                encoding,
                line_count,
            )

            raise FileDecodeError(
                f"Failed to decode file '{source}' " f"using encoding '{encoding}'.",
            ) from exc

        except OSError as exc:
            logger.exception(
                "Failed to read file: " "source=%s, encoding=%s, lines_read=%d",
                source,
                encoding,
                line_count,
            )

            raise FileReadError(
                f"Failed to read file: {source}",
            ) from exc

        except Exception as exc:
            logger.exception(
                "Unexpected error while reading file: " "source=%s, encoding=%s, lines_read=%d",
                source,
                encoding,
                line_count,
            )

            raise FileReadError(
                f"Unexpected failure while reading file: {source}",
            ) from exc

        finally:
            logger.debug(
                "Completed line-based file read: " "source=%s, lines_read=%d",
                source,
                line_count,
            )

    def open_binary(
        self,
        source: Path,
        *,
        resources: ResourceContextManager,
    ) -> BinaryIO:
        """
        Open a binary file and transfer ownership to the supplied
        ResourceContextManager.
        """

        self._validate_source(source)

        try:
            file_handle = resources.create(
                lambda: source.open("rb"),
            )

            logger.debug(
                "Opened binary file for parser: source=%s",
                source,
            )

            return file_handle

        except OSError as exc:
            logger.exception(
                "Failed to open binary file: source=%s",
                source,
            )

            raise FileReadError(
                f"Failed to open file: {source}",
            ) from exc

        except Exception as exc:
            logger.exception(
                "Unexpected error opening binary file: source=%s",
                source,
            )

            raise FileReadError(
                f"Unexpected failure opening file: {source}",
            ) from exc

    def open_text(
        self,
        source: Path,
        *,
        resources: ResourceContextManager,
        encoding: str = "utf-8",
    ) -> TextIO:
        """
        Open a text file and transfer ownership to the supplied
        ResourceContextManager.
        """

        self._validate_source(source)

        try:
            file_handle = resources.create(
                lambda: source.open(
                    "r",
                    encoding=encoding,
                    errors="strict",
                ),
            )

            logger.debug(
                "Opened text file for parser: " "source=%s, encoding=%s",
                source,
                encoding,
            )

            return file_handle

        except OSError as exc:
            logger.exception(
                "Failed to open text file: " "source=%s, encoding=%s",
                source,
                encoding,
            )

            raise FileReadError(
                f"Failed to open file: {source}",
            ) from exc

        except Exception as exc:
            logger.exception(
                "Unexpected error opening text file: " "source=%s, encoding=%s",
                source,
                encoding,
            )

            raise FileReadError(
                f"Unexpected failure opening file: {source}",
            ) from exc

    @staticmethod
    def _validate_source(source: Path) -> None:
        if not source.exists():
            logger.warning(
                "File source does not exist: source=%s",
                source,
            )

            raise FileSourceError(
                f"Source file does not exist: {source}",
            )

        if not source.is_file():
            logger.warning(
                "File source is not a regular file: source=%s",
                source,
            )

            raise FileSourceError(
                f"Source path is not a regular file: {source}",
            )
