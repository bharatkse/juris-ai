# Legal AI Agent System

Retrieval-Augmented Generation for legal documents.
Upload PDFs → ask questions in plain English → get grounded answers with citations.

---

## Features

- **PDF ingestion** — upload any PDF; automatic text extraction, chunking, deduplication
- **Semantic search** — FAISS vector search with cosine similarity
- **Grounded answers** — LLM answers cite your actual documents
- **Streaming** — token-by-token SSE streaming responses
- **Multiple LLMs** — OpenAI (GPT-3.5/4/4o) or Anthropic (Claude 3)
- **Pluggable storage** — local filesystem or AWS S3
- **Pluggable cache** — in-memory or Redis
- **REST API** — FastAPI with auto-generated OpenAPI docs

---

## Quick Start

```bash
git clone <repo> && cd juris-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # set SECRET_KEY + LLM API key
python scripts/seed_database.py
uvicorn main:app --reload
# Open http://localhost:8000/docs
```

---

## Project Layout

```
src/
├── core/          Config, logging, exceptions, enums
├── models/        Pydantic domain models
├── db/            SQLAlchemy ORM + session
├── repository/    Data access (Repository pattern)
├── storage/       File storage abstraction (local / S3)
├── ingestion/     PDF → chunks → embeddings → index
├── embeddings/    Text → vector (local / OpenAI)
├── vector_store/  FAISS search + reranking
├── cache/         In-memory / Redis cache
├── llm/           OpenAI / Claude provider
├── rag/           Retrieve + generate orchestration
├── api/           FastAPI routes + middleware
└── schemas/       HTTP request/response schemas
```

---

## Documentation

|                                        |                              |
| -------------------------------------- | ---------------------------- |
| [Getting Started](docs/README.md)      | Installation, first document |
| [API Reference](docs/API.md)           | All endpoints                |
| [Architecture](docs/ARCHITECTURE.md)   | System design + data flow    |
| [Ingestion Guide](docs/INGESTION.md)   | PDF processing pipeline      |
| [RAG Guide](docs/RAG.md)               | Retrieval + generation       |
| [Deployment Guide](docs/DEPLOYMENT.md) | Production deployment        |

---

## Stack

| Layer      | Technology                       |
| ---------- | -------------------------------- |
| API        | FastAPI + Uvicorn                |
| Database   | SQLite (dev) / PostgreSQL (prod) |
| ORM        | SQLAlchemy 2.0                   |
| Vector DB  | FAISS (local)                    |
| Embeddings | sentence-transformers / OpenAI   |
| LLM        | OpenAI GPT / Anthropic Claude    |
| Cache      | In-memory / Redis                |
| Storage    | Filesystem / AWS S3              |
| Migrations | Alembic                          |
| Container  | Docker + Compose                 |

---

## License

MIT
