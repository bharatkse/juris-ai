# ==============================================================================
# Stage 1: Build Stage (Builder)
# ==============================================================================
FROM python:3.11-slim AS builder

# Pinned so rebuilds (and the image vulnerability scan) are
# reproducible. >=2.3.3 for CVE-2026-34591; 2.5 also allows dulwich 1.x
# (0.25.x carries three HIGH CVEs).
ARG POETRY_VERSION=2.5.1

# Set WORKDIR to /juris_ai_server so virtualenv paths match the runtime container
WORKDIR /juris_ai_server

# No pip in the project venv: Poetry installs without it, nothing at
# runtime uses it, and pip's vendored msgpack/pkg_resources are flagged
# by the image scan with no fixed pip release yet.
ENV POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_VIRTUALENVS_OPTIONS_NO_PIP=true

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade the base image's own pip/setuptools/wheel first: the copies
# python:3.11-slim ships (setuptools 70.x, vendoring jaraco.context 5.3
# and wheel 0.45) carry fixable HIGH CVEs that the image scan flags.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock* ./

# Install dependencies.
# PyTorch is configured in pyproject.toml to use the CPU-only repository,
# avoiding CUDA/NVIDIA packages in the CPU-based application image.
RUN poetry install --no-interaction --no-ansi --no-root


# ==============================================================================
# Stage 2: Final Runtime Stage
# ==============================================================================
FROM python:3.11-slim AS runtime

ARG POETRY_VERSION=2.5.1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/juris_ai_server/src \
    PATH="/juris_ai_server/.venv/bin:$PATH" \
    POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /juris_ai_server

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade the base image's own pip/setuptools/wheel first: the copies
# python:3.11-slim ships (setuptools 70.x, vendoring jaraco.context 5.3
# and wheel 0.45) carry fixable HIGH CVEs that the image scan flags.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir "poetry==${POETRY_VERSION}" \
    && python -m pip uninstall --yes pip

# Create non-root user and runtime directories
RUN useradd -m -u 1000 appuser \
    && mkdir -p \
    data/raw \
    data/db \
    data/vector_db \
    data/cache \
    logs \
    && chown -R appuser:appuser /juris_ai_server

# Copy virtual environment from builder.
COPY --from=builder \
    --chown=appuser:appuser \
    /juris_ai_server/.venv \
    /juris_ai_server/.venv

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
