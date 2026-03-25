"""
Centralized logging configuration.

This module provides:
- One-time logging configuration
- Environment-driven log level
- Consistent log formatting across the application
"""

import logging
import sys

from src.config import settings

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def configure_logging() -> None:
    """
    Configure application-wide logging.

    This function is safe to call multiple times and ensures:
    - No duplicate handlers
    - Consistent log format
    - Log level driven by environment
    """
    root_logger = logging.getLogger()

    # Prevent duplicate handlers (important for reload / tests)
    if root_logger.handlers:
        return

    log_level = logging.DEBUG if settings.debug else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))

    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a module-scoped logger.

    Args:
        name: Typically __name__

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
