# Pins API (proposed)

Not implemented on FastAPI. Client default: `NEXT_PUBLIC_FEATURE_PINS_BACKEND=local`.

```json
{ "type": "conversation" | "project", "id": "string" }
```

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/pins` | — | `PinItem[]` (user order) |
| PUT | `/pins` | `{ items: PinItem[] }` | `PinItem[]` |
| POST | `/pins/toggle` | `PinItem` | `PinItem[]` |
