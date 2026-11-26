# Web client API audit

Snapshot of FastAPI `/api/v1` vs `clients/web`. Backend was not modified.
OpenAPI snapshot: `clients/web/openapi/openapi.json`.

## A. Hardcoded / fake UI (before → after)

| File | Line (before) | What it faked | After |
|---|---|---|---|
| `features/settings/components/settings-content.tsx` | Usage card `20 / minute`, `200,000 / day` | Invented quotas; API has no usage endpoint | Removed. Hidden behind `usageDashboard` (off) |
| Same | Document library card | UI with no library/ingestion API | Removed. Hidden behind `documentLibrary` (off) |
| `features/conversations/api.ts` | `GET .../events` | Wrong path | `GET .../messages` |
| `app/api/auth/me/route.ts` | `GET /auth/me` | Route does not exist | JWT `sub` → `GET /users/{id}` |
| `features/conversations/api.ts` | `PATCH` title | Schema exists; **no PATCH route** | Hidden behind `conversationRename` (off) |
| `features/chat/files.ts` | 20 MB, HTML | API: 10 MB, pdf/docx/txt/md | Aligned with backend limits |
| `features/approvals/components/approval-card.tsx` | Approve/Reject only, leftover `gold-600` | No payload, no `edit`, no resume | Payload JSON, Edit, resume retry |
| `features/chat/starters.ts` | Starter prompts | Copy, not API data | Moved to `src/constants/copy.ts` |
| `config/server.ts` | Default `http://127.0.0.1:8001/api/v1` | Dev fallback | Zod-validated server env; default kept for local only |
| `components/{chat,settings,citations,approvals}/*` | Duplicate gold-token copies of feature modules | Dead duplicates | Deleted |

No fake conversation/document arrays, `lorem ipsum`, or `Math.random` data were found in `src/features`.

## B. Endpoint inventory

Auth: JWT bearer (except register, login, health, root). No RBAC capability endpoint. Roles are DB-backed on the server only.

| method | path | purpose | auth | request | response | stream | web used | UI |
|---|---|---|---|---|---|---|---|---|
| GET | `/` | Root ping | public | — | envelope | no | no | no (not needed) |
| GET | `/health` | Liveness | public | — | `{status,service,version,environment}` | no | yes (settings) | Settings → Service |
| POST | `/auth/login` | OAuth2 password form | public | form username/password | tokens (unwrapped) | no | yes | Login |
| POST | `/auth/logout` | Invalidate refresh | user | `{refresh_token}` | ok | no | yes (BFF) | Log out |
| POST | `/auth/access-token` | Refresh | public | `{refresh_token}` | tokens | no | yes (BFF) | transparent |
| POST | `/users` | Register | public | RegisterNewUserRequest | UserResponse | no | yes | Register |
| GET | `/users/{id}` | Profile (self only) | self | — | UserResponse | no | yes (`/api/auth/me`) | Settings profile |
| PATCH | `/users/{id}` | Update profile | self | UpdateUserProfileRequest | UserResponse | no | yes | Profile form |
| POST | `/conversations` | Create | user | `{title?}` | ConversationResponse | no | yes | Sidebar new chat |
| GET | `/conversations` | List | user | offset/limit | Page | no | yes | Sidebar |
| GET | `/conversations/{id}` | Get | owner | — | ConversationResponse | no | yes | Thread header |
| GET | `/conversations/{id}/messages` | List messages | owner | offset/limit | Page of messages (citations/sources top-level) | no | yes | Thread |
| DELETE | `/conversations/{id}` | Archive | owner | — | 204 | no | yes | Archive confirm |
| PUT | `/conversations/{id}/memory` | Don’t-remember-this | owner | `{memory_disabled}` | ConversationResponse | no | yes | Thread toggle |
| POST | `/chat` | Sync chat | user | multipart message, conversation_id, files | ChatResponse | no | yes (flag) | Composer |
| POST | `/chat/stream` | SSE chat | user | same | SSE | **yes** | yes | Composer + list |
| GET | `/memory/settings` | Memory consent | user | — | `{enabled, consent_updated_at}` | no | yes | Settings + Memory |
| PUT | `/memory/settings` | Toggle memory (off deletes all) | user | `{enabled}` | settings | no | yes | Memory |
| GET | `/memory/items` | List memories | user | offset/limit | Page | no | yes | Memory |
| GET | `/memory/items/{id}` | One memory | user | — | MemoryItem | no | yes | Memory detail |
| DELETE | `/memory/items/{id}` | Delete one | user | — | 204 | no | yes | Memory |
| POST | `/approvals/{id}` | Decide HITL | requester | `{decision, edited_payload?, decision_reason?}` | ApprovalResponse + resume_status | no | yes | Approval card |
| POST | `/approvals/{id}/resume` | Retry resume | requester | `force?` | ApprovalResponse | no | yes | Approval card |

**Not in FastAPI (no UI invented):** document library, ingestion status, RAG search, agents/plans list, GET `/approvals/{id}`, GET `/auth/me`, PATCH conversation title, usage/quotas, RBAC/capabilities, tools/MCP admin, Grafana/admin.

## C. Gap analysis

### Endpoints with no UI (before) → after

| Endpoint | After |
|---|---|
| GET `/health` | Settings service card |
| PUT `/conversations/{id}/memory` | Header toggle |
| GET/PUT `/memory/settings`, GET/DELETE `/memory/items` | `/app/memory` |
| GET `/memory/items/{id}` | Detail in list (same page) |
| POST `/approvals/{id}` `edit` + `edited_payload` | Approval card |
| POST `/approvals/{id}/resume` | Retry on card |

### UI with no endpoint (hidden, not faked)

| UI | Flag | Why |
|---|---|---|
| Conversation rename | `NEXT_PUBLIC_FEATURE_CONVERSATION_RENAME` | `UpdateConversationRequest` unused; no PATCH route |
| Usage dashboard | `usageDashboard` always off | No usage API |
| Document library / ingestion | `documentLibrary` always off | Uploads only on `POST /chat` |
| Agent/plan browser, RAG search, admin | off | No routes |

### Client vs schema mismatches (fixed in client)

| Client (before) | Backend | Fix |
|---|---|---|
| `/conversations/{id}/events` | `/messages` | Path + map `citations`/`sources` into metadata |
| `/auth/me` | none; JWT `sub` is user id | BFF `GET /users/{sub}` |
| `Conversation` missing `memory_disabled` | field on ConversationResponse | Type + toggle |
| File 20MB + HTML | 10MB, pdf/docx/txt/md | `files.ts` |
| Approval approve/reject only | `edit` + `edited_payload` | Card + API |
| Hand-written types only | OpenAPI | `openapi-typescript` + `make web-api-types` |

### Backend issues / recommendations (do not workaround)

1. **No GET `/auth/me`.** Client must decode JWT `sub`. Prefer a real `/auth/me`.
2. **`UpdateConversationRequest` has no route.** Rename cannot be implemented honestly.
3. **No GET `/approvals/{id}`.** Pending payload is whatever landed on the assistant event metadata. Orchestrator `action` is not persisted on events — user may approve without seeing the exact tool JSON.
4. **Approval POST response has no `resumed_event`.** Resume continues the graph; the client must refetch messages.
5. **No usage or capabilities API.** Quotas exist only as server settings.
6. **No document library / ingestion job API.** Chat multipart is the only upload path.
7. **Login tokens are unwrapped** (not `ApiResponse`) while other routes are enveloped.
8. **Health `environment` / `APP_NAME`** are fine for ops; do not treat as a feature-flag API.
9. **RBAC is server-only.** UI cannot hide by permission without leaking a capabilities endpoint (optional future).
10. **Root GET `/` vs `/health` duplication.**
