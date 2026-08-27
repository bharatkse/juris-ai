from __future__ import annotations

from pydantic import Field, SecretStr, field_validator

from config.base import BaseAppSettings
from core.constants import DEFAULT_JWT_ACCESS_TOKEN_EXPIRE_MINUTES
from core.enums import CacheBackendEnum, JWTAlgorithmEnum


class SecuritySettings(BaseAppSettings):
    """Cryptographic secrets, JWT tokens, and Cache setup."""

    SECRET_KEY: str | None = Field(
        default=None,
        description="Application secret key used for signing JWTs and sessions.",
    )

    JWT_ALGORITHM: str = JWTAlgorithmEnum.HS256
    access_token_expire_minutes: int = DEFAULT_JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    JWT_SECRET_KEY: SecretStr

    # Cache
    CACHE_BACKEND: CacheBackendEnum = CacheBackendEnum.REDIS
    CACHE_TTL: int = 3600
    CACHE_MAX_SIZE: int = 1000
    REDIS_URL: str = "redis://localhost:6379/0"

    @field_validator("CACHE_TTL")
    @classmethod
    def validate_cache_ttl(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("CACHE_TTL must be greater than zero.")
        return value

    @property
    def redis_enabled(self) -> bool:
        return self.CACHE_BACKEND is CacheBackendEnum.REDIS

    @property
    def jwt_secret_key(self) -> str:
        return self.JWT_SECRET_KEY.get_secret_value()
