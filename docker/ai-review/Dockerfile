FROM ollama/ollama:latest

ARG MODEL=qwen3-coder:30b

ENV OLLAMA_HOST=0.0.0.0:11434
ENV REVIEW_MODEL=${MODEL}

# Install Python for the review script.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY docker/ai-review/review.py /app/review.py

# Start Ollama temporarily during image build,
# download the model, then stop Ollama.
RUN ollama serve > /tmp/ollama-build.log 2>&1 & \
    pid=$!; \
    echo "Waiting for Ollama..."; \
    for i in $(seq 1 60); do \
        if curl -fsS http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then \
            break; \
        fi; \
        sleep 2; \
    done; \
    curl -fsS http://127.0.0.1:11434/api/tags > /dev/null; \
    echo "Pulling model: ${MODEL}"; \
    ollama pull "${MODEL}"; \
    kill "${pid}" || true; \
    wait "${pid}" || true

EXPOSE 11434

ENTRYPOINT ["ollama"]
CMD ["serve"]
