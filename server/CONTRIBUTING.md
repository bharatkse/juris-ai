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

## Clone the repository

```bash
git clone <repository-url>
cd juris-ai
```

Everything below runs from the **repo root** unless noted otherwise. The
`Makefile` and `setup.sh` both live there; the Makefile runs the Python
tooling (Poetry, Alembic, pytest, Ruff, SAM) inside `server/` for you.

## Create a virtual environment

The virtualenv lives at the **repo root** (`.venv`). Poetry is configured
in-project for `server/`, so `server/.venv` is a symlink to it:

```bash
make venv
source .venv/bin/activate
```

## Install system dependencies

```bash
make bootstrap
```

## Install Python dependencies

```bash
make poetry-install
```

## Configure environment

```bash
cp server/env.example server/.env
```

Update the required values in `server/.env` — at minimum `SECRET_KEY`,
`JWT_SECRET_KEY`, `DB_*`, and `GROQ_API_KEY`. See the comments in
`server/env.example` for what else is configurable.

## Install git hooks

```bash
make install-hooks
```

Runs the repo-root [`.pre-commit-config.yaml`](../.pre-commit-config.yaml)
— it covers `server/` and `iac/cloud/` both, not just this directory.

## Start the full local environment

```bash
./setup.sh --install --mode dev    # Docker stacks
make dev                           # post-install steps
```

`setup.sh` starts the Docker stacks (Postgres, Redis, SearXNG, Ollama,
the local Floci AWS emulator, and the observability stack); it is the
single owner of stack lifecycle (install/start/stop/reinstall/cleanup/
uninstall), not the Makefile. `make dev` then sets up the restricted
DB role, pulls the Ollama model, runs migrations, and deploys the
local SAM stack. See
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

## Splitting large scripts

`setup.sh` and `Makefile` (both at the repo root) are single files on purpose. Revisit
that with the rule below, not on taste. Split a concern into its own
file (`lib/setup/<concern>.sh` / `mk/<concern>.mk`) when either holds:

- **Size and churn** — the concern's block is over ~250 lines (bash)
  or ~150 lines (make) **and** at least 3 commits in the last 30 days
  touched it without touching the rest of the file (check with
  `git log -L :<function>:<file>`), or
- **Second consumer** — another script needs the same code (for
  example `bootstrap.sh` and `setup.sh` both creating `.env`). Extract
  it regardless of size.

Hold any split while paths are about to move — everything would be edited
twice. (The Makefile has already moved to the repo root, so that is settled.)

Snapshot at the time of writing (2026-09-21): `setup.sh` is about
1,240 lines; its largest concern, argument parsing and menus, is about 355
lines, but the file has a single commit of history, so there is no churn
signal. `Makefile` is about 760 lines; its largest section is about 70.
Neither meets the rule. If a split is approved later: `setup.sh` stays the
entrypoint and `source`s `lib/setup/{common,args,env,compose,state,health,
dependencies,lifecycle}.sh` (function definitions only; globals stay in
`setup.sh`); the Makefile keeps its variables, `MODE` detection and `help`
and `include`s `mk/{docker,db,quality,test,iac}.mk` via
`MK_DIR := $(dir $(lastword $(MAKEFILE_LIST)))`, defined before the includes.

## Known gaps

Check [`docs/known-issues.md`](../docs/known-issues.md) before
assuming a piece of the design already works as documented — it's the
committed, continuously-updated list of confirmed gaps between the
intended architecture and what's actually implemented. (Module
READMEs, e.g. `src/agentic/README.md` and `src/rag/README.md`, carry
their own package-specific "Known gaps" sections too — check the
relevant one first if the area you're touching has one.)
