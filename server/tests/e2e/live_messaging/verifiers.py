"""
Count delivered messages that contain a test's unique marker.

One verifier per place a message can land: Mailpit (the sandbox SMTP
server), any IMAP inbox (a real mail provider), and a Slack channel. Each
only counts messages carrying the marker, so runs don't interfere.
"""

from __future__ import annotations

import asyncio
import imaplib
import os
import time
from typing import Protocol

import httpx

# Real providers deliver asynchronously.
TIMEOUT_SECONDS = float(os.getenv("LIVE_TEST_TIMEOUT_S", "20"))
# After the expected count is reached (or at once, when expecting none),
# wait this long and count again, so a late duplicate is still caught.
SETTLE_SECONDS = float(os.getenv("LIVE_TEST_SETTLE_S", "3"))


class DeliveryVerifier(Protocol):
    name: str

    async def count(self, marker: str) -> int: ...


class MailpitVerifier:
    name = "mailpit"

    def __init__(self, *, api_url: str) -> None:
        self._api_url = api_url.rstrip("/")

    async def count(self, marker: str) -> int:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{self._api_url}/api/v1/search", params={"query": f'"{marker}"'}
            )
        response.raise_for_status()
        return int(response.json()["messages_count"])


class ImapVerifier:
    name = "imap"

    def __init__(self, *, host: str, user: str, password: str, mailbox: str) -> None:
        self._host = host
        self._user = user
        self._password = password
        self._mailbox = mailbox

    def _count(self, marker: str) -> int:
        with imaplib.IMAP4_SSL(self._host) as imap:
            imap.login(self._user, self._password)
            imap.select(self._mailbox, readonly=True)
            status, data = imap.search(None, "SUBJECT", f'"{marker}"')
        if status != "OK":
            raise RuntimeError(f"IMAP search failed: {status}")
        return len(data[0].split())

    async def count(self, marker: str) -> int:
        return await asyncio.to_thread(self._count, marker)


class SlackVerifier:
    name = "slack"

    def __init__(self, *, token: str, channel_id: str) -> None:
        self._token = token
        self._channel_id = channel_id

    async def count(self, marker: str) -> int:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://slack.com/api/conversations.history",
                headers={"Authorization": f"Bearer {self._token}"},
                params={"channel": self._channel_id, "limit": 200},
            )
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Slack history read failed: {payload.get('error')}")
        return sum(marker in message.get("text", "") for message in payload["messages"])


async def delivered(verifier: DeliveryVerifier, marker: str, *, expected: int) -> int:
    """
    The number of messages with the marker, once it reaches ``expected``
    (or the timeout passes) and has had SETTLE_SECONDS to grow further.
    """

    deadline = time.monotonic() + TIMEOUT_SECONDS
    count = await verifier.count(marker)

    while count < expected and time.monotonic() < deadline:
        await asyncio.sleep(0.5)
        count = await verifier.count(marker)

    await asyncio.sleep(SETTLE_SECONDS)
    return await verifier.count(marker)
