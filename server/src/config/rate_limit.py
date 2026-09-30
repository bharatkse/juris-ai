from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ModelWrapValidatorHandler, PrivateAttr, field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
)

from config.base import BaseAppSettings

# The token quotas' old variable names (renamed in #84), still read but
# deprecated: each maps to its new name.
LEGACY_TOKEN_QUOTA_NAMES: Mapping[str, str] = {
    "RATE_LIMIT_REQUEST_TOKEN_QUOTA": "TOKEN_QUOTA_PER_REQUEST",
    "RATE_LIMIT_DAILY_TOKEN_QUOTA": "TOKEN_QUOTA_DAILY",
}

# Carries what _LegacyTokenQuotaSource found into the model validator.
_DEPRECATED_KEY = "deprecated_token_quota_names__"


@dataclass(frozen=True, slots=True)
class DeprecatedSetting:
    """A deprecated variable that was set, and whether its new name was too."""

    old_name: str
    new_name: str
    new_name_also_set: bool


class _LegacyTokenQuotaSource(PydanticBaseSettingsSource):
    """
    The old token quota names, at the lowest priority: an old name's value
    is used only when its new name isn't set anywhere (init arguments, the
    environment or the .env file), so a new name always wins, whichever
    source it is in. Every old name found is reported, for the startup
    warning (main.log_deprecated_settings()).
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        *,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
    ) -> None:
        super().__init__(settings_cls)
        self._init_names = (
            set(init_settings.init_kwargs)
            if isinstance(init_settings, InitSettingsSource)
            else set()
        )
        # The environment first: it takes priority over the .env file.
        self._env_maps = tuple(
            source.env_vars
            for source in (env_settings, dotenv_settings)
            if isinstance(source, EnvSettingsSource | DotEnvSettingsSource)
        )

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        deprecated: list[DeprecatedSetting] = []

        for old_name, new_name in LEGACY_TOKEN_QUOTA_NAMES.items():
            old_values = [env[old_name] for env in self._env_maps if env.get(old_name) is not None]
            if not old_values:
                continue

            new_name_set = new_name in self._init_names or any(
                env.get(new_name) is not None for env in self._env_maps
            )
            if not new_name_set:
                values[new_name] = old_values[0]

            deprecated.append(
                DeprecatedSetting(
                    old_name=old_name,
                    new_name=new_name,
                    new_name_also_set=new_name_set,
                )
            )

        if deprecated:
            values[_DEPRECATED_KEY] = tuple(deprecated)

        return values


class RateLimitSettings(BaseAppSettings):
    """
    Per-user request-rate and token-quota configuration.

    The defaults are placeholders, not derived from real traffic/cost
    data -- tune via env vars once real usage numbers exist
    (scripts/usage_percentiles.py reports them).
    """

    RATE_LIMIT_ENABLED: bool = True

    # (a) burst/rate limit: max requests per rolling-minute window.
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 20

    # (b) cost control: max total (input + output) tokens per user per
    # calendar day. 20x the per-request quota, so a user can make at
    # least 20 worst-case requests a day. The old RATE_LIMIT_* names are
    # still read, but deprecated (LEGACY_TOKEN_QUOTA_NAMES).
    TOKEN_QUOTA_DAILY: int = 2_000_000

    # (b2) cost control per request: max total tokens one chat request's
    # LLM calls may use. Checked before each call (core/usage.py), so a
    # call that would cross it is never made; the request fails with 413
    # REQUEST_TOKEN_QUOTA_EXCEEDED and the tokens already used still
    # count toward the daily quota. Not applied to a turn resumed after
    # an approval (that turn was admitted before the approval).
    TOKEN_QUOTA_PER_REQUEST: int = 100_000

    # (c) chat attachments (api/helpers/files.py): checked before a file
    # is read into memory, along with its type (only the types the parser
    # reads, core.constants.SUPPORTED_UPLOAD_CONTENT_TYPES; not a setting,
    # since another type couldn't be used). Each file's parsed text is also capped at
    # 20,000 characters before it reaches the model
    # (agentic/execution/attachments.py); that bounds the prompt, not
    # memory, parsing time or the number of files.
    UPLOAD_MAX_FILES: int = 5
    UPLOAD_MAX_FILE_BYTES: int = 10 * 1024 * 1024

    _deprecated_names: tuple[DeprecatedSetting, ...] = PrivateAttr(default=())

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            _LegacyTokenQuotaSource(
                settings_cls,
                init_settings=init_settings,
                env_settings=env_settings,
                dotenv_settings=dotenv_settings,
            ),
        )

    @model_validator(mode="wrap")
    @classmethod
    def record_deprecated_names(
        cls, data: Any, handler: ModelWrapValidatorHandler[RateLimitSettings]
    ) -> RateLimitSettings:
        deprecated = data.pop(_DEPRECATED_KEY, None) if isinstance(data, dict) else None
        settings = handler(data)
        if deprecated is not None:
            settings._deprecated_names = deprecated
        return settings

    def deprecated_names(self) -> tuple[DeprecatedSetting, ...]:
        """The deprecated quota variables that were set (logged at startup)."""

        return self._deprecated_names

    @field_validator(
        "RATE_LIMIT_REQUESTS_PER_MINUTE",
        "TOKEN_QUOTA_DAILY",
        "TOKEN_QUOTA_PER_REQUEST",
        "UPLOAD_MAX_FILES",
        "UPLOAD_MAX_FILE_BYTES",
    )
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Rate-limit values must be greater than zero.")
        return value

    @model_validator(mode="after")
    def validate_daily_quota_covers_one_request(self) -> RateLimitSettings:
        # Checked when settings load (at startup), so a daily quota that
        # would refuse even one full request fails fast.
        if self.TOKEN_QUOTA_DAILY < self.TOKEN_QUOTA_PER_REQUEST:
            raise ValueError(
                f"TOKEN_QUOTA_DAILY ({self.TOKEN_QUOTA_DAILY}) must be at least "
                f"TOKEN_QUOTA_PER_REQUEST ({self.TOKEN_QUOTA_PER_REQUEST})."
            )
        return self
