"""
scripts/slack_test_check.py (make slack-test-check): checks the Slack test
bot and channel the live messaging suite uses, with Slack's API mocked.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "slack_test_check.py"
TOKEN = "xoxb-1111-2222-SECRETSECRETabcd"
CHANNEL = "C0123456789"


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("slack_test_check", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve the module through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_OK: dict[str, dict[str, Any]] = {
    "auth.test": {"ok": True, "user": "juris-ai-test-bot", "team": "juris-ai-test"},
    "conversations.info": {"ok": True, "channel": {"id": CHANNEL, "name": "juris-ai-live-test"}},
    "chat.postMessage": {"ok": True, "ts": "1727700000.000100"},
}


def _slack(fail: dict[str, str] | None = None, posted: list[dict] | None = None):
    """A mocked Slack Web API: every method succeeds unless listed in fail."""

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        if fail and method in fail:
            body: dict[str, Any] = {"ok": False, "error": fail[method]}
            if fail[method] == "missing_scope":
                body["needed"] = "channels:read"
            return httpx.Response(200, json=body)
        if method == "chat.postMessage" and posted is not None:
            posted.append(json.loads(request.content))
        return httpx.Response(200, json=_OK[method])

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://slack.com/api")


def _run(client: httpx.Client, env: dict[str, str] | None = None) -> tuple[int, str]:
    lines: list[str] = []
    env = {"SLACK_TEST_BOT_TOKEN": TOKEN, "SLACK_TEST_CHANNEL_ID": CHANNEL} if env is None else env
    code = _script().run_check(env=env, client=client, out=lines.append)
    return code, "\n".join(lines)


def test_a_working_setup_reports_bot_workspace_channel_and_the_posted_message() -> None:
    posted: list[dict] = []

    code, output = _run(_slack(posted=posted))

    assert code == 0
    assert "juris-ai-test-bot" in output
    assert "juris-ai-test" in output
    assert "#juris-ai-live-test" in output
    assert "test message posted" in output
    assert "❌" not in output
    assert posted[0]["channel"] == CHANNEL
    assert posted[0]["text"].startswith("[juris-ai setup check]")


@pytest.mark.parametrize(
    ("method", "error", "hint"),
    [
        ("auth.test", "invalid_auth", "re-copy the Bot User OAuth Token"),
        ("auth.test", "not_authed", "re-copy the Bot User OAuth Token"),
        ("conversations.info", "missing_scope", "reinstall the app"),
        ("conversations.info", "channel_not_found", "public channel"),
        ("chat.postMessage", "not_in_channel", "/invite @juris-ai-test-bot"),
    ],
)
def test_each_slack_error_gets_its_hint_and_fails(method: str, error: str, hint: str) -> None:
    code, output = _run(_slack(fail={method: error}))

    assert code == 1
    assert "❌" in output
    assert error in output
    assert hint in output


def test_missing_scope_names_the_scope_slack_wants() -> None:
    _, output = _run(_slack(fail={"conversations.info": "missing_scope"}))

    assert "channels:read" in output


def test_a_failed_step_stops_the_check() -> None:
    posted: list[dict] = []

    code, output = _run(_slack(fail={"auth.test": "invalid_auth"}, posted=posted))

    assert code == 1
    assert posted == []
    assert "test message posted" not in output


@pytest.mark.parametrize(
    "fail", [None, {"auth.test": "invalid_auth"}, {"chat.postMessage": "not_in_channel"}]
)
def test_the_token_is_never_printed(fail: dict[str, str] | None) -> None:
    _, output = _run(_slack(fail=fail))

    assert TOKEN not in output
    assert "SECRETSECRET" not in output
    assert "xoxb-…abcd" in output


@pytest.mark.parametrize("missing", ["SLACK_TEST_BOT_TOKEN", "SLACK_TEST_CHANNEL_ID"])
def test_a_missing_variable_fails_before_calling_slack(missing: str) -> None:
    env = {"SLACK_TEST_BOT_TOKEN": TOKEN, "SLACK_TEST_CHANNEL_ID": CHANNEL}
    del env[missing]

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Slack called without both variables")

    client = httpx.Client(transport=httpx.MockTransport(unreachable))
    code, output = _run(client, env=env)

    assert code == 1
    assert missing in output


def test_a_network_error_fails_with_a_hint() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to slack.com")

    client = httpx.Client(transport=httpx.MockTransport(refuse), base_url="https://slack.com/api")
    code, output = _run(client)

    assert code == 1
    assert "network" in output.lower()


def test_variables_fall_back_to_the_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(f"SLACK_TEST_BOT_TOKEN={TOKEN}\nSLACK_TEST_CHANNEL_ID=C999\n")

    settings = _script().load_variables(
        environ={"SLACK_TEST_CHANNEL_ID": CHANNEL}, env_file=env_file
    )

    assert settings["SLACK_TEST_BOT_TOKEN"] == TOKEN
    # The environment wins over the file.
    assert settings["SLACK_TEST_CHANNEL_ID"] == CHANNEL
