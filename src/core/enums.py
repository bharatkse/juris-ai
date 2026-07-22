"""
All enumerations used across the application.
Using str-based enums keeps JSON serialisation automatic.
"""

from enum import StrEnum


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class CacheBackend(StrEnum):
    MEMORY = "memory"
    REDIS = "redis"


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
