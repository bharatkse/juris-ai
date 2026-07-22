# Deployment Guide

---

## Local Development

```bash
# Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in SECRET_KEY and OPENAI_API_KEY

# Initialise
python scripts/seed_database.py

# Run
uvicorn main:app --reload
# API: http://localhost:8000    Docs: http://localhost:8000/docs
```

---

## Docker (Recommended)

```bash
# Development stack (hot-reload, Redis included)
docker compose -f docker/docker-compose.yml up

# Production build
docker build -f docker/Dockerfile -t legal-ai:latest .
docker run -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  legal-ai:latest
```

---

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Random 32+ char secret. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | `sqlite:///./data/db/legal.db` or `postgresql://user:pass@host/db` |
| `OPENAI_API_KEY` | Required when `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | Required when `LLM_PROVIDER=claude` |

### Production Settings

```env
DEBUG=false
ENVIRONMENT=production
ENABLE_DOCS=false               # disable Swagger in production
LOG_FORMAT=json                 # structured logs for log aggregators
LOG_LEVEL=INFO
CACHE_BACKEND=redis
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS=["https://yourdomain.com"]
WORKERS=4                       # set to CPU count
```

---

## PostgreSQL Setup

```bash
# 1. Create database
psql -U postgres -c "CREATE USER legal_ai WITH PASSWORD 'strongpassword';"
psql -U postgres -c "CREATE DATABASE legal_db OWNER legal_ai;"

# 2. Set in .env
DATABASE_URL=postgresql://legal_ai:strongpassword@localhost:5432/legal_db

# 3. Run migrations
alembic upgrade head
```

---

## Database Migrations

```bash
# Create a new migration (after changing ORM models)
alembic revision --autogenerate -m "describe the change"

# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Show current revision
alembic current
```

---

## Production Checklist

**Security**
- [ ] `SECRET_KEY` is unique and random (32+ chars)
- [ ] `DEBUG=false` and `ENABLE_DOCS=false`
- [ ] `CORS_ORIGINS` restricted to your domain
- [ ] Database password is strong
- [ ] API keys stored in secrets manager (not plain .env)
- [ ] Running as non-root user in container

**Performance**
- [ ] `WORKERS` set to CPU core count
- [ ] `CACHE_BACKEND=redis` enabled
- [ ] PostgreSQL connection pool tuned (`DATABASE_POOL_SIZE=20`)
- [ ] GPU enabled if embedding throughput is needed

**Reliability**
- [ ] Database backups scheduled
- [ ] FAISS index backed up (`data/vector_db/`)
- [ ] Health check endpoint monitored (`GET /api/v1/health`)
- [ ] Logs shipped to centralised log system

**Scaling**
- [ ] Load balancer in front of multiple API instances
- [ ] Redis shared across all instances (`CACHE_BACKEND=redis`)
- [ ] Database on dedicated host

---

## Health Monitoring

```bash
# Basic health check
curl http://localhost:8000/api/v1/health

# Detailed stats
curl http://localhost:8000/api/v1/stats

# Script-based check (exits 0=healthy, 1=unhealthy)
python scripts/health_check.py --skip-llm
```

---

## Useful Operations

```bash
# Batch ingest new documents
python scripts/run_ingestion.py --dir ./new_documents

# Rebuild vector index (after model change)
python scripts/build_index.py --full

# Clear RAG cache
python scripts/cleanup_cache.py

# Reset everything (DEV ONLY)
python scripts/seed_database.py --reset
python scripts/build_index.py --full
```

---

## Logs

```bash
# Live log tail (local)
tail -f logs/app.log | jq .

# Docker logs
docker logs legal_ai_api -f

# Filter by level
tail -f logs/app.log | jq 'select(.level == "ERROR")'
```
