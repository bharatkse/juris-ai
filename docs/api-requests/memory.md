# Memory API gaps

Shipped today: `GET/PUT /memory/settings`, `GET /memory/items`, `GET /memory/items/{id}`, `DELETE /memory/items/{id}`.

The web UI also needs create/update for the master-detail editor:

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/memory/items` | `{ content: string, kind?: string }` | `MemoryItem` |
| PATCH | `/memory/items/{id}` | `{ content?: string, kind?: string }` | `MemoryItem` |

Turning memory off already deletes all items. A dedicated `DELETE /memory/items` (clear all while leaving consent on) would avoid the off/on round-trip the HTTP adapter uses today.

Until POST/PATCH exist, set `NEXT_PUBLIC_FEATURE_MEMORY_BACKEND=local` for a full editor, or keep `http` and accept 404 on add/edit.
