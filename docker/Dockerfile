# ==============================================================================
# Stage 1: Build Stage (Builder)
# ==============================================================================
FROM python:3.11-slim AS builder

# Set WORKDIR to /juris_ai so virtualenv paths match the runtime container
WORKDIR /juris_ai

ENV POETRY_VIRTUALENVS_IN_PROJECT=true

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock* ./

# Install dependencies.
# PyTorch is configured in pyproject.toml to use the CPU-only repository,
# avoiding CUDA/NVIDIA packages in the CPU-based application image.
RUN poetry install --no-interaction --no-ansi --no-root


# ==============================================================================
# Stage 2: Final Runtime Stage
# ==============================================================================
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/juris_ai/src \
    PATH="/juris_ai/.venv/bin:$PATH" \
    POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /juris_ai

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

# Create non-root user and runtime directories
RUN useradd -m -u 1000 appuser \
    && mkdir -p \
    data/raw \
    data/db \
    data/vector_db \
    data/cache \
    logs \
    && chown -R appuser:appuser /juris_ai

# Copy virtual environment from builder.
COPY --from=builder \
    --chown=appuser:appuser \
    /juris_ai/.venv \
    /juris_ai/.venv

# Copy project definition files.
COPY --chown=appuser:appuser pyproject.toml poetry.lock* ./

# Copy application configuration.
COPY --chown=appuser:appuser alembic.ini ./alembic.ini

# Copy source code.
COPY --chown=appuser:appuser src ./src

USER appuser

EXPOSE 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=10s \
    --start-period=15s \
    --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=5)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
