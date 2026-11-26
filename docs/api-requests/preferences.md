# Preferences, titles, integrations, API keys, account (proposed)

Client defaults are local except where noted.

## Preferences — `GET/PUT /preferences`

```json
{
  "timezone": "Asia/Kolkata",
  "language": "en",
  "avatarDataUrl": null,
  "notifications": { "product": true, "approvals": true }
}
```

Avatar upload should be a dedicated multipart route, not a data URL.

## Conversation titles

`PATCH /conversations/{id}` with `{ title }` exists in OpenAPI as a schema but has **no route**. The client stores overrides locally (`NEXT_PUBLIC_FEATURE_CONVERSATION_TITLES_BACKEND=local`).

## Integrations — `GET /integrations`, `PATCH /integrations/{id}` `{ enabled }`

MCP connector registry. Not on FastAPI.

## API keys — `GET/POST /api-keys`, `DELETE /api-keys/{id}`

Create response includes `secret` once.

## Account

`DELETE /users/{id}` for account deletion. Session/device list is not specified. Password change is not specified (email/password login only).
