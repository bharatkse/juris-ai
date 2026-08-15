FROM python:3.11-slim

# Project root inside container
WORKDIR /juris_ai

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/juris_ai

# System deps (psycopg)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (cache-friendly)
COPY pyproject.toml poetry.lock* ./

RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Copy application code
COPY src /juris_ai/src
COPY alembic.ini /juris_ai/alembic.ini

# Create directories used at runtime
# RUN mkdir -p /juris_ai/uploads /juris_ai/chroma_db

# Create required directories
RUN mkdir -p data/raw data/db data/vector_db data/cache logs


RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /juris_ai
USER appuser

EXPOSE 8000

# Healthcheck used by Docker / Compose
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

CMD ["uvicorn","src.main:app","--host","0.0.0.0","--port","8000","--reload","--reload-dir","/juris_ai/src"]
