# Document library API (proposed)

Not implemented on FastAPI. Chat file uploads remain on `POST /chat`. Client default: `NEXT_PUBLIC_FEATURE_DOCUMENTS_BACKEND=local` (metadata only).

```json
{
  "id": "string",
  "name": "string",
  "mime": "string",
  "size": 0,
  "created_at": "date-time"
}
```

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/documents` | — | `LibraryDocument[]` |
| POST | `/documents` | multipart file | `LibraryDocument` |
| DELETE | `/documents/{id}` | — | 204 |
