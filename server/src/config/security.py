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

    # REDIS_HOST/REDIS_PORT, not a single REDIS_URL field -- same
    # host/port composition pattern as DatabaseSettings.DB_HOST/
    # DB_PORT below, and what setup.sh's normalize_local_endpoint()
    # already writes into REDIS_HOST (localhost -> "redis", the
    # compose service name, for a local Docker install; see
    # configure_local_dependency_endpoints()). A prior version of this
    # field was a static `REDIS_URL: str = "redis://localhost:6379/0"`
    # that nothing ever overrode -- REDIS_HOST/REDIS_PORT existed in
    # env.example and setup.sh's own bookkeeping, but pydantic-settings
    # (extra="ignore") silently dropped them since neither matched a
    # declared field name, so every container always connected to
    # "localhost", which inside the api container is the container
    # itself, not the redis service -- broke any request that touched
    # the cache (guardrail/RAG-judge/embedding memoization), silently
    # in dev (redis's published host port made a non-containerized
    # `localhost:6379` connection accidentally work) and loudly in the
    # containerized release stack.
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    @field_validator("REDIS_PORT")
    @classmethod
    def validate_redis_port(cls, value: int) -> int:
        if not (1 <= value <= 65535):
            raise ValueError("REDIS_PORT must be between 1 and 65535.")
        return value

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

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
