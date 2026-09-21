# ============================================================================
# Juris AI - Local Development Makefile
#
# Lives at the repo root, next to ./setup.sh, because it drives paths outside
# server/ (docker/, iac/). Run `make` from the repo root. Python-side tooling
# (poetry, alembic, pytest, ruff, sam, server/scripts) runs inside server/ via
# the IN_SERVER prefix below.
#
# Purpose:
#   - Manage local development using Floci, Docker, SAM, and Poetry
#   - Provide developer-friendly commands for setup, testing, deployment
#   - Keep workflows CI-friendly and reproducible
#
# Philosophy:
#   - Makefile is the entry point for build/test/quality/migrations/IaC
#   - Stack lifecycle (install/start/stop/reinstall/cleanup/uninstall of the
#     server, dependencies, observability and development stacks) is owned by
#     ./setup.sh -- this Makefile only builds, tests, migrates, deploys and
#     inspects the running stack
#   - Size/split policy: see CONTRIBUTING.md ("Splitting large scripts")
#   - Intent-based commands instead of raw CLI usage
#   - Safe defaults with override-friendly variables
#   - Auto-detects dev vs snd based on Floci health
#   - Every Docker stack is its own Compose project; the project name is the
#     top-level `name:` in each docker/**/docker-compose*.yml
# ============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ============================================================================
# Colors
# ============================================================================
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
WHITE  := $(shell tput -Txterm setaf 7)
CYAN   := $(shell tput -Txterm setaf 6)
RED    := $(shell tput -Txterm setaf 1)
BOLD   := $(shell tput bold)
RESET  := $(shell tput -Txterm sgr0)

# -------------------------------------------------
# Project
# -------------------------------------------------

PROJECT_ROOT := $(CURDIR)
SERVER_DIR   := $(PROJECT_ROOT)/server

# Prefix for every recipe line that must run with server/ as its working
# directory (poetry, alembic, pytest, ruff, mypy, sam, server/scripts).
IN_SERVER := cd $(SERVER_DIR) &&

PYTHONPATH := $(SERVER_DIR)/src

export PYTHONPATH

# ragas (imported transitively wherever rag.evaluation.faithfulness_backend
# is, regardless of which backend is selected) starts a background
# analytics thread + atexit network flush unless told not to -- this is
# ragas' own sanctioned opt-out (see ragas/_analytics.py). conftest.py
# sets this too (for non-Make pytest invocations); this covers every
# other target here (scripts/, etc.) that isn't routed through pytest.
RAGAS_DO_NOT_TRACK := true

export RAGAS_DO_NOT_TRACK


# ============================================================================
# Environment Detection
#
# Floci running  -> MODE=dev
# Floci not found -> MODE=snd
#
# Override:
#   make <target> MODE=dev
#   make <target> MODE=snd
# ============================================================================
FLOCI_HEALTH_URL := http://localhost:4566/_localstack/health

_FLOCI_UP := $(shell curl -sf --max-time 2 $(FLOCI_HEALTH_URL) > /dev/null 2>&1 && echo "yes" || echo "no")

ifndef MODE
  ifeq ($(_FLOCI_UP),yes)
    MODE := dev
  else
    MODE := snd
  endif
endif

# ============================================================================
# Terraform / IaC provider selection
#
# Only PROVIDER=aws has a real implementation today -- see
# iac/terraform/modules/*/gcp|azure/README.md for the not-yet-built
# contracts. Passing PROVIDER=gcp fails fast with a clear message via
# the provider_name variable's own validation block, not a Makefile
# guard, so the error is the same whether Terraform is invoked
# through make or directly.
# ============================================================================
PROVIDER ?= aws
TF_DIR   := iac/terraform

ifeq ($(MODE),dev)
  TFVARS := dev.floci.tfvars
else
  TFVARS := prod.$(PROVIDER).tfvars
endif

# ============================================================================
# Application / AWS Configuration
# ============================================================================
MAIN_STACK_NAME := juris-ai-service-main
ECS_STACK_NAME  := juris-ai-service-ecs

API_NAME := juris-ai-api-snd

AWS_REGION := us-east-1
ENDPOINT   := http://localhost:4566

MAIN_TEMPLATE  := iac/cloud/template.yaml
ECS_TEMPLATE   := iac/cloud/ecs-template.yaml
# Relative to server/, where `sam build` / `sam deploy` run (see IN_SERVER).
BUILD_TEMPLATE := .aws-sam/build/template.yaml

POETRY  := poetry
ALEMBIC := alembic

STACK_NAME :=
TEMPLATE  :=

STACK_DEPLOY := main

# ============================================================================
# Docker Configuration
# ============================================================================
# Project names come from `name:` in each compose file (single source of truth,
# shared with ./setup.sh); do not pass --project-name here.
DOCKER_COMPOSE := docker compose --env-file server/.env

SERVER_COMPOSE        := $(DOCKER_COMPOSE) -f docker/server/docker-compose.yml
OBSERVABILITY_COMPOSE := $(DOCKER_COMPOSE) -f docker/observability/docker-compose.yml
OLLAMA_COMPOSE        := $(DOCKER_COMPOSE) -f docker/development/docker-compose-llm.yml

# Compose service name (not container name) of the API.
API_SERVICE := api

TEST      ?=
S3_BUCKET ?= juris-ai-document-snd

# ============================================================================
# CloudFormation Template Selection
# ============================================================================
ifeq ($(STACK_DEPLOY),main)

  STACK_NAME := $(MAIN_STACK_NAME)-$(MODE)
  TEMPLATE   := $(MAIN_TEMPLATE)

else

  STACK_NAME := $(ECS_STACK_NAME)-$(MODE)
  TEMPLATE   := $(ECS_TEMPLATE)

endif

# ============================================================================
# AWS Environment
#
# dev:
#   Floci endpoint + dummy credentials
#
# snd:
#   Real AWS region
# ============================================================================
ifeq ($(MODE),dev)

  AWS_ENV := AWS_ACCESS_KEY_ID=test \
             AWS_SECRET_ACCESS_KEY=test \
             AWS_DEFAULT_REGION=$(AWS_REGION) \
             AWS_ENDPOINT_URL=$(ENDPOINT)

else

  AWS_ENV := AWS_DEFAULT_REGION=$(AWS_REGION)

endif

# ============================================================================
# Guards — prevent accidental cross-env ops
# ============================================================================

.PHONY: _require-dev

_require-dev:
	@if [ "$(MODE)" != "dev" ]; then \
	  echo "$(RED) This target requires MODE=dev$(RESET)"; \
	  exit 1; \
	fi; \
	if [ "$(_FLOCI_UP)" != "yes" ]; then \
	  echo "$(YELLOW)⚠ Floci is not running, but MODE=dev is forced$(RESET)"; \
	fi

.PHONY: _require-floci

# cf-deploy / iac-apply need Floci (not the API) when MODE=dev. This only
# checks -- Floci is started by ./setup.sh, never by this Makefile.
_require-floci:
	@if [ "$(MODE)" = "dev" ] && [ "$(_FLOCI_UP)" != "yes" ]; then \
	  echo "$(RED)Floci is not running. Start it with: ./setup.sh --install --dependency floci$(RESET)"; \
	  exit 1; \
	fi

.PHONY: _confirm-snd

_confirm-snd:
	@if [ "$(MODE)" = "snd" ]; then \
	  read -p "$(YELLOW)⚠  You are targeting the SND (real AWS) environment. Continue? [y/N] $(RESET)" and; \
	  [ "$$and" = "y" ] || exit 1; \
	fi

# ============================================================================
# API Gateway Auto-Discovery
# ============================================================================

define GET_API_ID
$(shell \
	$(AWS_ENV) aws apigateway get-rest-apis \
		--query "items[?name=='$(API_NAME)'].id | [0]" \
		--output text 2>/dev/null \
)
endef

define GET_API_KEY
$(shell \
	API_ID="$(call GET_API_ID)"; \
	USAGE_PLAN_ID=$$($(AWS_ENV) aws apigateway get-usage-plans \
		--query "items[?apiStages[?apiId=='$$API_ID']].id | [0]" \
		--output text 2>/dev/null); \
	API_KEY_ID=$$($(AWS_ENV) aws apigateway get-usage-plan-keys \
		--usage-plan-id $$USAGE_PLAN_ID \
		--query "items[0].id" \
		--output text 2>/dev/null); \
	$(AWS_ENV) aws apigateway get-api-key \
		--api-key $$API_KEY_ID \
		--include-value \
		--query "value" \
		--output text 2>/dev/null \
)
endef

API_ID  ?= $(call GET_API_ID)
API_KEY ?= $(call GET_API_KEY)

# ============================================================================
# Environment Information
# ============================================================================

.PHONY: env-info

env-info: ## Show active environment and resolved configuration
	@echo ''
	@echo '$(CYAN)$(BOLD)╔══════════════════════════════════════════════╗$(RESET)'
	@echo '$(CYAN)$(BOLD)║           Juris AI — Active Config           ║$(RESET)'
	@echo '$(CYAN)$(BOLD)╚══════════════════════════════════════════════╝$(RESET)'
	@echo ''

	@if [ "$(MODE)" = "dev" ]; then \
	  echo "  $(GREEN)ENV$(RESET)             dev  $(CYAN)(Floci — local)$(RESET)"; \
	else \
	  echo "  $(YELLOW)ENV$(RESET)             snd  $(RED)(real AWS — be careful)$(RESET)"; \
	fi

	@echo "  $(GREEN)MODE$(RESET)            $(MODE)"
	@echo "  $(GREEN)PROVIDER$(RESET)        $(PROVIDER)"
	@echo "  $(GREEN)REGION$(RESET)          $(AWS_REGION)"
	@echo "  $(GREEN)STACK$(RESET)           $(STACK_NAME)"
	@echo "  $(GREEN)TEMPLATE$(RESET)        $(TEMPLATE)"
	@echo "  $(GREEN)API_SERVICE$(RESET)     $(API_SERVICE)"
	@echo "  $(GREEN)S3_BUCKET$(RESET)       $(S3_BUCKET)"

	@if [ "$(MODE)" = "dev" ]; then \
	  echo "  $(GREEN)ENDPOINT$(RESET)        $(ENDPOINT)"; \
	fi

	@echo "  $(GREEN)Floci$(RESET)      $(_FLOCI_UP)"
	@echo ''
	@echo "  Override with: $(YELLOW)make <target> MODE=dev|snd$(RESET)"
	@echo ''

# ============================================================================
# Bootstrap
# ============================================================================

.PHONY: bootstrap

bootstrap:
	@chmod +x $(SERVER_DIR)/scripts/bash/bootstrap.sh
	@$(IN_SERVER) ./scripts/bash/bootstrap.sh

# ============================================================================
# Docker - Application
# ============================================================================

# Install/start/stop/reinstall of the API (and every other stack) is done by
# ./setup.sh, e.g. `./setup.sh --reinstall --bundle server`. The targets
# below only build, inspect, and attach to an already-running stack.
.PHONY: docker-build docker-app-logs docker-ps docker-exec-app

docker-build: ## Build application Docker images
	@$(SERVER_COMPOSE) build --no-cache

docker-app-logs: ## Follow application container logs
	@$(SERVER_COMPOSE) logs -f $(API_SERVICE)

docker-ps: ## Show application containers
	@$(SERVER_COMPOSE) ps

docker-exec-app: ## Open shell in application container
	@$(SERVER_COMPOSE) exec $(API_SERVICE) bash

# ============================================================================
# Docker - Observability Infrastructure
#
# Services:
#   - OpenTelemetry Collector
#   - Prometheus
#   - Grafana
#
# These services belong to the same Compose project but have
# an independent lifecycle, owned by ./setup.sh.
# ============================================================================

# Install/reinstall/cleanup/uninstall: ./setup.sh --install|--reinstall|--cleanup|--uninstall --bundle observability
.PHONY: infra-logs infra-ps

infra-logs: ## Follow observability infrastructure logs
	@$(OBSERVABILITY_COMPOSE) logs -f


infra-ps: ## Show observability infrastructure containers
	@$(OBSERVABILITY_COMPOSE) ps



# ============================================================================
# Docker - LLM Infrastructure
#
# Services:
#   - Ollama
#
# Ollama provides local LLM inference for Juris-AI.
# The LLM infrastructure has an independent lifecycle from the application,
# owned by ./setup.sh.
# ============================================================================

# Start/stop/reinstall: ./setup.sh --install|--reinstall --bundle development
# (starts Ollama and SearXNG). setup.sh does NOT pull the model -- run
# `make llm-pull` after it (also part of `make dev` / `make restart-hard`).
.PHONY: llm-pull llm-logs llm-ps

llm-pull: ## Pull the configured local LLM model into Ollama (idempotent, skips if already present)
	@$(IN_SERVER) scripts/bash/pull_ollama_models.sh


llm-logs: ## Follow Ollama LLM infrastructure logs
	@$(OLLAMA_COMPOSE) logs -f


llm-ps: ## Show Ollama LLM infrastructure container
	@$(OLLAMA_COMPOSE) ps



# ============================================================================
# Poetry / Python
# ============================================================================

.PHONY: poetry-install poetry-update poetry-lock \
        poetry-check poetry-show poetry-activate poetry-export

poetry-install: ## Install Python dependencies via Poetry
	@$(IN_SERVER) $(POETRY) install

poetry-update: ## Update Python dependencies via Poetry
	@$(IN_SERVER) $(POETRY) update

poetry-lock: ## Regenerate poetry.lock
	@$(IN_SERVER) $(POETRY) lock

poetry-check: ## Validate pyproject.toml
	@$(IN_SERVER) $(POETRY) check

poetry-show: ## Show dependency tree
	@$(IN_SERVER) $(POETRY) show --tree

poetry-activate: ## Activate Poetry virtual environment
	@$(IN_SERVER) VENV="$$(poetry env info --path)"; \
	echo "Activating $$VENV"; \
	exec bash --rcfile <(echo "source $$VENV/bin/activate")

poetry-export: ## Export main dependencies to requirements.txt
	@$(IN_SERVER) $(POETRY) export \
	  --only main \
	  -f requirements.txt \
	  -o src/requirements.txt

# ============================================================================
# Code Quality
# ============================================================================

.PHONY: lint format type-check ci pre-commit install-hooks

lint: ## Run Ruff linter
	@echo '$(CYAN)Running linter...$(RESET)'
	@$(IN_SERVER) $(POETRY) run ruff check .
	@echo '$(GREEN)Linting passed$(RESET)'

format: ## Format code and run pre-commit hooks
	@echo '$(CYAN)Running auto-formatters...$(RESET)'
	@$(IN_SERVER) $(POETRY) run ruff check . --fix
	@$(IN_SERVER) $(POETRY) run ruff format .
	@$(IN_SERVER) $(POETRY) run pre-commit run -c $(PROJECT_ROOT)/.pre-commit-config.yaml --all-files
	@echo '$(GREEN)Auto-formatting complete$(RESET)'

type-check: ## Run mypy type checker
	@echo '$(CYAN)Running type checks...$(RESET)'
	@$(IN_SERVER) $(POETRY) run mypy src/
	@echo '$(GREEN)Type checking passed$(RESET)'

ci: ## Run lint, type-check, and tests
	@echo '$(CYAN)Running CI pipeline...$(RESET)'
	@$(MAKE) lint
	@$(MAKE) type-check
	@$(MAKE) test
	@echo '$(GREEN)CI pipeline passed$(RESET)'

pre-commit: ## Run pre-commit hooks
	@echo '$(CYAN)Running pre-commit hooks...$(RESET)'
	@$(IN_SERVER) $(POETRY) run pre-commit run -c $(PROJECT_ROOT)/.pre-commit-config.yaml --all-files
	@echo '$(GREEN)Pre-commit hooks passed$(RESET)'

install-hooks: ## Install pre-commit git hooks
	@$(IN_SERVER) $(POETRY) run pre-commit install -c $(PROJECT_ROOT)/.pre-commit-config.yaml

# ============================================================================
# Alembic / Database Migrations
# ============================================================================

.PHONY: alembic-upgrade alembic-downgrade alembic-current \
        alembic-history alembic-heads alembic-stamp alembic-revision

alembic-upgrade: ## Apply all pending Alembic migrations
	@$(IN_SERVER) $(POETRY) run $(ALEMBIC) upgrade head

alembic-downgrade: ## Rollback last Alembic migration (prompts for confirmation)
	@read -p "$(YELLOW)⚠  Downgrade database? [y/N] $(RESET)" and; \
	[ "$$and" = "y" ] || exit 1
	@$(IN_SERVER) $(POETRY) run $(ALEMBIC) downgrade -1

alembic-current: ## Show current Alembic revision
	@$(IN_SERVER) $(POETRY) run $(ALEMBIC) current

alembic-history: ## Show Alembic migration history
	@$(IN_SERVER) $(POETRY) run $(ALEMBIC) history

alembic-heads: ## Show current Alembic heads
	@$(IN_SERVER) $(POETRY) run $(ALEMBIC) heads

alembic-stamp: ## Stamp database to a revision [rev=<rev|head>]
ifndef rev
	$(error Usage: make alembic-stamp rev=head)
endif
	@$(IN_SERVER) $(POETRY) run $(ALEMBIC) stamp $(rev)

alembic-revision: ## Create autogenerated Alembic revision [msg="..."]
ifndef msg
	$(error Usage: make alembic-revision msg="add stations table")
endif
	@$(IN_SERVER) $(POETRY) run $(ALEMBIC) revision \
	  --autogenerate \
	  -m "$(msg)"

# ============================================================================
# Local dev DB role separation
# ============================================================================

.PHONY: db-setup-role

db-setup-role: ## Create/sync the restricted local-dev runtime role (APP_DB_USER) -- safe to re-run, needed once per Postgres volume
	@chmod +x $(SERVER_DIR)/scripts/bash/setup_app_role.sh
	@$(IN_SERVER) ./scripts/bash/setup_app_role.sh

# ============================================================================
# Floci Resource Inspection
# ============================================================================

.PHONY: ls-s3 ls-api-id ls-api-key ls-api ls-resources ls-s3-objects

ls-s3: _require-dev ## List Floci S3 buckets
	@$(AWS_ENV) aws s3 ls

ls-api-id: _require-dev ## List Floci API Gateway REST APIs
	@$(AWS_ENV) aws apigateway get-rest-apis \
	  --query 'items[*].[name,id]' \
	  --output table

ls-api-key: _require-dev ## Show API key for configured API
	@API_ID=$$($(AWS_ENV) aws apigateway get-rest-apis \
	  --query "items[?name=='$(API_NAME)'].id | [0]" \
	  --output text); \
	USAGE_PLAN_ID=$$($(AWS_ENV) aws apigateway get-usage-plans \
	  --query "items[?apiStages[?apiId=='$$API_ID']].id | [0]" \
	  --output text); \
	API_KEY_ID=$$($(AWS_ENV) aws apigateway get-usage-plan-keys \
	  --usage-plan-id $$USAGE_PLAN_ID \
	  --query "items[0].id" \
	  --output text); \
	API_KEY_VALUE=$$($(AWS_ENV) aws apigateway get-api-key \
	  --api-key $$API_KEY_ID \
	  --include-value \
	  --query 'value' \
	  --output text); \
	BLUE='\033[34m'; \
	RESET='\033[0m'; \
	echo "+------------------------------------------------------------------------+"; \
	echo "|  API Key Lookup                                                        |"; \
	echo "+------------------------+-----------------------------------------------+"; \
	printf "|  %b%-20s%b  |  %b%-38s%b  |\n" \
	  "$$BLUE" "$(API_NAME)" "$$RESET" \
	  "$$BLUE" "$$API_KEY_VALUE" "$$RESET"; \
	echo "+------------------------+-----------------------------------------------+"

ls-api: ls-api-id ls-api-key ## List API IDs and keys

ls-resources: ls-s3 ls-api-id ## List Floci resources

ls-s3-objects: _require-dev ## List objects in S3_BUCKET [S3_BUCKET=<name>]
	@echo "$(CYAN)Listing objects in: $(S3_BUCKET)$(RESET)"
	@$(AWS_ENV) aws s3 ls s3://$(S3_BUCKET) --recursive

# ============================================================================
# CloudFormation / SAM
# ============================================================================

.PHONY: cf-build cf-deploy cf-status cf-logs cf-delete

cf-build: poetry-export ## Build SAM application
	@$(IN_SERVER) $(POETRY) run sam build \
	  --template-file $(PROJECT_ROOT)/$(TEMPLATE)

cf-deploy: _require-floci cf-build ## Build and deploy SAM stack
	@$(IN_SERVER) $(AWS_ENV) $(POETRY) run sam deploy \
	  --template-file $(BUILD_TEMPLATE) \
	  --stack-name $(STACK_NAME) \
	  --resolve-s3 \
	  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
	  --region $(AWS_REGION) \
	  --no-confirm-changeset \
	  --no-fail-on-empty-changeset

cf-status: ## Show CloudFormation stack status
	@$(AWS_ENV) aws cloudformation describe-stacks \
	  --stack-name $(STACK_NAME)

cf-logs: ## Show CloudFormation stack events
	@$(AWS_ENV) aws cloudformation describe-stack-events \
	  --stack-name $(STACK_NAME) \
	  --output table

cf-delete: ## Clean local SAM artifacts (does not delete the deployed stack)
	@echo "$(RED)Cleaning local SAM artifacts for stack: $(STACK_NAME)$(RESET)"
	@$(MAKE) clean-local || true

# ============================================================================
# Terraform / IaC (multi-cloud Phase 1 -- AWS only today)
# ============================================================================

.PHONY: iac-init iac-plan iac-apply iac-output iac-destroy

iac-init: ## Initialize the Terraform working directory
	@cd $(TF_DIR) && terraform init

iac-plan: iac-init ## Show the Terraform execution plan [PROVIDER=aws]
	@cd $(TF_DIR) && $(AWS_ENV) terraform plan \
	  -var-file=$(TFVARS) \
	  -var="provider_name=$(PROVIDER)"

iac-apply: _require-floci iac-init ## Apply the Terraform configuration [PROVIDER=aws]
	@cd $(TF_DIR) && $(AWS_ENV) terraform apply \
	  -var-file=$(TFVARS) \
	  -var="provider_name=$(PROVIDER)" \
	  -auto-approve

iac-output: ## Show Terraform outputs
	@cd $(TF_DIR) && terraform output

iac-destroy: ## Destroy Terraform-managed infrastructure [PROVIDER=aws]
	@cd $(TF_DIR) && $(AWS_ENV) terraform destroy \
	  -var-file=$(TFVARS) \
	  -var="provider_name=$(PROVIDER)" \
	  -auto-approve

# ============================================================================
# Testing
# ============================================================================

.PHONY: test test-unit test-integration test-smoke test-e2e \
        test-cov test-failed test-path test-watch

PYTEST := $(POETRY) run pytest

# Optional path/module selector
TARGET ?=

test: ## Run all tests [TARGET=<path>]
	@$(IN_SERVER) $(PYTEST) $(TARGET) -v -s

test-unit: ## Run unit tests [TARGET=<path>]
	@$(IN_SERVER) if [ -z "$(TARGET)" ]; then \
		$(PYTEST) tests/unit -v -s; \
	elif [ -e "$(TARGET)" ]; then \
		$(PYTEST) "$(TARGET)" -v -s; \
	else \
		$(PYTEST) "tests/unit/$(TARGET)" -v -s; \
	fi

test-integration: ## Run integration tests [TARGET=<path>]
	@$(IN_SERVER) if [ -z "$(TARGET)" ]; then \
		$(PYTEST) tests/integration -v; \
	elif [ -e "$(TARGET)" ]; then \
		$(PYTEST) "$(TARGET)" -v; \
	else \
		$(PYTEST) "tests/integration/$(TARGET)" -v; \
	fi

test-e2e: ## Run e2e tests [TARGET=<path>]
	@$(IN_SERVER) if [ -z "$(TARGET)" ]; then \
		$(PYTEST) tests/e2e -v; \
	elif [ -e "$(TARGET)" ]; then \
		$(PYTEST) "$(TARGET)" -v; \
	else \
		$(PYTEST) "tests/e2e/$(TARGET)" -v; \
	fi

test-smoke: ## Run smoke tests [TARGET=<path>]
	@$(IN_SERVER) if [ -z "$(TARGET)" ]; then \
		$(PYTEST) tests/smoke -v -s; \
	elif [ -e "$(TARGET)" ]; then \
		$(PYTEST) "$(TARGET)" -v -s; \
	else \
		$(PYTEST) "tests/smoke/$(TARGET)" -v -s; \
	fi

test-cov: ## Run unit tests with coverage [TARGET=<path>]
	@$(IN_SERVER) $(PYTEST) tests/unit$(if $(TARGET),/$(TARGET),) \
	  -v \
	  --cov=src \
	  --cov-report=term-missing \
	  --cov-report=html \
	  --cov-report=xml

test-failed: ## Re-run previously failed tests
	@$(IN_SERVER) $(PYTEST) --lf -v

test-path: ## Run any test path [TARGET=<path>]
ifndef TARGET
	$(error Usage: make test-path TARGET=<path>)
endif
	@$(IN_SERVER) $(PYTEST) "$(TARGET)" -v

test-watch: ## Watch unit tests [TARGET=<path>]
	@$(IN_SERVER) $(POETRY) run ptw \
	  $(if $(TARGET),$(TARGET),tests/unit)

# ============================================================================
# Local Cleanup / Reset
# ============================================================================

.PHONY: clean-local restart-hard

clean-local: ## Remove local SAM build artifacts
	@echo "$(CYAN)Cleaning SAM artifacts...$(RESET)"
	@rm -rf $(SERVER_DIR)/.aws-sam

restart-hard: ## Reset SAM artifacts and redo post-install steps (run setup.sh --reinstall --mode dev first)
	@echo "$(YELLOW)HARD RESET — SAM artifacts and post-install steps$(RESET)"
	@echo "   (stacks are ./setup.sh's job: run ./setup.sh --reinstall --mode dev first)"
	@echo ''
	@echo "1) Cleaning SAM artifacts..."
	@$(MAKE) clean-local || true
	@echo "2) Setting up local dev DB role separation..."
	@$(MAKE) db-setup-role
	@echo "3) Pulling the Ollama model..."
	@$(MAKE) llm-pull
	@echo "4) Applying database migrations..."
	@$(MAKE) alembic-upgrade
	@echo "5) Deploying SAM stack..."
	@$(MAKE) cf-deploy MODE=dev

# ============================================================================
# Development Mode
#
# Stack lifecycle is owned by ./setup.sh. Run
#   ./setup.sh --install --mode dev
# first; the targets below are the Makefile-native steps that follow it.
# ============================================================================

.PHONY: dev-build dev-deploy dev

dev-build: ## Build development SAM application
	@$(MAKE) cf-build MODE=dev

dev-deploy: ## Deploy development SAM stack
	@$(MAKE) cf-deploy MODE=dev

dev: ## Post-install dev steps (DB role, model pull, migrations, deploy) after setup.sh --install --mode dev
	@$(MAKE) db-setup-role
	@$(MAKE) llm-pull
	@$(MAKE) alembic-upgrade
	@$(MAKE) dev-deploy

# ===
# Utilities
# ===
.PHONY: project-tree

project-tree: ## Show current project directory
	$(IN_SERVER) tree -a -I '__pycache__|*.pyc|.git|.pytest_cache|.volumes|.venv|.vscode|.aws-sam|floci*|node_modules|htmlcov|*.egg-info|dist|build|.ruff_cache|.mypy_cache'

# ============================================================================
# Help
# ============================================================================

.PHONY: help

help: ## Show available Make targets
	@echo ''
	@echo '$(CYAN)$(BOLD)Juris AI — Make Targets$(RESET)'
	@echo ''

	@if [ "$(_FLOCI_UP)" = "yes" ]; then \
	  echo "  $(GREEN)Active env:$(RESET) $(BOLD)dev$(RESET)  (Floci detected)"; \
	else \
	  echo "  $(YELLOW)Active env:$(RESET) $(BOLD)snd$(RESET)  (Floci not detected)"; \
	fi

	@echo "  Override: $(YELLOW)make <target> MODE=dev|snd$(RESET)"
	@echo ''
	@echo '$(YELLOW)Usage:$(RESET)'
	@echo '  $(GREEN)make <target>$(RESET) [MODE=dev|snd]'
	@echo ''

	@awk 'BEGIN {FS = ":.*?## "} \
	  /^## / { \
	    printf "\n$(CYAN)%s$(RESET)\n", substr($$0, 4) \
	  } \
	  /^[a-zA-Z_-]+:.*?##/ { \
	    printf "  $(YELLOW)%-22s$(RESET) %s\n", $$1, $$2 \
	  }' $(MAKEFILE_LIST)

	@echo ''
	@echo '$(YELLOW)Stack lifecycle is not a make target - use ./setup.sh:$(RESET)'
	@echo '  ./setup.sh --install   --dependency postgres|redis|floci'
	@echo '  ./setup.sh --install   --bundle server|observability|development'
	@echo '  ./setup.sh --reinstall --bundle <bundle>   (recreate; server = rebuild + restart)'
	@echo '  ./setup.sh --cleanup   --bundle <bundle>   (stop, keep data)'
	@echo '  ./setup.sh --uninstall --bundle <bundle>   (also removes data; destructive, asks to confirm)'
	@echo '  ./setup.sh --help'
	@echo '  Then: make db-setup-role, make llm-pull, make alembic-upgrade (or make dev)'
	@echo ''
	@echo "  Run $(GREEN)make env-info$(RESET) to see resolved configuration."
	@echo ''
