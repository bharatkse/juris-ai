# Live messaging tests

The `email_send` and `slack_post` tools send only after a person approves the
draft. The unit and e2e suites check that flow with the outbound call replaced.
The live suite (`server/tests/e2e/live_messaging/`) runs the same flow through
real delivery, so run it with real accounts before turning on
`ENABLE_MESSAGING_TOOLS`.

What is real: the approval API, the resume service, the gated tool and its
approval check, the application's MCP client, and delivery by the MCP server.
What is scripted: only the LLM calls (planning, the agent's reasoning, the
answer check), so the agent reliably proposes the send.

Each test puts a unique marker (`jlt-…`) in the subject or text and counts only
messages that contain it, so runs don't interfere with each other or with other
mail in the inbox or channel.

The tests are marked `live_messaging`. They are skipped unless
`RUN_LIVE_MESSAGING=1`, and always skipped in CI.

## Cases (run for email and for Slack)

| # | Case | Expected |
|---|---|---|
| 1 | Approve | Exactly one message delivered; the action is marked completed with its result stored |
| 2 | Two approvals at once | One `200` and one `409`; exactly one message |
| 3 | Approve and reject at once | One `200` and one `409`; one message if the approval won, none if the rejection won; the action's final state matches the winner |
| 4 | Retry after the message was sent | `409 APPROVAL_RESUME_NOT_ALLOWED`; no new message |
| 5 | Retry of a stale send with no recorded outcome | Without `force`: `409 APPROVAL_RESUME_NEEDS_CONFIRMATION` with `possibly_sent: true` and no new message. With `force=true`: one more message (two in total) and a WARNING logged |

Case 5 shows the one accepted duplicate: a user who confirms the retry of a send
whose outcome is unknown can receive the message twice.

## Quick start: local sandbox (email)

The sandbox needs no accounts. It runs two containers, in the `messaging-test`
compose profile only:

- **Mailpit**: a local SMTP server that keeps every message (web UI at
  <http://localhost:8025>).
- **Sandbox MCP server**: exposes the same tools and inputs the app calls on its
  mail and Slack MCP servers (`send_message`, `chat_postMessage`) at
  `http://localhost:8765/mcp`. It relays mail to Mailpit and posts to Slack with a
  test bot token.

With Postgres and Redis running (`./setup.sh --install --mode dev`), from the
repository root:

```bash
docker compose -f docker/development/docker-compose-messaging-test.yml \
  --profile messaging-test up -d --build
make test-live-messaging
```

Expected: the five email cases pass; the Slack cases are skipped until a Slack
token and channel are set.

Stop the sandbox with:

```bash
docker compose -f docker/development/docker-compose-messaging-test.yml \
  --profile messaging-test down
```

## Slack

The Slack cases need a free test workspace, a bot with the `chat:write`,
`channels:history` and `channels:read` scopes, and a public channel the bot is in.
Follow [slack-test-workspace-setup.md](slack-test-workspace-setup.md). It creates
the app from a manifest and ends with `make slack-test-check`, which verifies the
token and channel before you run the suite. Then:

```bash
docker compose --env-file server/.env \
  -f docker/development/docker-compose-messaging-test.yml \
  --profile messaging-test up -d --build
make test-live-messaging
```

Expected: all ten cases pass. Each Slack test leaves one or two messages in the
channel, each with its marker.

## Using real MCP servers

The app reads `MCP_GMAIL_SERVER_URL` and `MCP_SLACK_SERVER_URL`. The suite uses
them when they are set (in the environment or `server/.env`), and the sandbox
server when they are not. Delivery is checked by:

| Channel | Checked through | Needs |
|---|---|---|
| Email, sandbox | Mailpit's HTTP API | nothing (`MAILPIT_API_URL`, default `http://localhost:8025`) |
| Email, any server | An IMAP inbox | `LIVE_TEST_IMAP_HOST`, `LIVE_TEST_IMAP_USER`, `LIVE_TEST_IMAP_PASSWORD` (for Gmail, an app password); the mail is sent to `LIVE_TEST_EMAIL_TO` |
| Slack, any server | The channel's history | `SLACK_TEST_BOT_TOKEN`, `SLACK_TEST_CHANNEL_ID` |

When the IMAP variables are set, email is checked over IMAP, whichever server
sends it. A real mail server URL without IMAP credentials skips the email cases,
since delivery can't be checked. The Slack cases are skipped without a token and
channel.

Example: a real mail MCP server, checked over IMAP:

```bash
export MCP_GMAIL_SERVER_URL=https://mail-mcp.example.internal/mcp
export LIVE_TEST_EMAIL_TO=test-inbox@example.org
export LIVE_TEST_IMAP_HOST=imap.gmail.com
export LIVE_TEST_IMAP_USER=test-inbox@example.org
export LIVE_TEST_IMAP_PASSWORD=app-password
make test-live-messaging
```

Use a test inbox and a test workspace: the suite sends real messages.

## Settings

The test variables below are read from the environment, or else from
`server/.env` (gitignored). An exported variable wins.

| Variable | Default | Purpose |
|---|---|---|
| `RUN_LIVE_MESSAGING` | unset | `1` runs the suite (`make test-live-messaging` sets it) |
| `SANDBOX_MCP_URL` | `http://localhost:8765/mcp` | Sandbox MCP server, used when no real server URL is set |
| `MAILPIT_API_URL` | `http://localhost:8025` | Mailpit API for the sandbox email checks |
| `LIVE_TEST_EMAIL_TO` | `live-test@example.org` | Recipient of the test emails |
| `LIVE_TEST_IMAP_HOST` / `_USER` / `_PASSWORD` | unset | Check email over IMAP instead of Mailpit |
| `LIVE_TEST_IMAP_MAILBOX` | `INBOX` | IMAP folder to search |
| `SLACK_TEST_BOT_TOKEN` / `SLACK_TEST_CHANNEL_ID` | unset | Slack cases (and the sandbox's Slack posting) |
| `LIVE_TEST_TIMEOUT_S` | `20` | How long to wait for a message to arrive |
| `LIVE_TEST_SETTLE_S` | `3` | Extra wait before the final count, so a late duplicate is still caught |
