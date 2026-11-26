# Projects API (proposed)

Not implemented on FastAPI. The web client uses `NEXT_PUBLIC_FEATURE_PROJECTS_BACKEND=local` until these routes exist.

Conversations stay scoped by `conversation_id`. Do not add `allowed_document_ids`.

## `Project`

```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "instructions": "string",
  "conversation_ids": ["string"],
  "document_ids": ["string"],
  "created_at": "date-time",
  "updated_at": "date-time"
}
```

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/projects` | — | `Project[]` |
| POST | `/projects` | `{ name, description?, instructions? }` | `Project` |
| GET | `/projects/{id}` | — | `Project` |
| PATCH | `/projects/{id}` | `{ name?, description?, instructions? }` | `Project` |
| DELETE | `/projects/{id}` | — | 204 |
| POST | `/projects/{id}/conversations` | `{ conversation_id }` | `Project` |
| DELETE | `/projects/{id}/conversations/{conversation_id}` | — | `Project` |
| POST | `/projects/{id}/documents` | `{ document_id }` | `Project` |
| DELETE | `/projects/{id}/documents/{document_id}` | — | `Project` |
