# Juris-AI Development Guide

The **Makefile is the primary entry point** for testing, code quality, database migrations, SAM/Terraform deployment, and inspecting the running stack (logs, shells, container status).

**Installing, starting, stopping, reinstalling and removing the Docker stacks is done by [`setup.sh`](../../setup.sh) at the repo root, not by `make`.** Run it, like every `make` command in this guide, from the repo root — e.g. `./setup.sh --install --mode dev`; `./setup.sh --help` lists every option. The sections below say which commands are `make` and which are `setup.sh`.

The `Makefile` lives at the repo root (next to `setup.sh`) and runs the Python tooling — Poetry, Alembic, pytest, Ruff, SAM, and the `server/scripts/` helpers — inside `server/` for you. `TARGET=` paths in the test targets are therefore relative to `server/` (for example `tests/unit/services/test_user.py`).

You generally should not need to run raw Docker, Poetry, Alembic, SAM, or AWS CLI commands for normal development.

The Makefile also auto-detects the active environment from Floci health.

> Floci is a drop-in, MIT-licensed local AWS emulator that replaced
> LocalStack here (see `claude.md`'s Known gaps for the one rough
> edge found during that swap). It serves the same
> `/_localstack/health` endpoint for compatibility. Most internal
> Makefile identifiers were renamed to match (`FLOCI_HEALTH_URL`,
> `_FLOCI_UP`) — the `ls-*` target names, and `make env-info`'s/`make help`'s
> printed labels below were deliberately left as "LocalStack" (see
> the repo-wide LocalStack sweep for the reasoning per item).

---

## Where to look for what

This guide covers **workflow** (commands, environments, troubleshooting). For **architecture**:

| Document | Authoritative for |
|---|---|
| [`docs/architecture/overview.md`](architecture/overview.md) | Intended/target design, with inline "Current implementation status" callouts marking where reality has diverged (and been fixed back) |
| [`docs/architecture/api.md`](architecture/api.md) | REST API surface reference |
| [`docs/architecture/user-memory.md`](architecture/user-memory.md) | Cross-conversation user memory: consent/retention model, write/read path design, pre-ship checklist |
| [`src/agentic/README.md`](../src/agentic/README.md) | Current, real behavior of planning/orchestration/execution/agents/tools — read this to debug a live agent request |
| [`src/rag/README.md`](../src/rag/README.md) | Current, real behavior of ingestion/indexing/retrieval/evaluation — read this to debug a retrieval-quality issue |
| [`claude.md`](../claude.md) (repo root) | Repo-wide working conventions and the authoritative, cross-cutting "Known gaps" list — every module doc cross-references it rather than duplicating it |

When `overview.md` and a module README disagree, the module README
wins — it documents what the code does today, not what it was
designed to do.

---

## 1. Prerequisites

Before starting, make sure the following are installed:

- Docker / Docker Compose
- Poetry
- Python
- AWS CLI
- AWS SAM CLI
- Make
- Git

For local development, Floci is required.

---

# 2. Environment Detection

The Makefile automatically determines the environment:

| Environment | Meaning                                     |
| ----------- | ------------------------------------------- |
| `dev`       | Local development using Docker + Floci      |
| `snd`       | Shared AWS environment                      |

Detection is based on Floci health:

```text
Floci running      → MODE=dev
Floci not running  → MODE=snd
```

You can always override the detected mode:

```bash
make <target> MODE=dev
make <target> MODE=snd
```

> **Be careful with `MODE=snd` because it targets real AWS resources.**

---

# 3. Check the Active Environment

Before running deployment or infrastructure commands:

```bash
make env-info
```

This shows the resolved configuration, including:

- environment
- mode
- API service name
- CloudFormation stack
- template
- AWS region
- Floci status
- S3 bucket

Example (the Makefile's own output still prints the historical `LocalStack` label — see the note in the introduction above):

```text
ENV             dev
MODE            dev
REGION          us-east-1
LocalStack      yes
```

You can also see all available commands:

```bash
make help
```

---

# 4. First-Time Setup

Run:

```bash
make bootstrap
```

This executes:

```text
server/scripts/bash/bootstrap.sh
```

and prepares the development environment.

Install or synchronize Python dependencies with:

```bash
make poetry-install
```

If you want to validate the Poetry configuration:

```bash
make poetry-check
```

---

# 5. Configure Environment Variables

Juris-AI uses `server/.env` for local configuration.

Typical external services include:

- Groq
- Brave Search
- LangSmith
- PostgreSQL
- OpenTelemetry

Do not commit `server/.env`.

Use `.env.example` as the safe template.

For service-specific setup instructions, see:

```text
docs/
└── setup/
    ├── groq.md
    ├── brave.md
    └── langsmith.md
```

---

# 6. Local Development

Use `MODE=dev`.

Local development uses:

- Docker
- PostgreSQL
- Redis
- Floci
- AWS SAM
- OpenTelemetry Collector
- Prometheus
- Grafana
- Tempo, when included in the infrastructure Compose configuration

No real AWS resources are intended for the local workflow.

---

## 6.1 Start the Application

Install and start the stacks with `setup.sh`, then run the Makefile's post-install steps:

```bash
./setup.sh --install --mode dev   # server, dependencies, observability, development
make dev                           # DB role, Ollama model, migrations, local SAM deploy
```

Check the application containers:

```bash
make docker-ps MODE=dev
```

Follow application logs:

```bash
make docker-app-logs MODE=dev
```

Open a shell inside the API container:

```bash
make docker-exec-app MODE=dev
```

---

# 7. Observability Infrastructure

Observability has an independent lifecycle from the application, owned by `setup.sh`.

Start, or recreate and pull current images:

```bash
./setup.sh --install --bundle observability
./setup.sh --reinstall --bundle observability
```

Stop, keeping data: `./setup.sh --cleanup --bundle observability`.

Remove, including data: `./setup.sh --uninstall --bundle observability` — destructive: also deletes the Prometheus, Tempo and Grafana data volumes, and asks for confirmation.

Check:

```bash
make infra-ps MODE=dev
```

View logs:

```bash
make infra-logs MODE=dev
```

The observability stack contains:

```text
OpenTelemetry Collector
Prometheus
Grafana
```

If Tempo is included in `docker/observability/docker-compose.yml`, it should be managed alongside the observability stack.

---

# 8. Database Migrations

## Local DB role separation (one-time per Postgres volume)

The app connects as a restricted, non-superuser role (`APP_DB_USER`)
distinct from the admin/migration role (`DB_USER`) that owns the
schema. A **fresh** Postgres container/volume creates this role
automatically on first boot
(`docker/dependencies/init/postgres/01-create-app-role.sh`, a
`docker-entrypoint-initdb.d` hook). That hook only ever runs against
an empty volume, though — if your local Postgres volume predates this
role split (or you're not sure), run:

```bash
make db-setup-role
```

Safe to re-run any time (idempotent — creates the role if missing,
re-syncs its password to `.env` if it already exists). Run this
**before** `make alembic-upgrade` below: one migration
(`dd110a14caf1_restrict_compliance_log_to_insert_.py`) restricts this
role's access to a specific table and requires the role to already
exist, or it errors.

Local dev only — this does not apply to any cloud/RDS deployment.

## Apply migrations

Apply all pending migrations:

```bash
make alembic-upgrade
```

Check the current migration:

```bash
make alembic-current
```

Show migration history:

```bash
make alembic-history
```

Show migration heads:

```bash
make alembic-heads
```

Create a new autogenerated migration:

```bash
make alembic-revision msg="create users table"
```

Rollback the last migration:

```bash
make alembic-downgrade
```

Stamp a database revision:

```bash
make alembic-stamp rev=head
```

---

# 9. Floci

Floci is automatically detected by the Makefile.

Check:

```bash
make env-info
```

You should see (still labeled `LocalStack` in the Makefile's own output — see the note in the introduction):

```text
MODE        dev
LocalStack  yes
```

List S3 buckets:

```bash
make ls-s3
```

List API Gateway APIs:

```bash
make ls-api-id
```

List API keys:

```bash
make ls-api-key
```

List APIs and keys together:

```bash
make ls-api
```

List all supported Floci resources:

```bash
make ls-resources
```

List objects in the configured S3 bucket:

```bash
make ls-s3-objects
```

To specify a different bucket:

```bash
make ls-s3-objects S3_BUCKET=<bucket-name>
```

These resource inspection commands require development mode.

---

# 10. Build and Deploy the Application

Two infrastructure-as-code paths exist side by side. **SAM/CloudFormation
is the original path and still works.** **Terraform
(`iac/terraform/`) is the newer, multi-cloud-oriented path** — AWS
is fully built and parity-tested against it; GCP/Azure exist only as
interface-contract stubs (`iac/terraform/modules/*/{gcp,azure}/README.md`),
not working code. Prefer Terraform for new infrastructure work; SAM
remains available and is not scheduled for removal yet.

## SAM / CloudFormation (existing)

### Build

```bash
make cf-build MODE=dev
```

The Makefile exports the main Poetry dependencies and runs SAM build.

### Deploy locally

```bash
make cf-deploy MODE=dev
```

This builds the application and deploys the selected CloudFormation stack.

### Check stack status

```bash
make cf-status MODE=dev
```

### View CloudFormation events

```bash
make cf-logs MODE=dev
```

## Terraform (new)

### Initialize

```bash
make iac-init
```

Run once per checkout, and again any time a module is added.

### Plan

```bash
make iac-plan PROVIDER=aws
```

### Deploy locally

```bash
make iac-apply PROVIDER=aws
```

Applies all four Phase 1 modules (`secrets`, `api-gateway`, `storage`,
`observability`) against Floci, using `iac/terraform/dev.floci.tfvars`.

### Show outputs

```bash
make iac-output
```

### Destroy

```bash
make iac-destroy PROVIDER=aws
```

> **Do not run `make iac-apply` a second time against an
> already-applied Floci stack expecting a clean incremental update.**
> A confirmed Floci defect on `aws_api_gateway_integration`'s
> `timeout_milliseconds` makes any update attempt against an existing
> Floci-created integration fail outright — see `claude.md`'s Known
> gaps. Always `make iac-destroy` before re-applying against Floci;
> real AWS deploys are unaffected.

`PROVIDER` only accepts `aws` today — anything else fails fast with a
clear message from the Terraform configuration's own variable
validation, not a Makefile guard.

---

# 11. Shared AWS / SND Environment

Use `MODE=snd` when working with the shared AWS environment.

Before using it, configure AWS credentials:

```bash
aws configure
```

Verify the active AWS identity:

```bash
aws sts get-caller-identity
```

Then explicitly use:

```bash
make cf-build MODE=snd
make cf-deploy MODE=snd
```

Check the stack:

```bash
make cf-status MODE=snd
```

View stack events:

```bash
make cf-logs MODE=snd
```

> The Makefile includes a confirmation guard for SND operations. Review the target and environment carefully before continuing.

---

# 12. Testing

Run the complete test suite:

```bash
make test
```

Run unit tests:

```bash
make test-unit
```

Run a specific unit-test package:

```bash
make test-unit TARGET=services
```

Run a sub-package:

```bash
make test-unit TARGET=services/chat
```

Run a specific test file:

```bash
make test-unit TARGET=tests/unit/services/test_user.py
```

You can also provide a path that already exists:

```bash
make test-unit TARGET=services/test_user.py
```

Run a single test:

```bash
make test-path   TARGET="tests/unit/services/test_user.py::test_create_user"
```

Run integration tests:

```bash
make test-integration
```

Run a specific integration target:

```bash
make test-integration TARGET=services/chat
```

Run end-to-end tests:

```bash
make test-e2e
```

Run a specific E2E target:

```bash
make test-e2e TARGET=chat
```

Run tests with coverage:

```bash
make test-cov
```

Re-run only previously failed tests:

```bash
make test-failed
```

Watch unit tests:

```bash
make test-watch
```

Run tests by keyword directly through Poetry when needed:

```bash
poetry run pytest tests/unit -k create_user -v
```

---

# 13. Code Quality

Run Ruff linting:

```bash
make lint
```

Format the project:

```bash
make format
```

Run mypy:

```bash
make type-check
```

Run pre-commit hooks:

```bash
make pre-commit
```

Install the Git pre-commit hooks:

```bash
make install-hooks
```

Run the complete CI workflow:

```bash
make ci
```

The current CI target runs:

```text
lint
  ↓
type-check
  ↓
tests
```

---

# 14. Poetry

Install dependencies:

```bash
make poetry-install
```

Update dependencies:

```bash
make poetry-update
```

Regenerate the lock file:

```bash
make poetry-lock
```

Validate the project:

```bash
make poetry-check
```

Show the dependency tree:

```bash
make poetry-show
```

Activate the Poetry environment:

```bash
make poetry-activate
```

Export main dependencies:

```bash
make poetry-export
```

The exported requirements file is:

```text
src/requirements.txt
```

---

# 15. Complete Local Development Workflow

For a normal development session:

## Step 1 — Check environment

```bash
make env-info
```

## Step 2 — Install / start the stacks

```bash
./setup.sh --install --mode dev
```

Starts the server, PostgreSQL/Redis/Floci, observability, and the Ollama/SearXNG stacks. Anything already running is left unchanged.

## Step 3 — Set up local DB role separation

```bash
make db-setup-role
```

Idempotent — safe on every session, but only strictly needed once per
Postgres volume (see section 8 above for why). Must come before Step 5.

## Step 4 — Set up the local Ollama model

```bash
make llm-pull
```

Idempotent — checks `ollama list` inside the container first and
skips the (multi-GB) pull if the configured model (`LLM_LOCAL_MODEL`
in `.env`, default `qwen3:8b`) is already present. Only wired into
explicit setup flows like this one and `make dev`/`make
restart-hard`, never into a plain `docker compose up`, so a routine
restart never blocks on a multi-GB download. `setup.sh` starts Ollama
but does not pull the model. See `server/scripts/bash/pull_ollama_models.sh`.

## Step 5 — Apply database migrations

```bash
make alembic-upgrade
```

## Step 6 — Check containers

```bash
make docker-ps MODE=dev
make infra-ps MODE=dev
```

## Step 7 — Check application logs

```bash
make docker-app-logs MODE=dev
```

## Step 8 — Run tests

```bash
make test-unit
```

## Step 9 — Run quality checks

```bash
make lint
make type-check
```

---

# 16. One-Command Post-Install Steps

The Makefile also provides:

```bash
make dev
```

This runs the Makefile-native steps of the local development workflow. **Install and start the stacks first** with `./setup.sh --install --mode dev` — `make dev` does not start Docker services itself.

```text
Local DB role separation setup (idempotent)
        ↓
Local Ollama model pull (idempotent)
        ↓
Database migrations
        ↓
SAM build/deployment
```

To redo those steps from a clean SAM state, use:

```bash
make restart-hard MODE=dev
```

This cleans SAM artifacts and reruns `db-setup-role`, `llm-pull`, `alembic-upgrade` and `cf-deploy`. To recreate the Docker stacks first, run `./setup.sh --reinstall --mode dev`.

---

# 17. Application-Specific Development Targets

The Makefile also provides smaller development workflows:

Build the development SAM application:

```bash
make dev-build
```

Deploy the development SAM stack:

```bash
make dev-deploy
```

Post-install development steps (run `./setup.sh --install --mode dev` first):

```bash
make dev
```

---

# 18. Cleanup

Stop or remove Docker stacks with `setup.sh`:

```bash
./setup.sh --cleanup --bundle <bundle>     # stop and remove containers, keep data
./setup.sh --uninstall --bundle <bundle>   # also remove persistent data (destructive, asks to confirm)
```

`<bundle>` is `server`, `dependencies`, `observability`, `development` or `clients`; use `--dependency postgres|redis|floci` to target one dependency. See `./setup.sh --help`.

Clean SAM build artifacts:

```bash
make clean-local
```

To redo the post-install steps from a clean SAM state:

```bash
make restart-hard MODE=dev
```

> `setup.sh --uninstall` is destructive. Use it when you intentionally want to remove local Docker state and its data.

---

# 19. Troubleshooting

## Floci is not detected

Check:

```bash
make env-info
```

If you intended to use Floci, make sure it is running.

You can explicitly force development mode:

```bash
make ls-s3 MODE=dev
```

The Makefile will warn if Floci is not healthy. To start Floci: `./setup.sh --install --dependency floci`.

---

## PostgreSQL database files are incompatible

If PostgreSQL reports a version/storage incompatibility, reset the local Postgres state (destructive: deletes the local Postgres data, asks to confirm):

```bash
./setup.sh --uninstall --dependency postgres
```

If necessary:

```bash
docker volume prune -f
```

---

## App fails to connect to Postgres / "password authentication failed" for APP_DB_USER

Your Postgres volume predates local DB role separation, so
`APP_DB_USER` (e.g. `juris_ai_app`) was never created —
`docker-entrypoint-initdb.d` only runs against a brand-new, empty
volume, never an existing one. Run:

```bash
make db-setup-role
```

then restart the `api` container so it picks up the (possibly new)
`.env` values:

```bash
docker compose -f docker/server/docker-compose.yml up -d --force-recreate --no-deps api
```

See section 8 above for the full explanation.

Then restart:

```bash
./setup.sh --install --dependency postgres
./setup.sh --reinstall --bundle server
```

Apply migrations:

```bash
make alembic-upgrade
```

> `docker volume prune -f` affects unused Docker volumes on the machine, so use it carefully.

---

## Port Already Allocated

Find the process using a port:

```bash
sudo lsof -i :8001
```

Or inspect Docker containers:

```bash
docker ps
```

Stop the conflicting process/container before restarting Juris-AI.

---

## AWS Credentials Not Found

Configure AWS credentials:

```bash
aws configure
```

Verify:

```bash
aws sts get-caller-identity
```

For local development, use:

```bash
MODE=dev
```

so AWS operations are directed toward Floci rather than real AWS.

---

# 20. Full Clean Rebuild

For a complete local rebuild:

```bash
./setup.sh --uninstall --mode dev   # destructive; asks for confirmation
./setup.sh --install --mode dev
make clean-local
make db-setup-role
make llm-pull
make alembic-upgrade
make cf-build MODE=dev
make cf-deploy MODE=dev
```

For most cases, recreate the stacks with `./setup.sh --reinstall --mode dev` and then prefer:

```bash
make restart-hard MODE=dev
```

because it already runs the post-install steps (SAM clean, DB role, model pull, migrations, deploy).

---

# 21. Recommended Daily Commands

Most development work should only require a small subset of the Makefile:

```bash
# Check environment
make env-info

# Start the stacks (skips anything already running)
./setup.sh --install --mode dev

# Apply migrations
make alembic-upgrade

# Run tests
make test-unit

# Check code quality
make lint
make type-check

# View application logs
make docker-app-logs MODE=dev

# View infrastructure logs
make infra-logs MODE=dev
```

---

# 22. Command Reference

| Area          | Target              | Purpose                                |
| ------------- | ------------------- | -------------------------------------- |
| Environment   | `env-info`          | Show resolved environment              |
| Setup         | `bootstrap`         | Run project bootstrap                  |
| Docker        | `docker-build`      | Build application images               |
| Docker        | `docker-ps`         | Show application containers            |
| Docker        | `docker-app-logs`   | Follow application logs                |
| Docker        | `docker-exec-app`   | Open API container shell               |
| Observability | `infra-logs`        | Follow observability logs              |
| Observability | `infra-ps`          | Show observability containers          |
| Database      | `db-setup-role`     | Create restricted runtime DB role      |
| LLM           | `llm-pull`          | Pull the Ollama model                  |
| Database      | `alembic-upgrade`   | Apply migrations                       |
| Database      | `alembic-downgrade` | Roll back migration                    |
| Database      | `alembic-current`   | Show current revision                  |
| Database      | `alembic-history`   | Show migration history                 |
| Database      | `alembic-revision`  | Create migration                       |
| Floci         | `ls-s3`             | List S3 buckets                        |
| Floci         | `ls-api-id`         | List API Gateway APIs                  |
| Floci         | `ls-api-key`        | Show API key                           |
| Floci         | `ls-api`            | List APIs and keys                     |
| Floci         | `ls-resources`      | List Floci resources                   |
| Floci         | `ls-s3-objects`     | List S3 objects                        |
| SAM           | `cf-build`          | Build SAM application                  |
| SAM           | `cf-deploy`         | Deploy CloudFormation                  |
| SAM           | `cf-status`         | Show stack status                      |
| SAM           | `cf-logs`           | Show stack events                      |
| Terraform     | `iac-init`          | Initialize Terraform                   |
| Terraform     | `iac-plan`          | Show execution plan                    |
| Terraform     | `iac-apply`         | Apply configuration                    |
| Terraform     | `iac-output`        | Show outputs                           |
| Terraform     | `iac-destroy`       | Destroy managed infrastructure         |
| Tests         | `test`              | Run all tests                          |
| Tests         | `test-unit`         | Run unit tests                         |
| Tests         | `test-integration`  | Run integration tests                  |
| Tests         | `test-e2e`          | Run E2E tests                          |
| Tests         | `test-cov`          | Run tests with coverage                |
| Tests         | `test-failed`       | Re-run failed tests                    |
| Tests         | `test-path`         | Run a specific test path               |
| Quality       | `lint`              | Run Ruff                               |
| Quality       | `format`            | Format code                            |
| Quality       | `type-check`        | Run mypy                               |
| Quality       | `pre-commit`        | Run pre-commit                         |
| Quality       | `ci`                | Run lint, type-check, tests            |
| Poetry        | `poetry-install`    | Install dependencies                   |
| Poetry        | `poetry-update`     | Update dependencies                    |
| Poetry        | `poetry-lock`       | Regenerate lock                        |
| Poetry        | `poetry-show`       | Show dependency tree                   |
| Poetry        | `poetry-export`     | Export requirements                    |
| Cleanup       | `clean-local`       | Remove SAM build artifacts             |
| Cleanup       | `restart-hard`      | Clean SAM and redo post-install steps  |
| Development   | `dev`               | Post-install steps (DB role, model, migrations, deploy) |

**Not in this table:** installing, starting, stopping, reinstalling, cleaning up and uninstalling the Docker stacks (server, PostgreSQL/Redis/Floci, observability, Ollama/SearXNG). That is [`setup.sh`](../../setup.sh) — run `./setup.sh --help`.

---

# 23. Makefile Help

If you forget a target or its purpose:

```bash
make help
```

The Makefile is the source of truth for available development commands.

When a command changes in the Makefile, update this guide accordingly.
