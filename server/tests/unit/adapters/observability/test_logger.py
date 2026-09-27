"""
Unit tests for logging utilities.
"""

from __future__ import annotations

import json
import logging

from adapters.observability.logger import (
    _build_formatter,
    _JsonFormatter,
    _TextFormatter,
    get_logger,
    setup_logging,
)


def test_build_formatter_returns_json_formatter() -> None:
    """
    It should return the JSON formatter.
    """

    formatter = _build_formatter(
        "json",
    )

    assert isinstance(
        formatter,
        _JsonFormatter,
    )


def test_build_formatter_returns_text_formatter() -> None:
    """
    It should return the text formatter.
    """

    formatter = _build_formatter(
        "text",
    )

    assert isinstance(
        formatter,
        _TextFormatter,
    )


def test_text_formatter_uses_expected_format() -> None:
    """
    It should initialize the expected text formatter.
    """

    formatter = _TextFormatter()

    assert formatter._style._fmt == _TextFormatter.FORMAT
    assert formatter.datefmt == _TextFormatter.DATE_FORMAT


def test_json_formatter_formats_log_record() -> None:
    """
    It should serialize a log record as JSON.
    """

    formatter = _JsonFormatter()

    record = logging.LogRecord(
        name="tests",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="Hello",
        args=(),
        exc_info=None,
    )

    payload = json.loads(
        formatter.format(
            record,
        )
    )

    assert payload["level"] == "INFO"
    assert payload["logger"] == "tests"
    assert payload["message"] == "Hello"
    assert payload["line"] == 42
    assert payload["module"] == "test_logger"
    assert payload["function"] is None
    assert "timestamp" in payload


def test_json_formatter_includes_extra_fields() -> None:
    """
    It should include custom log record attributes.
    """

    formatter = _JsonFormatter()

    record = logging.LogRecord(
        name="tests",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Hello",
        args=(),
        exc_info=None,
    )

    record.request_id = "request_123"

    payload = json.loads(
        formatter.format(
            record,
        )
    )

    assert payload["extra"]["request_id"] == "request_123"


def test_json_formatter_includes_exception() -> None:
    """
    It should include exception information.
    """

    formatter = _JsonFormatter()

    try:
        raise RuntimeError(
            "Boom",
        )
    except RuntimeError:
        record = logging.LogRecord(
            name="tests",
            level=logging.ERROR,
            pathname=__file__,
            lineno=10,
            msg="Failure",
            args=(),
            exc_info=True,
        )

        record.exc_info = logging.sys.exc_info()

    payload = json.loads(
        formatter.format(
            record,
        )
    )

    assert "exception" in payload
    assert "RuntimeError" in payload["exception"]


def test_setup_logging_configures_root_logger(
    tmp_path,
) -> None:
    """
    It should configure the root logger.
    """

    logfile = tmp_path / "app.log"

    setup_logging(
        level="DEBUG",
        fmt="text",
        log_file=str(logfile),
    )

    root = logging.getLogger()

    assert root.level == logging.DEBUG
    assert len(root.handlers) == 2


def test_get_logger_returns_named_logger() -> None:
    """
    It should return a named logger.
    """

    logger = get_logger(
        "my.logger",
    )

    assert isinstance(
        logger,
        logging.Logger,
    )

    assert logger.name == "my.logger"
