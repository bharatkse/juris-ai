# Sandbox messaging MCP server for the live messaging tests
# (docs/messaging-live-test.md). Test-only; never part of the app image.
FROM python:3.11-slim

# Same versions as server/poetry.lock.
RUN pip install --no-cache-dir "mcp==2.2.0" "httpx==0.28.1"

WORKDIR /sandbox
COPY server.py ./server.py

RUN useradd --create-home sandbox
USER sandbox

ENV SANDBOX_MCP_HOST=0.0.0.0 \
    SANDBOX_MCP_PORT=8765

EXPOSE 8765

CMD ["python", "server.py"]
