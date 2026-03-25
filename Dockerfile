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
RUN mkdir -p /juris_ai/uploads /juris_ai/chroma_db

# Pre-download the embedding model so first request isn't slow
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
