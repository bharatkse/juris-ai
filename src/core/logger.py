"""
Structured logging system.
All modules call `get_logger(__name__)` to get their own logger.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Exception info
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Include extra fields safely
        standard_attrs = logging.LogRecord(
            name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
        ).__dict__.keys()

        extras = {k: v for k, v in record.__dict__.items() if k not in standard_attrs}

        if extras:
            payload["extra"] = extras

        return json.dumps(payload, ensure_ascii=False)


class _TextFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self) -> None:
        super().__init__(fmt=self.FORMAT, datefmt=self.DATE_FORMAT)


def _build_formatter(fmt: str) -> logging.Formatter:
    if fmt == "json":
        return _JsonFormatter()
    return _TextFormatter()


def setup_logging(
    level: str = "INFO",
    fmt: str = "json",
    log_file: str = "./logs/app.log",
    max_mb: int = 100,
    backup_count: int = 5,
) -> None:
    """
    Call once at application startup (in main.py).
    Configures the root logger with a console + rotating-file handler.
    """

    # Ensure log directory exists
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    formatter = _build_formatter(fmt)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=max_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # Root logger
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()

    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # Reduce noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.  Usage: logger = get_logger(__name__)"""
    return logging.getLogger(name)
