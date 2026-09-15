from __future__ import annotations

from pydantic import field_validator

from config.base import BaseAppSettings
from core.constants import TEST_DB_URL
from core.enums import EnvironmentEnum


class DatabaseSettings(BaseAppSettings):
    """PostgreSQL connection and connection pool configuration."""

    DB_HOST: str | None = None
    DB_PORT: int = 5432
    DB_NAME: str | None = None

    # Admin/migration role: owns the schema, runs Alembic. Used by
    # get_sync_database_url() (alembic/env.py) and
    # get_langgraph_database_url() (the LangGraph checkpointer's
    # connection, setup() call included) -- never by the app's normal
    # request-handling connection, which uses APP_DB_USER instead. See
    # get_admin_async_database_url() for the one place application
    # code (not migrations) is meant to still use this pair.
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None

    # Restricted runtime role: NOSUPERUSER, does not own the schema,
    # granted baseline CRUD via ALTER DEFAULT PRIVILEGES (see
    # deploy/docker/init/postgres/01-create-app-role.sh) rather than
    # table ownership. This is what get_async_database_url() resolves
    # to for DEVELOPMENT -- i.e. what session.py's shared engine (all
    # normal request handling) connects as. Local dev only: this
    # split is not implemented for STAGING/PRODUCTION.
    APP_DB_USER: str | None = None
    APP_DB_PASSWORD: str | None = None

    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800

    TEST_DATABASE_URL: str = TEST_DB_URL

    @field_validator("DB_PORT")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if not (1 <= value <= 65535):
            raise ValueError("DB_PORT must be between 1 and 65535.")
        return value

    @field_validator(
        "DATABASE_POOL_SIZE",
        "DATABASE_MAX_OVERFLOW",
        "DATABASE_POOL_TIMEOUT",
        "DATABASE_POOL_RECYCLE",
    )
    @classmethod
    def validate_positive_numbers(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Database pool values must be greater than zero.")
        return value

    def get_async_database_url(self, environment: EnvironmentEnum) -> str:
        """
        The runtime application's async connection -- session.py's
        shared engine, used for all normal request-handling DB access.

        Connects as APP_DB_USER (a restricted, NOSUPERUSER role), not
        DB_USER (the schema-owning admin/migration role). Admin-only
        code (Alembic, the LangGraph checkpointer, and scripts that
        need privilege the restricted role deliberately doesn't have)
        must use get_admin_async_database_url() /
        get_sync_database_url() / get_langgraph_database_url()
        instead -- never this method.
        """
        if environment is EnvironmentEnum.TESTING:
            return self.TEST_DATABASE_URL
        if environment is EnvironmentEnum.DEVELOPMENT:
            return (
                f"postgresql+asyncpg://"
                f"{self.APP_DB_USER}:{self.APP_DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}"
                f"/{self.DB_NAME}"
            )
        raise NotImplementedError("Async URL not implemented for this environment.")

    def get_admin_async_database_url(self, environment: EnvironmentEnum) -> str:
        """
        The schema-owning admin/migration connection (DB_USER), as an
        async URL -- for admin-only application code that needs
        privilege the restricted runtime role (get_async_database_url()
        above) deliberately doesn't have: scripts/python/
        purge_compliance_log.py (disables compliance_log's
        immutability trigger, which requires table ownership) and
        scripts/python/verify_compliance_log_privileges.py (CREATE
        ROLE / GRANT / REVOKE, which requires elevated privilege).

        Never use this for normal request-handling code paths -- that
        defeats the point of the role split.
        """
        if environment is EnvironmentEnum.TESTING:
            return self.TEST_DATABASE_URL
        if environment is EnvironmentEnum.DEVELOPMENT:
            return (
                f"postgresql+asyncpg://"
                f"{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}"
                f"/{self.DB_NAME}"
            )
        raise NotImplementedError("Admin async URL not implemented for this environment.")

    def get_sync_database_url(self, environment: EnvironmentEnum) -> str:
        """
        Alembic's connection (env.py). Always DB_USER -- migrations
        create/alter schema, which requires the admin/owner role
        regardless of how the runtime app connects.
        """
        if environment is EnvironmentEnum.TESTING:
            return self.TEST_DATABASE_URL
        return (
            f"postgresql+psycopg://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    def get_langgraph_database_url(self) -> str:
        """
        The LangGraph checkpointer's connection -- used for both its
        one-time setup() call (DDL, needs the admin role) and, because
        main.py keeps and reuses the same checkpointer/connection for
        the app's whole lifetime, its ongoing runtime checkpoint
        reads/writes too. Deliberately left on DB_USER, unchanged:
        splitting checkpointer setup from checkpointer runtime use is
        a separate change (a second, differently-scoped connection)
        outside this role-separation task.
        """
        return (
            f"postgresql://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
