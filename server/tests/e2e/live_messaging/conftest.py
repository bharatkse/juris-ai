"""
Live messaging suite setup: which MCP servers the app sends through, and
where delivered messages are counted (docs/messaging-live-test.md).

- Email: MCP_GMAIL_SERVER_URL when set (a real server), else the sandbox
  MCP server (SANDBOX_MCP_URL, default http://localhost:8765/mcp), which
  relays to Mailpit. Counted over IMAP when LIVE_TEST_IMAP_HOST/USER/
  PASSWORD are set, else through Mailpit's API (MAILPIT_API_URL, default
  http://localhost:8025). A real server without IMAP credentials: skipped.
- Slack: MCP_SLACK_SERVER_URL when set, else the sandbox server. Counted
  in SLACK_TEST_CHANNEL_ID's history with SLACK_TEST_BOT_TOKEN; skipped
  when either is missing.

Each of these variables is read from the environment, else from
server/.env (_env()), so either place works (docs/slack-test-workspace-
setup.md).
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from dotenv import dotenv_values

from config.settings import get_settings
from tests.e2e.live_messaging.verifiers import (
    DeliveryVerifier,
    ImapVerifier,
    MailpitVerifier,
    SlackVerifier,
)

DEFAULT_SANDBOX_MCP_URL = "http://localhost:8765/mcp"
DEFAULT_MAILPIT_API_URL = "http://localhost:8025"

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
_FILE_VALUES = dotenv_values(_ENV_FILE) if _ENV_FILE.is_file() else {}


def _env(name: str) -> str | None:
    """A live-test variable: the environment first, then server/.env."""

    return os.environ.get(name) or _FILE_VALUES.get(name)


@dataclass(frozen=True)
class Channel:
    """One messaging channel under test: how to send, and how to count."""

    name: str
    tool_name: str
    server_setting: str  # the LLMSettings field the app reads
    server_url: str
    verifier: DeliveryVerifier

    def parameters(self, marker: str) -> dict[str, Any]:
        text = f"Live messaging test {marker}: please ignore."
        if self.tool_name == "email_send":
            return {
                "to": _env("LIVE_TEST_EMAIL_TO") or "live-test@example.org",
                "subject": f"[{marker}] live messaging test",
                "body": text,
            }
        return {"channel": _env("SLACK_TEST_CHANNEL_ID"), "text": text}


def _reachable(url: str) -> bool:
    parsed = urlparse(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((parsed.hostname or "localhost", port), timeout=2):
            return True
    except OSError:
        return False


def _require(url: str, what: str) -> None:
    if not _reachable(url):
        pytest.fail(
            f"{what} isn't reachable at {url}. Start the sandbox with: docker compose -f "
            "docker/development/docker-compose-messaging-test.yml --profile messaging-test "
            "up -d --build (see docs/messaging-live-test.md)."
        )


def _server_url(real_url: str | None) -> str:
    """The real MCP server when one is configured, else the sandbox."""

    return real_url or _env("SANDBOX_MCP_URL") or DEFAULT_SANDBOX_MCP_URL


def _email_channel() -> Channel:
    real_url = get_settings().llm.MCP_GMAIL_SERVER_URL
    imap = {key: _env(f"LIVE_TEST_IMAP_{key}") for key in ("HOST", "USER", "PASSWORD")}

    if all(imap.values()):
        verifier: DeliveryVerifier = ImapVerifier(
            host=imap["HOST"] or "",
            user=imap["USER"] or "",
            password=imap["PASSWORD"] or "",
            mailbox=_env("LIVE_TEST_IMAP_MAILBOX") or "INBOX",
        )
    elif real_url:
        pytest.skip(
            "MCP_GMAIL_SERVER_URL points at a real server, but LIVE_TEST_IMAP_HOST/USER/"
            "PASSWORD aren't set, so delivery can't be checked."
        )
    else:
        api_url = _env("MAILPIT_API_URL") or DEFAULT_MAILPIT_API_URL
        _require(api_url, "Mailpit")
        verifier = MailpitVerifier(api_url=api_url)

    server_url = _server_url(real_url)
    _require(server_url, "The email MCP server")
    return Channel("email", "email_send", "MCP_GMAIL_SERVER_URL", server_url, verifier)


def _slack_channel() -> Channel:
    token = _env("SLACK_TEST_BOT_TOKEN")
    channel_id = _env("SLACK_TEST_CHANNEL_ID")
    if not token or not channel_id:
        pytest.skip("SLACK_TEST_BOT_TOKEN and SLACK_TEST_CHANNEL_ID aren't set.")
    assert token is not None and channel_id is not None  # narrowed for mypy

    real_url = get_settings().llm.MCP_SLACK_SERVER_URL
    server_url = _server_url(real_url)
    _require(server_url, "The Slack MCP server")
    return Channel(
        "slack",
        "slack_post",
        "MCP_SLACK_SERVER_URL",
        server_url,
        SlackVerifier(token=token, channel_id=channel_id),
    )


@pytest.fixture(params=["email", "slack"])
def channel(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Channel:
    """
    The channel under test, with the app pointed at its MCP server. Must
    be requested before e2e_client: the app builds its MCP registry from
    these settings at startup.
    """

    selected = _email_channel() if request.param == "email" else _slack_channel()
    monkeypatch.setattr(get_settings().llm, selected.server_setting, selected.server_url)
    return selected
