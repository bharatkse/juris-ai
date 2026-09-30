# Slack test workspace setup

## 1. Purpose

The live messaging suite (`make test-live-messaging`, see
[messaging-live-test.md](messaging-live-test.md)) posts real Slack messages and
reads them back. It needs a Slack workspace, a bot and a channel of its own. This
guide sets those up for free in about ten minutes. Use them only for these tests.
**Never use a real company workspace**: the suite posts test messages, and the
bot's token can read channel history.

## 2. Create a free workspace

1. Go to <https://slack.com/get-started> and create a new workspace.
2. Name it something like `juris-ai-test`.

## 3. Create the app from a manifest

A manifest sets the bot and its permissions in one step.

1. Go to <https://api.slack.com/apps> → **Create New App** → **From a manifest**.
2. Pick the test workspace.
3. Choose YAML and paste:

   ```yaml
   display_information:
     name: juris-ai-test-bot
   features:
     bot_user:
       display_name: juris-ai-test-bot
       always_online: false
   oauth_config:
     scopes:
       bot:
         - chat:write
         - channels:history
         - channels:read
   settings:
     org_deploy_enabled: false
     socket_mode_enabled: false
     token_rotation_enabled: false
   ```

4. Click **Next**, then **Create**.

What each scope is for:

| Scope | Used to |
|---|---|
| `chat:write` | Post the test messages |
| `channels:history` | Read the channel back, to count the messages the tests sent |
| `channels:read` | Look up the channel's details (`make slack-test-check`) |

## 4. Install the app and copy the token

1. In the app's settings, open **Install App** and click **Install to Workspace**,
   then **Allow**.
2. Open **OAuth & Permissions** and copy the **Bot User OAuth Token**. It starts
   with `xoxb-`.

## 5. Create the test channel and invite the bot

1. In the workspace, create a **public** channel, e.g. `#juris-ai-live-test`.
2. In that channel, run:

   ```text
   /invite @juris-ai-test-bot
   ```

## 6. Get the channel ID

Click the channel name at the top of the channel. The ID is at the bottom of the
**About** panel and starts with `C`, e.g. `C0123456789`.

Alternatively, right-click the channel in the sidebar → **Copy link**. The ID is
the last part of the link.

## 7. Set the variables

Either export them in the shell you run the tests from:

```bash
export SLACK_TEST_BOT_TOKEN=xoxb-...        # Bot User OAuth Token
export SLACK_TEST_CHANNEL_ID=C0123456789    # channel details, bottom of the About panel
```

or add the same two lines, without `export`, to `server/.env`. That file is
gitignored. An exported variable wins over `server/.env`.

**Never commit the token**, and don't paste it into issues, pull requests or chat.

## 8. Check the setup

From the repository root:

```bash
make slack-test-check
```

It checks the token, finds the channel and posts one message tagged
`[juris-ai setup check]`. Expected output:

```text
Token xoxb-…abcd, channel C0123456789
✅ Token works: bot juris-ai-test-bot in workspace juris-ai-test.
✅ Channel found: #juris-ai-live-test.
✅ test message posted to #juris-ai-live-test.
Slack test setup is ready: run make test-live-messaging.
```

A failed step prints ❌ with Slack's error code and what to do about it. The
[troubleshooting table](#10-troubleshooting) has the same fixes. The token is
never printed, only its first and last characters.

## 9. Run the live tests

Start (or restart) the sandbox so it picks up the token, then run the suite:

```bash
docker compose --env-file server/.env \
  -f docker/development/docker-compose-messaging-test.yml \
  --profile messaging-test up -d --build
make test-live-messaging    # expect 10 passed
```

`--env-file server/.env` lets the sandbox read the token from `server/.env`. An
exported `SLACK_TEST_BOT_TOKEN` takes precedence.

## 10. Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `invalid_auth` / `not_authed` | Wrong or old token | Re-copy the `xoxb-` token from **OAuth & Permissions** |
| `missing_scope` | A scope was added after the app was installed | Reinstall the app (**Install App** → **Reinstall to Workspace**) |
| `not_in_channel` | The bot wasn't invited | Run `/invite @juris-ai-test-bot` in the channel |
| `channel_not_found` | Wrong ID, or a private channel | Use a public channel and re-check the ID (starts with `C`) |
| Slack tests skipped | The variables aren't set in the shell running the tests (or in `server/.env`) | Export them in the same shell, or add them to `server/.env` |
| Slack tests fail with "Slack is not configured" | The sandbox container started before the token was set | Restart it with the `up -d --build` command in step 9 |

## 11. Cleanup and security

- **Revoke the token:** in the app's settings, **OAuth & Permissions** →
  **Revoke All OAuth Tokens**. Reinstall the app to get a new one.
- **Delete the app:** **Basic Information** → **Delete App**.
- **Rotate the token** (revoke it, then reinstall) if it was ever shared, committed,
  or shown in a log.
- The whole test workspace can be deleted from its workspace settings when you no
  longer need it.
