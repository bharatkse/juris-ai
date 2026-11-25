# docker/clients/

Compose overlay for first-party clients under [`clients/`](../../clients/).

The web app image is built from [`web/Dockerfile`](web/Dockerfile)
(Next.js standalone, non-root). Compose `build.context` is
[`clients/web`](../../clients/web) and `dockerfile` is
`../../docker/clients/web/Dockerfile` (relative to that context — Compose
bake). Ignore rules are [`web/Dockerfile.dockerignore`](web/Dockerfile.dockerignore)
next to the Dockerfile (BuildKit), so the Next.js package root does not
carry a `.dockerignore`. The Compose file lives here so it can join the
shared `juris_ai_network` next to the FastAPI service.

```bash
# Server stack must already be on juris_ai_network
docker compose -f docker/clients/docker-compose.yml up -d web

# Hot-reload (bind-mounts clients/web)
docker compose -f docker/clients/docker-compose.yml --profile dev up web-dev
```

Makefile: `make web-up`, `make web-up-dev`. See [`clients/web/README.md`](../../clients/web/README.md).
