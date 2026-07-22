# Legal AI API Reference

Base URL: `http://localhost:8000/api/v1`
Interactive docs: `http://localhost:8000/docs`

---

## Documents

### `POST /documents/upload`
Upload and ingest a PDF document.

**Request:** `multipart/form-data`
| Field | Type | Description |
|-------|------|-------------|
| `file` | File | PDF file (max 50 MB) |

**Response 201:**
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename":    "contract.pdf",
  "file_size":   204800,
  "status":      "processing",
  "message":     "Document uploaded and queued for ingestion."
}
```

---

### `GET /documents`
List all documents with pagination.

**Query Parameters:**
| Param | Default | Description |
|-------|---------|-------------|
| `skip` | 0 | Records to skip |
| `limit` | 10 | Page size (max 100) |
| `status` | — | Filter: `pending`, `processing`, `indexed`, `failed` |

**Response 200:**
```json
{
  "items": [
    {
      "id":           "550e8400...",
      "filename":     "contract.pdf",
      "status":       "indexed",
      "chunk_count":  42,
      "page_count":   15,
      "file_size_mb": 0.19,
      "doc_type":     "contract",
      "created_at":   "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1,
  "skip":  0,
  "limit": 10
}
```

---

### `GET /documents/{document_id}`
Get full details for a single document.

**Response 200:** Full `DocumentOut` schema including metadata.
**Response 404:** Document not found.

---

### `DELETE /documents/{document_id}`
Delete a document and all its chunks from the DB and vector index.

**Response 200:**
```json
{
  "document_id": "550e8400...",
  "message":     "Document deleted (42 chunks removed).",
  "success":     true
}
```

---

### `POST /documents/{document_id}/reingest`
Re-process an existing document (clears old chunks, re-runs pipeline).

**Response 200:**
```json
{"message": "Document re-ingested successfully.", "success": true}
```

---

## Retrieval

### `POST /retrieval/search`
Pure vector search — returns relevant chunks, no LLM call.

**Request body:**
```json
{
  "query":     "What are the termination clauses?",
  "top_k":     5,
  "threshold": 0.0,
  "use_cache": true
}
```

**Response 200:**
```json
{
  "query": "What are the termination clauses?",
  "chunks": [
    {
      "chunk_id":        "abc123",
      "document_id":     "550e8400...",
      "document_name":   "contract.pdf",
      "chunk_text":      "Either party may terminate this Agreement...",
      "relevance_score": 0.91,
      "sequence":        7
    }
  ],
  "count":  1,
  "cached": false
}
```

---

### `POST /retrieval/ask`
Full RAG: retrieve relevant chunks + generate grounded LLM answer.

**Request body:**
```json
{
  "query":     "What are the payment terms?",
  "top_k":     5,
  "threshold": 0.0,
  "use_cache": true
}
```

**Response 200:**
```json
{
  "query":  "What are the payment terms?",
  "answer": "According to contract.pdf, payment is due within 30 days of invoice...",
  "chunks": [...],
  "source_documents": ["contract.pdf"],
  "model_used": "gpt-3.5-turbo",
  "cached": false
}
```

---

### `POST /retrieval/ask-stream`
Same as `/ask` but streams the answer token-by-token as Server-Sent Events.

**Response:** `text/event-stream`
```
data: {"token": "According"}
data: {"token": " to"}
data: {"token": " contract.pdf"}
...
data: [DONE]
```

**JavaScript example:**
```javascript
const res = await fetch('/api/v1/retrieval/ask-stream', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({query: 'What are the payment terms?'})
});
const reader = res.body.getReader();
const decoder = new TextDecoder();
while (true) {
  const {done, value} = await reader.read();
  if (done) break;
  const lines = decoder.decode(value).split('\n');
  for (const line of lines) {
    if (line.startsWith('data: ') && line !== 'data: [DONE]') {
      const {token} = JSON.parse(line.slice(6));
      process.stdout.write(token);
    }
  }
}
```

---

### `DELETE /retrieval/cache`
Clear all cached search and generation results.

**Response 200:**
```json
{"message": "RAG cache cleared successfully.", "success": true}
```

---

## System

### `GET /health`
Liveness/readiness probe.

**Response 200:**
```json
{
  "status":    "healthy",
  "version":   "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "checks": {
    "database":     "ok",
    "vector_index": "ok"
  }
}
```

---

### `GET /stats`
System statistics.

**Response 200:**
```json
{
  "documents": {
    "total": 10, "indexed": 9, "processing": 1, "failed": 0
  },
  "chunks": {
    "total": 420, "vector_indexed": 420
  },
  "rag": {
    "model": "gpt-3.5-turbo",
    "top_k": 5,
    "reranking": false,
    "cache": {"size": 12, "hit_rate": 0.65}
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Error Responses

All errors return a consistent envelope:

```json
{
  "error":      "not_found",
  "message":    "DocumentORM with id='xyz' not found",
  "details":    [],
  "request_id": "a1b2c3d4-..."
}
```

| HTTP Status | Error Code | Cause |
|-------------|-----------|-------|
| 404 | `not_found` | Document/resource does not exist |
| 413 | `file_too_large` | PDF exceeds size limit |
| 415 | `unsupported_file_type` | Non-PDF file uploaded |
| 422 | `validation_error` | Request body fails validation |
| 422 | `ingestion_error` | PDF processing failed |
| 500 | `retrieval_error` | Vector search failed |
| 502 | `llm_error` | LLM API call failed |
| 503 | Database/storage unavailable |
