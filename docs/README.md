# Juris AI - Development Guide

This project uses a single `Makefile` as the primary entry point for all development tasks.

The Makefile automatically detects the environment:

| Environment | Description                                 |
| ----------- | ------------------------------------------- |
| **dev**     | Local development using Docker + LocalStack |
| **snd**     | Shared/Cloud AWS environment                |

You can always override the environment:

```bash
make <target> MODE=dev
make <target> MODE=snd
```

---

# Quick Start

## First Time Setup

```bash
make bootstrap
```

Installs project dependencies and prepares the development environment.

---

# Check Active Environment

Before running anything:

```bash
make env-info
```

Example output:

```
ENV            dev
MODE           dev
FILES          both
REGION         us-east-1
LocalStack     yes
```

---

# Local Development (MODE=dev)

This mode uses:

- Docker
- PostgreSQL
- Redis
- LocalStack
- SAM CLI

No real AWS resources are used.

---

## Step 1 Build Docker Images

```bash
make docker-build MODE=dev
```

---

## Step 2 Start Containers

```bash
make docker-up MODE=dev
```

Verify:

```bash
make docker-ps MODE=dev
```

---

## Step 3 Apply Database Migrations

```bash
make alembic-upgrade
```

---

## Step 4 Build SAM Application

```bash
make cf-build MODE=dev
```

---

## Step 5 Deploy CloudFormation

```bash
make cf-deploy MODE=dev
```

---

## Step 6 Verify LocalStack Resources

List APIs

```bash
make ls-api
```

List Buckets

```bash
make ls-s3
```

List S3 Objects

```bash
make ls-s3-objects
```

---

## View Logs

Application logs

```bash
make docker-app-logs MODE=dev
```

---

## Open Shell Inside API Container

```bash
make docker-exec-app MODE=dev
```

---

## Stop Everything

```bash
make docker-down MODE=dev
```

---

## Clean Everything

Removes:

- Containers
- Volumes
- Networks
- Images

```bash
make docker-clean MODE=dev
```

---

## Hard Reset

Completely recreates LocalStack and deploys everything again.

```bash
make restart-hard MODE=dev
```

---

# Shared AWS Environment (MODE=snd)

Deploys to the shared AWS account.

Before deploying configure AWS credentials:

```bash
aws configure
```

Verify:

```bash
aws sts get-caller-identity
```

Build

```bash
make cf-build MODE=snd
```

Deploy

```bash
make cf-deploy MODE=snd
```

Check Stack

```bash
make cf-status MODE=snd
```

View Events

```bash
make cf-logs MODE=snd
```

Delete Stack

```bash
make cf-delete MODE=snd
```

---

# Database Migrations

Create migration

```bash
make alembic-revision msg="create users table"
```

Upgrade

```bash
make alembic-upgrade
```

Current Version

```bash
make alembic-current
```

History

```bash
make alembic-history
```

Rollback

```bash
make alembic-downgrade
```

---

# Code Quality

Lint

```bash
make lint
```

Format

```bash
make format
```

Type Check

```bash
make type-check
```

Run Pre-Commit

```bash
make pre-commit
```

Run Complete CI

```bash
make ci
```

---

# Run Test Suit

Run everything:

```
make test
```

Run all unit tests:

```
make test-unit
```

Run a package:

```
make test-unit TARGET=services
```

Run a sub-package:

```
make test-unit TARGET=services/chat
```

Run a single file:

```
make test-unit TARGET=tests/unit/services/test_user.py
```

or

```
make test-unit TARGET=services/test_user.py
```

Run a single test:

```
make test-path TARGET="tests/unit/services/test_user.py::test_create_user"
```

Run by keyword:

```
poetry run pytest tests/unit -k create_user -v
```

---

# Poetry Commands

Install Dependencies

```bash
make poetry-install
```

Update Dependencies

```bash
make poetry-update
```

Regenerate Lock File

```bash
make poetry-lock
```

Export requirements.txt

```bash
make poetry-export
```

---

# Troubleshooting

## PostgreSQL Version Error

```
database files are incompatible
```

Reset local volumes

```bash
make docker-clean MODE=dev
docker volume prune -f
make docker-up MODE=dev
```

---

## LocalStack Not Running

Check

```bash
make env-info
```

Expected

```
MODE=dev
LocalStack=yes
```

Restart

```bash
make restart-hard MODE=dev
```

---

## Port Already Allocated

Find process

```bash
sudo lsof -i :8001
```

or

```bash
docker ps
```

Stop the conflicting container or process.

---

## AWS Credentials Not Found

Configure credentials

```bash
aws configure
```

Verify

```bash
aws sts get-caller-identity
```

---

# Typical Daily Workflow

```bash
# Check environment
make env-info

# Start local infrastructure
make docker-up MODE=dev

# Apply database migrations
make alembic-upgrade

# Start development
make docker-app-logs MODE=dev
```

---

# Full Clean Rebuild

```bash
make docker-clean MODE=dev

make clean-local

make docker-build MODE=dev

make docker-up MODE=dev

make alembic-upgrade

make cf-build MODE=dev

make cf-deploy MODE=dev
```
