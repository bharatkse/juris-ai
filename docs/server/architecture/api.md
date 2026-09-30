# API Reference

---

## API Endpoints

**Base URL:** `http://localhost:8001/api/v1`

**Interactive Documentation:** `http://localhost:8001/docs`

**Authentication:** endpoints marked as requiring a bearer token expect
`Authorization: Bearer <access_token>`, using the token returned by
[`POST /auth/login`](#authentication). A missing, invalid or expired
token returns `401`; an inactive account returns `403`.

---

### Root

Served at the application root, outside the `/api/v1` base URL. No
authentication.

| Method | Endpoint                       | Description                              |
| :----: | ------------------------------ | ---------------------------------------- |
| `GET`  | `/` (`http://localhost:8001/`) | Application name, version and entry points |

```json
{
  "success": true,
  "data": {
    "name": "Juris AI",
    "version": "0.1.0",
    "environment": "development",
    "docs": "/docs",
    "health": "/api/v1/health"
  },
  "metadata": {
    "timestamp": "2026-09-23T15:09:42.904434Z"
  }
}
```

`docs` is `null` when interactive documentation is disabled.

---

### Health

| Method | Endpoint  | Description                     |
| :----: | --------- | ------------------------------- |
| `GET`  | `/health` | Check application health status |

---

### Authentication

| Method | Endpoint             | Description                                  | Bearer token |
| :----: | -------------------- | -------------------------------------------- | :----------: |
| `POST` | `/auth/login`        | Exchange email and password for an access token |      ❌      |
| `POST` | `/auth/access-token` | Exchange a refresh token for a new access token |      ❌      |
| `POST` | `/auth/logout`       | Log out the current client                    |      ✅      |

#### Login

Form-encoded (`application/x-www-form-urlencoded`, OAuth2 password form):
`username` (the account's email) and `password`, both required.

```bash
curl -X POST "http://localhost:8001/api/v1/auth/login" \
  -d "username=user@example.com" \
  -d "password=<password>"
```

Returns the token object directly (not wrapped in the `success`/`data`
envelope):

```json
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

`expires_in` is in seconds (default 60 minutes). Status codes: `200`
authenticated; `401` invalid email or password (`{"detail": "Invalid email or password"}`);
`403` inactive account; `422` missing form field.

#### Access Token (refresh)

JSON body `{"refresh_token": "<JWT>"}`. The token must be a JWT of type
`refresh` for an active user; the response is the standard envelope with
`data: {"access_token": ..., "token_type": "bearer", "expires_in": ...}`.
`/auth/login` returns an access token only; refresh tokens are not issued
by this API. Status codes: `200`; `401` invalid or non-refresh token
(`{"detail": "Invalid refresh token"}` / `{"detail": "Invalid token type"}`);
`422` missing `refresh_token`.

#### Logout

No body. Returns
`{"success": true, "data": {"message": "Successfully logged out"}, "message": "Logout successful.", ...}`.
Access tokens are stateless JWTs and are not revoked server-side: the
client discards its token, which otherwise remains valid until it
expires.

---

### Users

| Method  | Endpoint           | Description           |
| :-----: | ------------------ | --------------------- |
| `POST`  | `/users`           | Create a new user     |
|  `GET`  | `/users/{user_id}` | Retrieve user details |
| `PATCH` | `/users/{user_id}` | Update user profile   |

`POST /users` (registration) needs no authentication and returns `201`.
`GET` and `PATCH /users/{user_id}` need a bearer access token (`401`
without one) and act only on the caller's own profile: any other
`user_id` returns `403 FORBIDDEN`, whether or not that user exists.

#### User ID Format

```text
user_<32-character hexadecimal UUID>

Example:
user_f2b2d0f2e6ea4db39e23d8a24b61c74d
```

---

### Conversations

Requires a bearer token. Every route acts only on the caller's own
conversations.

|  Method  | Endpoint                                  | Description                                                  |
| :------: | ------------------------------------------ | -------------------------------------------------------------- |
|  `POST`  | `/conversations`                          | Create a new conversation (`201`)                              |
|  `GET`   | `/conversations`                          | List the caller's conversations (paginated)                    |
|  `GET`   | `/conversations/{conversation_id}`        | Retrieve a conversation                                        |
|  `GET`   | `/conversations/{conversation_id}/messages` | List the conversation's stored messages, oldest first (paginated) |
| `DELETE` | `/conversations/{conversation_id}`        | Archive a conversation (`204`)                                  |
|  `PUT`   | `/conversations/{conversation_id}/memory` | Turn "don't remember this" on or off for this conversation (see [Memory](#memory)) |

#### Conversation ID Format

```text
conv_<32-character hexadecimal UUID>

Example:
conv_0c72a842cf344d52a3dc0a0b9894d7a2
```

#### List Conversations

Query parameters: `offset` (integer, default `0`) and `limit` (integer,
default `20`); a non-integer value returns `422`.

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "conv_8d097a58c1c9440e981312e7b58d7f61",
        "user_id": "user_ad2eda45ada34138a42af245e7d05af9",
        "title": "Doc check",
        "is_active": true,
        "memory_disabled": false,
        "created_at": "2026-09-23T15:09:42.834255Z",
        "updated_at": "2026-09-23T15:09:42.834257Z"
      }
    ],
    "pagination": {
      "total": 1,
      "offset": 0,
      "limit": 20,
      "has_more": false
    }
  },
  "metadata": {
    "timestamp": "2026-09-23T15:09:42.853182Z"
  }
}
```

#### Conversation Messages

`GET /conversations/{conversation_id}/messages` returns the messages
stored in a conversation, oldest first: each user message and each
assistant answer, including an answer saved after an approval was
decided (see [Approvals](#approvals)).

Query parameters: `offset` (integer, default `0`, at least `0`) and
`limit` (integer, default `20`, `1` to `100`); a value outside these
returns `422`. The same ownership check as
`GET /conversations/{conversation_id}` applies: another user's
conversation returns `404`, and an archived one fails the same way it
does there.

Each item:

| Field             | Description |
| ----------------- | ----------- |
| `id`              | Message ID (`evnt_...`) |
| `conversation_id` | The conversation |
| `parent_event_id` | The user message an answer replies to. An answer saved after an approval points to the same user message as the reply that asked for the approval. Absent for a user message |
| `role`            | `user` or `assistant` |
| `content`         | The message text |
| `metadata`        | What was stored with the message: `{}` for a user message. An answer carries the turn's `agents`, `workflow`, `termination_reason`, `groundedness` and `relevance`, plus `approval` when it asked for one and `guardrail` when a guardrail acted. An answer saved after an approval carries `resumed_agent_action_id` instead, plus `approval` if it asked for another one |
| `citations`       | Citations stored with an answer (same shape as in the chat response); `[]` when none |
| `sources`         | Sources stored with an answer (same shape as in the chat response); `[]` when none |
| `created_at`      | When the message was saved |

As in every response, a field with no value is left out rather than sent
as `null`.

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "evnt_3f1c0d8e2b8a4a57b0c2a1e9d4f6b7c8",
        "conversation_id": "conv_8d097a58c1c9440e981312e7b58d7f61",
        "role": "user",
        "content": "What is an FIR?",
        "metadata": {},
        "citations": [],
        "sources": [],
        "created_at": "2026-09-29T10:02:11.402117Z"
      },
      {
        "id": "evnt_9a4e2c7d1f0b4c3e8d5a6b7c8d9e0f1a",
        "conversation_id": "conv_8d097a58c1c9440e981312e7b58d7f61",
        "parent_event_id": "evnt_3f1c0d8e2b8a4a57b0c2a1e9d4f6b7c8",
        "role": "assistant",
        "content": "An FIR (First Information Report) is ...",
        "metadata": {
          "agents": ["legal"],
          "termination_reason": "completed"
        },
        "citations": [
          {
            "title": "Code of Criminal Procedure, 1973",
            "source": "retriever",
            "reference": "Section 154",
            "snippet": "Every information relating to the commission of a cognizable offence ..."
          }
        ],
        "sources": [],
        "created_at": "2026-09-29T10:02:15.918554Z"
      }
    ],
    "pagination": {
      "total": 2,
      "offset": 0,
      "limit": 20,
      "has_more": false
    }
  },
  "metadata": {
    "timestamp": "2026-09-29T10:04:02.117308Z"
  }
}
```

Messages don't carry token usage or `resume_status`: usage is recorded
per user per day, and `resume_status` belongs to the approval.

---

### Chat

Requires a bearer token. Both endpoints take `multipart/form-data`.

| Method | Endpoint       | Description                                           |
| :----: | -------------- | ----------------------------------------------------- |
| `POST` | `/chat`        | Generate a complete AI response                       |
| `POST` | `/chat/stream` | Stream the AI response using Server-Sent Events (SSE) |

#### Chat Request

| Field           | Type                        | Required |
| --------------- | --------------------------- | :------: |
| conversation_id | Conversation ID             |    ✅    |
| message         | string                      |    ✅    |
| files           | file (repeat for several)   |    ❌    |

#### Chat Limits

- **Uploads:** at most 5 files per message (`UPLOAD_MAX_FILES`) and
  10 MB per file (`UPLOAD_MAX_FILE_BYTES`), each of a type the server can
  read: PDF (`application/pdf`), DOCX
  (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`),
  plain text (`text/plain`) or Markdown (`text/markdown`), as declared in
  the part's `Content-Type` (parameters such as `; charset=utf-8` are
  ignored). Otherwise the request fails before any file is read: `422`
  `TOO_MANY_UPLOADS`, `422` `UPLOAD_UNSUPPORTED_TYPE` naming the file and
  its type, or `413` `UPLOAD_TOO_LARGE` naming the file. Each file's
  extracted text is also cut to 20,000 characters before the model sees
  it.
- **Requests and tokens:** `429` `RATE_LIMIT_EXCEEDED` past
  `RATE_LIMIT_REQUESTS_PER_MINUTE`, and `429` `TOKEN_QUOTA_EXCEEDED` once
  the day's tokens reach `TOKEN_QUOTA_DAILY` (default 2,000,000; resets
  at midnight UTC). Every LLM call a turn makes counts: planner, agents,
  answer checks and guardrail judge, including a turn resumed after an
  approval. The quota is checked before a turn, so the turn that crosses
  it still completes.
- **Tokens per request:** one request may use at most
  `TOKEN_QUOTA_PER_REQUEST` tokens (default 100,000). Each LLM call
  is checked before it is made, against the tokens the request has used
  so far plus the call's estimated prompt; a call that would cross the
  limit isn't made and the request fails with `413`
  `REQUEST_TOKEN_QUOTA_EXCEEDED` (on `/chat/stream`, a final `error`
  event; see below). Nothing from the request is saved, but the tokens
  its earlier calls used count toward the daily quota. The last call's
  output can take the total slightly past the limit. Not applied to a
  turn resumed after an approval.
- **Tokens of a failed request** count too: a request that fails, is
  refused, or is abandoned (a client disconnecting from `/chat/stream`)
  still adds the tokens its LLM calls used to the daily quota, once per
  request.
- **Planning time:** planning runs on the local model first. If it
  doesn't finish within `PLANNER_TIMEOUT_S` (default 45 s) or fails, the
  plan is asked once of `PLANNER_FAILOVER_PROVIDER` (default Groq) within
  the rest of the request's time budget. If either call runs out of time,
  or too little time is left for the second, the request fails with `504`
  `PLANNING_TIMEOUT`. If both calls fail with a provider error before
  that, it fails with `503` `PLANNING_UNAVAILABLE` and a `Retry-After`
  header (`PLANNER_UNAVAILABLE_RETRY_AFTER_S`, default 30 s; also in
  `error.details.retry_after_seconds`). On `/chat/stream` either is a
  final `error` event. Nothing is run. Planning time counts toward the
  request's overall time budget.
- **Plan size:** a request whose plan needs more than 6 steps
  (`PLAN_MAX_STEPS`) isn't run. The answer (`200`) says how many steps it
  would need and asks the user to split it into smaller questions.

### Streaming CURL Request

```
curl -N \
  -X POST "http://localhost:8001/api/v1/chat/stream" \
  -H "Authorization: Bearer <access_token>" \
  -H "Accept: text/event-stream" \
  -F "conversation_id=conv_23833e202e934590bb1306c518518aad" \
  -F "message=Explain Article 21 of the Constitution of India."
```

#### Streaming Response

The `/chat/stream` endpoint returns a `text/event-stream` response. Each
event is named `message`, except the last, which is named `complete`
(`is_final: true`).

Errors found before the stream starts (authentication, rate limits, the
daily quota, upload limits) are normal error responses. An application
error raised after it has started, such as `REQUEST_TOKEN_QUOTA_EXCEEDED`,
ends the stream with a single `error` event instead of `complete`; its
`data` is the same `code`, `message` and (when present) `details` as an
error response's `error` object. A stream can't send headers, so a
`Retry-After` value is read from `details.retry_after_seconds`:

```text
event: error
data: {"code":"REQUEST_TOKEN_QUOTA_EXCEEDED","message":"This request needs more than the 100000 tokens one request may use (99100 used, about 2013 more needed). Try a shorter message or fewer attachments."}
```

Each event's `data` has the following structure:

```json
{
  "content": "Article",
  "is_final": false,
  "metadata": {}
}
```

Example stream:

```text
event: message
data: {"content":"Article","is_final":false,"metadata":{}}

event: message
data: {"content":" 21","is_final":false,"metadata":{}}

event: message
data: {"content":" guarantees","is_final":false,"metadata":{}}

event: complete
data: {"content":".","is_final":true,"metadata":{}}
```

---

### Memory

Durable, per-user facts (preferences, professional-profile details) that
persist across conversations. Off by default; every route acts only on
the authenticated caller's own memories. See
[`docs/server/architecture/user-memory.md`](user-memory.md) for the
full design, consent, and retention model.

|  Method  | Endpoint               | Description                        |
| :------: | ----------------------- | ----------------------------------- |
|  `GET`   | `/memory/settings`      | Get the long-term memory setting   |
|  `PUT`   | `/memory/settings`      | Turn long-term memory on or off    |
|  `GET`   | `/memory/items`         | List saved memories (paginated)    |
|  `GET`   | `/memory/items/{memory_id}` | Retrieve a saved memory        |
| `DELETE` | `/memory/items/{memory_id}` | Delete a saved memory          |

#### Memory ID Format

```text
umem_<32-character hexadecimal UUID>

Example:
umem_3a2c9e8f1b7d4a5c9e0f2b8d6a4c1e7d
```

---

### Approvals

Human decisions on agent actions that paused for approval: calls to the
send tools `email_send` and `slack_post`. The read tools `email` and
`slack` never pause. Requires a bearer token. Only the user who made
the request that produced an approval can decide it or retry its resume.

| Method | Endpoint                          | Description                                          |
| :----: | --------------------------------- | ---------------------------------------------------- |
| `POST` | `/approvals/{approval_id}`        | Approve, reject or edit a pending approval           |
| `POST` | `/approvals/{approval_id}/resume` | Retry resuming a decided approval that didn't finish |

#### Approval ID Format

```text
appr_<32-character hexadecimal UUID>

Example:
appr_474554ac1f5d410aaf7ca7da84a9f9a5
```

The ID is returned in the assistant event's metadata (`approval.approval_id`)
of the chat response that paused. That response's text is: "This needs
your approval before I can continue. Review the pending request to
approve, edit or reject it."

#### Behaviour

- The decision is saved before anything acts on it, and it stands
  whatever happens next.
- Every decision resumes the paused conversation:
  - `approve`: the proposed call runs once, with the proposed
    parameters.
  - `edit`: the call runs once, with `edited_payload` merged over the
    proposed parameters (fields you leave out keep their proposed
    values). The status becomes `edited`.
  - `reject`: nothing runs; the agent is told the request was refused.
- Before an approved or edited call runs, the user's current role is
  checked again. If the role no longer allows the action, for example
  because the user was moved from `member` to `reader` after the request,
  the call doesn't run and the agent is told it was refused.
- The resumed answer is saved to the conversation as a new assistant
  message; it is not part of this response. Fetch it with
  `GET /conversations/{conversation_id}/messages` (see
  [Conversation Messages](#conversation-messages)). `resume_status`
  reports how resuming went:
  `completed`, or `failed` if the conversation could not be resumed. A
  failed resume still returns `200` with the decision's status. The
  approval can't be decided again; retry the resume with
  `POST /approvals/{approval_id}/resume`.
- An approval can be decided only while its status is `waiting` and
  before `expires_at` (15 minutes after creation). Otherwise the request
  fails with `410` (expired) or `409` (already decided).
- Only one decision is ever recorded. If two decisions arrive at once
  (for example `approve` and `reject` from two tabs), the first one saved
  wins; the other gets `409` and changes nothing. Its error `details`
  give the status the approval now has, e.g.
  `{"current_status": "rejected"}`. Only a recorded `approve` or `edit`
  runs the call.

#### Approval Response (`200`)

```json
{
  "success": true,
  "data": {
    "approval_id": "appr_474554ac1f5d410aaf7ca7da84a9f9a5",
    "agent_action_id": "actn_74fbcaf24390474bb4165a0555741ab5",
    "requested_by": "user_7be4edf3a8e14087b68447e5ace7e3f8",
    "status": "approved",
    "created_at": "2026-09-23T14:21:09.672912Z",
    "expires_at": "2026-09-23T14:36:09.668924Z",
    "resume_status": "completed"
  },
  "metadata": {
    "timestamp": "2026-09-23T14:21:09.871769Z"
  }
}
```

`status` is one of `waiting`, `approved`, `rejected`, `edited`, `expired`.
`resume_status` is `completed`, `failed`, or `in_progress` when another
request is already resuming the same approval (only one request ever
runs the approved call). (The enum also has `not_resumed`, which these
endpoints no longer return, since every decision now resumes.)

#### Approval Status Codes

| Status | Description |
| :----: | ----------- |
| `200`  | Decision saved; `resume_status` gives the resume outcome |
| `401`  | Missing, invalid or expired bearer token (`{"detail": ...}`) |
| `403`  | The caller is not the user who requested this approval (error code `FORBIDDEN`), or the caller's account is inactive (`{"detail": ...}`) |
| `404`  | No approval with this ID (error code `APPROVAL_NOT_FOUND`) |
| `409`  | The approval has already been decided (error code `APPROVAL_ALREADY_DECIDED`; `details.current_status` gives its status) |
| `410`  | The approval has expired (error code `APPROVAL_EXPIRED`) |
| `422`  | Invalid body: unknown `decision` value or an unrecognized field |

Ownership is checked first: a caller who isn't the requester receives
`403` whatever the approval's state.

#### Retry a Resume

`POST /approvals/{approval_id}/resume` (no body; optional query
parameter `force`) retries the resume of an
approval that was decided but whose conversation never continued: the
resume failed (`resume_status` was `failed`), or the server stopped
before it finished. It is never retried automatically.

- Only the approval's requester may call it.
- The call is sent at most once. If an earlier attempt already ran the
  approved call, successfully or not, its stored result is reused and
  nothing is sent again. The permission check described above applies
  only when the call hasn't run yet.
- It works after `expires_at`; the expiry applies only to deciding.
- Only one request resumes an approval at a time. While another request
  is resuming it, the retry is refused with `409`, with or without
  `force`. A resume that stopped without finishing (for example, the
  server restarted) can be retried once `HITL_RESUME_STALE_SECONDS`
  (default 600) have passed without progress. If the approved call's
  outcome was already stored, it is reused and nothing is sent again.
- If it stopped while sending and no outcome was recorded, the message
  may or may not have gone out. The retry is then refused with `409`
  `APPROVAL_RESUME_NEEDS_CONFIRMATION` and `details`
  `{"possibly_sent": true}`. Check whether the message arrived; to send
  it anyway, retry with `?force=true`. It is then sent once more.
- The response has the same shape as the decision response, with the
  approval's current `status` and the retry's `resume_status`.

| Status | Description |
| :----: | ----------- |
| `200`  | Resume retried; `resume_status` gives the outcome |
| `401`  | Missing, invalid or expired bearer token (`{"detail": ...}`) |
| `403`  | The caller is not the user who requested this approval (error code `FORBIDDEN`), or the caller's account is inactive |
| `404`  | No approval with this ID (error code `APPROVAL_NOT_FOUND`) |
| `409`  | The approval hasn't been decided yet, its resume already finished, or another request is resuming it (error code `APPROVAL_RESUME_NOT_ALLOWED`) |
| `409`  | The send may already have gone out and needs `force=true` to retry (error code `APPROVAL_RESUME_NEEDS_CONFIRMATION`, `details.possibly_sent: true`) |

Error responses from the application use the standard envelope:

```json
{
  "success": false,
  "error": {
    "code": "FORBIDDEN",
    "message": "Not permitted to act on this approval request."
  },
  "metadata": {
    "timestamp": "2026-09-23T14:21:09.871769Z"
  }
}
```

Some errors add a `details` object with structured fields, such as the
approval's `current_status` on a `409`; it is omitted when there are none.

---

## Request Models

### Create User

| Field            | Type                          | Required |
| ---------------- | ----------------------------- | :------: |
| email            | Email                         |    ✅    |
| password         | string                        |    ✅    |
| confirm_password | string                        |    ✅    |
| first_name       | string                        |    ❌    |
| last_name        | string                        |    ❌    |
| gender           | `male` \| `female` \| `other` |    ❌    |
| phone_number     | string                        |    ❌    |
| date_of_birth    | date                          |    ❌    |

Unrecognized fields are rejected (`422`).

---

### Update User

| Field         | Type                          | Required |
| ------------- | ----------------------------- | :------: |
| first_name    | string                        |    ❌    |
| last_name     | string                        |    ❌    |
| gender        | `male` \| `female` \| `other` |    ❌    |
| phone_number  | string                        |    ❌    |
| date_of_birth | date                          |    ❌    |

Unrecognized fields are rejected (`422`).

---

### Create Conversation

| Field | Type   | Required |
| ----- | ------ | :------: |
| title | string |    ❌    |

The conversation belongs to the authenticated caller. The body may be
empty (`{}`); unrecognized fields are rejected (`422`).

---

### Chat Request

`multipart/form-data`.

| Field           | Type                      | Required |
| --------------- | ------------------------- | :------: |
| conversation_id | Conversation ID           |    ✅    |
| message         | string                    |    ✅    |
| files           | file (repeat for several) |    ❌    |

---

### Update Memory Settings

| Field   | Type    | Required |
| ------- | ------- | :------: |
| enabled | boolean |    ✅    |

`true`: allow saving durable facts and using them in later
conversations. `false`: stop, and permanently delete every memory
saved so far — this cannot be undone.

---

### Update Conversation Memory

| Field           | Type    | Required |
| ---------------- | ------- | :------: |
| memory_disabled | boolean |    ✅    |

Forward-only. `true` stops anything said in this conversation from
being saved to long-term memory from now on; it does **not** delete
facts already saved from earlier messages in it.

---

### Approval Decision

| Field           | Type                         | Required |
| --------------- | ---------------------------- | :------: |
| decision        | `approve` \| `reject` \| `edit` |    ✅    |
| edited_payload  | object                       |    ❌    |
| decision_reason | string                       |    ❌    |

`edited_payload` is used with `edit`. Unrecognized fields are rejected
(`422`).

---

## Response Codes

| Status | Description                    |
| :----: | ------------------------------ |
| `200`  | Request completed successfully |
| `201`  | Resource created successfully  |
| `204`  | Resource archived successfully |
| `400`  | Invalid request                |
| `401`  | Missing, invalid or expired bearer token (every endpoint that requires one) |
| `403`  | Authenticated but not permitted (inactive account, or deciding another user's approval) |
| `404`  | Resource not found             |
| `409`  | Conflict with the resource's current state (e.g. an approval already decided) |
| `410`  | Resource no longer available (e.g. an expired approval) |
| `413`  | An uploaded file is over the size limit (`UPLOAD_TOO_LARGE`), or the request would use more tokens than one request may (`REQUEST_TOKEN_QUOTA_EXCEEDED`) |
| `422`  | Request validation failed, too many files uploaded (`TOO_MANY_UPLOADS`), or a file of an unsupported type (`UPLOAD_UNSUPPORTED_TYPE`) |
| `429`  | Request rate limit or daily token quota exceeded |
| `500`  | Internal server error          |
| `502`  | LLM provider error             |
| `503`  | Planning unavailable: every planner provider failed (`PLANNING_UNAVAILABLE`); retry after the `Retry-After` header |
| `504`  | LLM provider timeout, or planning didn't finish in time (`PLANNING_TIMEOUT`) |

---

For complete request and response schemas, visit the interactive API documentation:

**http://localhost:8001/docs**
