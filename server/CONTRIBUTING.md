# Contributing to the Juris AI server

This covers developing on the backend itself — running from source,
tests, linting, and the full local infrastructure (Postgres, Redis,
SearXNG, observability, and the local AWS emulation used for
SAM/Terraform work).

Just want to run Juris AI, not develop on it? Use `./install.sh` from
the repo root instead — see the root [README.md](../README.md).

## Set up commit signing (required for PRs)

Both `develop` and `main` require every commit to be signed before it
can merge. Set this up now, before your first commit — see
[`docs/server/setup/commit-signing.md`](../docs/server/setup/commit-signing.md).

## Clone and enter the server directory

```bash
git clone <repository-url>
cd juris-ai/server
```

Everything below runs from `server/` unless noted otherwise.

## Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

## Install system dependencies

```bash
make bootstrap
```

## Install Python dependencies

```bash
poetry install
```

## Configure environment

```bash
cp env.example .env
```

Update the required values in `.env` — at minimum `SECRET_KEY`,
`JWT_SECRET_KEY`, `DB_*`, and `GROQ_API_KEY`. See the comments in
`env.example` for what else is configurable.

## Install git hooks

```bash
make install-hooks
```

Runs the repo-root [`.pre-commit-config.yaml`](../.pre-commit-config.yaml)
— it covers `server/` and `iac/cloud/` both, not just this directory.

## Start the full local environment

```bash
make dev
```

This starts Docker services (Postgres, Redis, SearXNG, the local
Floci AWS emulator), the observability stack, sets up the restricted
DB role, runs migrations, and deploys the local SAM stack. See
[`docs/server/README.md`](../docs/server/README.md) for what each
step does and the full Makefile command reference — it's long enough
to warrant its own document rather than duplicating it here.

The API will be available at:

- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

## Run tests

```bash
make test-cov          # unit tests with coverage
make test-e2e           # end-to-end tests (needs the DB running)
make test-smoke TARGET=<dir>   # smoke tests against real infra
```

## Before opening a PR

```bash
make pre-commit
make test-cov
```

Both also run in CI (`.github/workflows/ci-server.yml`) — running them
locally first saves a round-trip.

## Known gaps

Check [`claude.md`](../claude.md)'s Known gaps section before assuming
a piece of the design already works as documented — it's the
authoritative, continuously-updated list of confirmed gaps between
the intended architecture and what's actually implemented.
