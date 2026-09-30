"""
Check the Slack test bot and channel used by the live messaging suite
(make slack-test-check; docs/slack-test-workspace-setup.md).

Reads SLACK_TEST_BOT_TOKEN and SLACK_TEST_CHANNEL_ID from the environment,
or else from server/.env, then:
1. auth.test: the token works; prints the bot and workspace names.
2. conversations.info: the channel exists and the bot can see it.
3. chat.postMessage: posts one message tagged "[juris-ai setup check]".

Prints ✅/❌ per step, with Slack's error code and what to do about it,
and exits non-zero on the first failure. The token is never printed, only
masked (xoxb-…last4).

Usage (from the repository root): make slack-test-check
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values

SLACK_API = "https://slack.com/api"
TAG = "[juris-ai setup check]"
VARIABLES = ("SLACK_TEST_BOT_TOKEN", "SLACK_TEST_CHANNEL_ID")
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
GUIDE = "docs/slack-test-workspace-setup.md"

# Slack error code -> what to do (the guide's troubleshooting table).
HINTS: Mapping[str, str] = {
    "invalid_auth": "The token is wrong or old: re-copy the Bot User OAuth Token (xoxb-…) "
    "from OAuth & Permissions.",
    "not_authed": "No token reached Slack: re-copy the Bot User OAuth Token (xoxb-…) "
    "from OAuth & Permissions.",
    "token_revoked": "The token was revoked: reinstall the app and re-copy the Bot User "
    "OAuth Token.",
    "account_inactive": "The app or workspace is inactive: reinstall the app and re-copy "
    "the Bot User OAuth Token.",
    "missing_scope": "A scope was added after the app was installed: reinstall the app "
    "(Install App → Reinstall to Workspace).",
    "not_in_channel": "The bot isn't in the channel: run /invite @juris-ai-test-bot in it.",
    "channel_not_found": "Wrong channel ID, or a private channel: use a public channel and "
    "re-check the ID (it starts with C).",
    "ratelimited": "Slack is rate-limiting this app: wait a minute and try again.",
}

Out = Callable[[str], None]


class _StepFailed(Exception):
    pass


def mask_token(token: str) -> str:
    """xoxb-…last4: enough to tell tokens apart, never enough to use one."""

    return f"{token[:5]}…{token[-4:]}" if len(token) > 12 else "…"


def load_variables(
    *, environ: Mapping[str, str], env_file: Path = ENV_FILE
) -> dict[str, str | None]:
    """The two variables from the environment, else from server/.env."""

    from_file = dotenv_values(env_file) if env_file.is_file() else {}
    return {name: environ.get(name) or from_file.get(name) for name in VARIABLES}


def _call(
    client: httpx.Client,
    out: Out,
    *,
    step: str,
    method: str,
    bot: str = "juris-ai-test-bot",
    **params: Any,
) -> dict[str, Any]:
    try:
        # Form-encoded: Slack's read methods (conversations.info) don't
        # accept JSON bodies, only write methods do.
        response = client.post(f"/{method}", data=params)
        body: dict[str, Any] = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        out(f"❌ {step}: couldn't reach Slack ({type(exc).__name__}).")
        out("   Check the network connection to slack.com and try again.")
        raise _StepFailed from exc

    if not body.get("ok"):
        error = str(body.get("error", f"HTTP {response.status_code}"))
        out(f"❌ {step}: Slack returned {error}.")
        hint = HINTS.get(error, f"See https://api.slack.com/methods/{method} ({error}).")
        if error == "missing_scope" and body.get("needed"):
            hint += f" Needed scope: {body['needed']}."
        # Name the bot actually installed, not the guide's example name.
        hint = hint.replace("@juris-ai-test-bot", f"@{bot}")
        out(f"   {hint}")
        raise _StepFailed

    return body


def run_check(*, env: Mapping[str, str | None], client: httpx.Client, out: Out = print) -> int:
    missing = [name for name in VARIABLES if not env.get(name)]
    if missing:
        out(f"❌ Not set: {', '.join(missing)}.")
        out(f"   Export them, or add them to server/.env (see {GUIDE}).")
        return 1

    token = env["SLACK_TEST_BOT_TOKEN"] or ""
    channel_id = env["SLACK_TEST_CHANNEL_ID"] or ""
    client.headers["Authorization"] = f"Bearer {token}"
    out(f"Token {mask_token(token)}, channel {channel_id}")

    try:
        auth = _call(client, out, step="Token", method="auth.test")
        out(f"✅ Token works: bot {auth.get('user')} in workspace {auth.get('team')}.")

        info = _call(client, out, step="Channel", method="conversations.info", channel=channel_id)
        out(f"✅ Channel found: #{info['channel'].get('name')}.")

        stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        _call(
            client,
            out,
            step="Post",
            method="chat.postMessage",
            bot=str(auth.get("user") or "juris-ai-test-bot"),
            channel=channel_id,
            text=f"{TAG} {stamp}",
        )
        out(f"✅ test message posted to #{info['channel'].get('name')}.")
    except _StepFailed:
        out(f"Setup check failed; see the troubleshooting table in {GUIDE}.")
        return 1

    out("Slack test setup is ready: run make test-live-messaging.")
    return 0


def main() -> int:
    import os

    env = load_variables(environ=os.environ)
    with httpx.Client(base_url=SLACK_API, timeout=10) as client:
        return run_check(env=env, client=client)


if __name__ == "__main__":
    sys.exit(main())
