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
- The resumed answer is added to the conversation as a new assistant
  message (fetch it with `GET /conversations/{conversation_id}`); it is
  not part of this response. `resume_status` reports how resuming went:
  `completed`, or `failed` if the conversation could not be resumed. A
  failed resume still returns `200` with the decision's status. The
  approval can't be decided again; retry the resume with
  `POST /approvals/{approval_id}/resume`.
- An approval can be decided only while its status is `waiting` and
  before `expires_at` (15 minutes after creation). Otherwise the request
  fails with `410` (expired) or `409` (already decided).

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
`resume_status` is `completed` or `failed`. (The enum also has
`not_resumed`, which these endpoints no longer return, since every
decision now resumes.)

#### Approval Status Codes

| Status | Description |
| :----: | ----------- |
| `200`  | Decision saved; `resume_status` gives the resume outcome |
| `401`  | Missing, invalid or expired bearer token (`{"detail": ...}`) |
| `403`  | The caller is not the user who requested this approval (error code `FORBIDDEN`), or the caller's account is inactive (`{"detail": ...}`) |
| `404`  | No approval with this ID (error code `APPROVAL_NOT_FOUND`) |
| `409`  | The approval has already been decided (error code `APPROVAL_ALREADY_DECIDED`) |
| `410`  | The approval has expired (error code `APPROVAL_EXPIRED`) |
| `422`  | Invalid body: unknown `decision` value or an unrecognized field |

Ownership is checked first: a caller who isn't the requester receives
`403` whatever the approval's state.

#### Retry a Resume

`POST /approvals/{approval_id}/resume` (no body) retries the resume of an
approval that was decided but whose conversation never continued: the
resume failed (`resume_status` was `failed`), or the server stopped
before it finished. It is never retried automatically.

- Only the approval's requester may call it.
- The call is sent at most once. If an earlier attempt already ran the
  approved call, successfully or not, its stored result is reused and
  nothing is sent again. The permission check described above applies
  only when the call hasn't run yet.
- It works after `expires_at`; the expiry applies only to deciding.
- The response has the same shape as the decision response, with the
  approval's current `status` and the retry's `resume_status`.

| Status | Description |
| :----: | ----------- |
| `200`  | Resume retried; `resume_status` gives the outcome |
| `401`  | Missing, invalid or expired bearer token (`{"detail": ...}`) |
| `403`  | The caller is not the user who requested this approval (error code `FORBIDDEN`), or the caller's account is inactive |
| `404`  | No approval with this ID (error code `APPROVAL_NOT_FOUND`) |
| `409`  | The approval hasn't been decided yet, or its resume already finished (error code `APPROVAL_RESUME_NOT_ALLOWED`) |

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
| `422`  | Request validation failed      |
| `429`  | Rate limit exceeded            |
| `500`  | Internal server error          |
| `502`  | LLM provider error             |
| `504`  | LLM provider timeout           |

---

For complete request and response schemas, visit the interactive API documentation:

**http://localhost:8001/docs**
