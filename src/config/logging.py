from __future__ import annotations

from typing import Literal

from config.base import BaseAppSettings


class LoggingSettings(BaseAppSettings):
    """File and console logging configuration."""

    LOG_LEVEL: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = "INFO"

    LOG_FORMAT: Literal["json", "text"] = "json"
    LOG_FILE: str = "./logs/app.log"
    DATA_DIRECTORY: str = "./data"
    LOG_DIRECTORY: str = "./logs"
    LOG_MAX_MB: int = 100
    LOG_BACKUP_COUNT: int = 5
