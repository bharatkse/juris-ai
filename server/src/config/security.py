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

    # TTL specifically for LLM-judge/embedding memoization
    # (wiring/factories/cache.py) -- deliberately separate from
    # CACHE_TTL above (a shorter, generic default not tailored to this
    # use case). Judge/embedding outputs for a given input don't
    # logically expire; 7 days is a predictable operational bound
    # rather than the real eviction mechanism -- Redis's own
    # `--maxmemory 256mb --maxmemory-policy allkeys-lru`
    # (deploy/docker/docker-compose.yml) does the actual bounding.
    CACHE_TTL_SECONDS: int = 604_800

    @field_validator("CACHE_TTL", "CACHE_TTL_SECONDS")
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
