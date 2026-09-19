# ============================================================================
# Juris AI - Local Development Makefile
#
# Purpose:
#   - Manage local development using Floci, Docker, SAM, and Poetry
#   - Provide developer-friendly commands for setup, testing, deployment
#   - Keep workflows CI-friendly and reproducible
#
# Philosophy:
#   - Makefile is the single entry point
#   - Intent-based commands instead of raw CLI usage
#   - Safe defaults with override-friendly variables
#   - Auto-detects dev vs snd based on Floci health
#   - Application and observability use the same Docker Compose project
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
PYTHONPATH := $(PROJECT_ROOT)/src

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
# Compose File Selection
#
# dev:
#   FILES=main  -> application only
#   FILES=both  -> application + Floci
#   FILES=local -> Floci only
#
# snd:
#   main application compose
# ============================================================================
ifndef FILES
  ifeq ($(MODE),dev)
    FILES := both
  else
    FILES := main
  endif
endif

# ============================================================================
# Terraform / IaC provider selection
#
# Only PROVIDER=aws has a real implementation today -- see
# ../iac/terraform/modules/*/gcp|azure/README.md for the not-yet-built
# contracts. Passing PROVIDER=gcp fails fast with a clear message via
# the provider_name variable's own validation block, not a Makefile
# guard, so the error is the same whether Terraform is invoked
# through make or directly.
# ============================================================================
PROVIDER ?= aws
TF_DIR   := ../iac/terraform

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

MAIN_TEMPLATE  := ../iac/cloud/template.yaml
ECS_TEMPLATE   := ../iac/cloud/ecs-template.yaml
BUILD_TEMPLATE := .aws-sam/build/template.yaml

POETRY  := poetry
ALEMBIC := alembic

STACK_NAME :=
TEMPLATE  :=

STACK_DEPLOY := main

# ============================================================================
# Docker Configuration
# ============================================================================
DOCKER_COMPOSE := docker compose \
	--env-file .env

DOCKER_COMPOSE_MAIN_FILE       := ../docker/server/docker-compose.yml
DOCKER_COMPOSE_FLOCI_FILE      := ../docker/dependencies/docker-compose-floci.yml
DOCKER_COMPOSE_POSTGRES_FILE   := ../docker/dependencies/docker-compose-postgres.yml
DOCKER_COMPOSE_REDIS_FILE      := ../docker/dependencies/docker-compose-redis.yml
DOCKER_COMPOSE_INFRA_FILE      := ../docker/observability/docker-compose.yml
DOCKER_COMPOSE_LLM_FILE        := ../docker/development/docker-compose-llm.yml
DOCKER_COMPOSE_SEARCHXNG_FILE  := ../docker/development/docker-compose-searxng.yml

# Compose projects are intentionally independent.
#
# Each Compose file has its own project name so starting/stopping one
# stack never removes containers from another stack.
SERVER_PROJECT_NAME       := juris-ai-server
FLOCI_PROJECT_NAME        := juris-ai-floci
POSTGRES_PROJECT_NAME     := juris-ai-postgres
REDIS_PROJECT_NAME        := juris-ai-redis
OBSERVABILITY_PROJECT_NAME := juris-ai-observability
OLLAMA_PROJECT_NAME       := juris-ai-ollama
SEARXNG_PROJECT_NAME      := juris-ai-searxng

SERVER_COMPOSE       := $(DOCKER_COMPOSE) --project-name $(SERVER_PROJECT_NAME) -f $(DOCKER_COMPOSE_MAIN_FILE)
FLOCI_COMPOSE        := $(DOCKER_COMPOSE) --project-name $(FLOCI_PROJECT_NAME) -f $(DOCKER_COMPOSE_FLOCI_FILE)
POSTGRES_COMPOSE     := $(DOCKER_COMPOSE) --project-name $(POSTGRES_PROJECT_NAME) -f $(DOCKER_COMPOSE_POSTGRES_FILE)
REDIS_COMPOSE        := $(DOCKER_COMPOSE) --project-name $(REDIS_PROJECT_NAME) -f $(DOCKER_COMPOSE_REDIS_FILE)
OBSERVABILITY_COMPOSE := $(DOCKER_COMPOSE) --project-name $(OBSERVABILITY_PROJECT_NAME) -f $(DOCKER_COMPOSE_INFRA_FILE)
OLLAMA_COMPOSE       := $(DOCKER_COMPOSE) --project-name $(OLLAMA_PROJECT_NAME) -f $(DOCKER_COMPOSE_LLM_FILE)
SEARXNG_COMPOSE      := $(DOCKER_COMPOSE) --project-name $(SEARXNG_PROJECT_NAME) -f $(DOCKER_COMPOSE_SEARCHXNG_FILE)

VOLUMES_DIR := ../docker/.volumes

FLOCI_APP_CONTAINER := floci
API_APP_CONTAINER   := api

# Default values (safe fallback)
COMPOSE_FILES  :=
APP_CONTAINERS :=

TEST      ?=
S3_BUCKET ?= juris-ai-document-snd

# ============================================================================
# Application Compose Selection
#
# The server Compose file is API-only. Dependencies and development
# infrastructure have independent Compose projects/lifecycles.
# ============================================================================
COMPOSE_FILES  := -f $(DOCKER_COMPOSE_MAIN_FILE)
APP_CONTAINERS := $(API_APP_CONTAINER)

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
	@echo "  $(GREEN)FILES$(RESET)           $(FILES)"
	@echo "  $(GREEN)PROVIDER$(RESET)        $(PROVIDER)"
	@echo "  $(GREEN)REGION$(RESET)          $(AWS_REGION)"
	@echo "  $(GREEN)STACK$(RESET)           $(STACK_NAME)"
	@echo "  $(GREEN)TEMPLATE$(RESET)        $(TEMPLATE)"
	@echo "  $(GREEN)SERVER_COMPOSE$(RESET)  $(DOCKER_COMPOSE_MAIN_FILE)"
	@echo "  $(GREEN)APP_CONTAINERS$(RESET)  $(APP_CONTAINERS)"
	@echo "  $(GREEN)S3_BUCKET$(RESET)       $(S3_BUCKET)"

	@if [ "$(MODE)" = "dev" ]; then \
	  echo "  $(GREEN)ENDPOINT$(RESET)        $(ENDPOINT)"; \
	fi

	@echo "  $(GREEN)Floci$(RESET)      $(_FLOCI_UP)"
	@echo ''
	@echo "  Override with: $(YELLOW)make <target> MODE=dev|snd FILES=main|both|local$(RESET)"
	@echo ''

# ============================================================================
# Bootstrap
# ============================================================================

.PHONY: bootstrap

bootstrap:
	@chmod +x scripts/bash/bootstrap.sh
	@./scripts/bash/bootstrap.sh

# ============================================================================
# Docker - Application
# ============================================================================

.PHONY: docker-networks docker-build docker-up docker-down \
        docker-restart docker-app-logs docker-ps docker-exec-app docker-clean

docker-networks: ## Create shared Docker network
	@docker network inspect juris_ai_network >/dev/null 2>&1 \
	  || docker network create juris_ai_network

docker-build: ## Build application Docker images
	@$(SERVER_COMPOSE) build --no-cache

docker-up: docker-networks ## Start application Docker services
	@$(SERVER_COMPOSE) up -d

docker-down: ## Stop application Docker services
	@$(SERVER_COMPOSE) down

docker-restart: ## Rebuild and restart application services
	@$(SERVER_COMPOSE) down
	@$(SERVER_COMPOSE) up -d --build

docker-app-logs: ## Follow application container logs
	@$(SERVER_COMPOSE) logs -f $(APP_CONTAINERS)

docker-ps: ## Show application containers
	@$(SERVER_COMPOSE) ps

docker-exec-app: ## Open shell in application container
	@$(SERVER_COMPOSE) exec $(APP_CONTAINERS) bash

docker-clean: ## Remove application containers and local Docker resources
	@$(SERVER_COMPOSE) down --remove-orphans
	@$(FLOCI_COMPOSE) down --remove-orphans
	@$(POSTGRES_COMPOSE) down --remove-orphans
	@$(REDIS_COMPOSE) down --remove-orphans
	@$(OBSERVABILITY_COMPOSE) down --remove-orphans
	@$(OLLAMA_COMPOSE) down --remove-orphans
	@$(SEARXNG_COMPOSE) down --remove-orphans

# ============================================================================
# Docker - Observability Infrastructure
#
# Services:
#   - OpenTelemetry Collector
#   - Prometheus
#   - Grafana
#
# These services belong to the same Compose project but have
# an independent lifecycle.
# ============================================================================

.PHONY: infra-build infra-up infra-down infra-restart infra-logs infra-ps infra-volumes

infra-volumes:
	@mkdir -p $(VOLUMES_DIR)/prometheus $(VOLUMES_DIR)/tempo $(VOLUMES_DIR)/grafana


infra-build: docker-networks ## Pull observability infrastructure images
	@$(OBSERVABILITY_COMPOSE) pull


infra-up: docker-networks infra-volumes ## Start OpenTelemetry, Prometheus, Grafana, and Tempo
	@$(OBSERVABILITY_COMPOSE) up -d


infra-down: ## Stop observability infrastructure
	@$(OBSERVABILITY_COMPOSE) down


infra-restart: ## Restart observability infrastructure
	@$(OBSERVABILITY_COMPOSE) restart


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
# The LLM infrastructure has an independent lifecycle from the application.
# ============================================================================

.PHONY: llm-build llm-up llm-down llm-restart llm-logs llm-ps llm-pull ollama-setup

llm-build: docker-networks ## Pull LLM infrastructure images
	@$(OLLAMA_COMPOSE) pull


llm-up: docker-networks ## Start Ollama and ensure the configured model is available
	@$(OLLAMA_COMPOSE) up -d --force-recreate
	@$(MAKE) llm-pull


llm-pull: ## Pull the configured local LLM model into Ollama (idempotent, skips if already present)
	@scripts/bash/pull_ollama_models.sh

ollama-setup: ## Start Ollama and ensure the configured model is pulled -- same idempotent pattern as db-setup-role
	@$(MAKE) llm-up

llm-down: ## Stop Ollama LLM infrastructure
	@$(OLLAMA_COMPOSE) down


llm-restart: ## Restart Ollama LLM infrastructure
	@$(OLLAMA_COMPOSE) restart


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
	@$(POETRY) install

poetry-update: ## Update Python dependencies via Poetry
	@$(POETRY) update

poetry-lock: ## Regenerate poetry.lock
	@$(POETRY) lock

poetry-check: ## Validate pyproject.toml
	@$(POETRY) check

poetry-show: ## Show dependency tree
	@$(POETRY) show --tree

poetry-activate: ## Activate Poetry virtual environment
	@VENV="$$(poetry env info --path)"; \
	echo "Activating $$VENV"; \
	exec bash --rcfile <(echo "source $$VENV/bin/activate")

poetry-export: ## Export main dependencies to requirements.txt
	@$(POETRY) export \
	  --only main \
	  -f requirements.txt \
	  -o src/requirements.txt

# ============================================================================
# Code Quality
# ============================================================================

.PHONY: lint format type-check ci pre-commit install-hooks

lint: ## Run Ruff linter
	@echo '$(CYAN)Running linter...$(RESET)'
	@$(POETRY) run ruff check .
	@echo '$(GREEN)Linting passed$(RESET)'

format: ## Format code and run pre-commit hooks
	@echo '$(CYAN)Running auto-formatters...$(RESET)'
	@$(POETRY) run ruff check . --fix
	@$(POETRY) run ruff format .
	@$(POETRY) run pre-commit run -c ../.pre-commit-config.yaml --all-files
	@echo '$(GREEN)Auto-formatting complete$(RESET)'

type-check: ## Run mypy type checker
	@echo '$(CYAN)Running type checks...$(RESET)'
	@$(POETRY) run mypy src/
	@echo '$(GREEN)Type checking passed$(RESET)'

ci: ## Run lint, type-check, and tests
	@echo '$(CYAN)Running CI pipeline...$(RESET)'
	@$(MAKE) lint
	@$(MAKE) type-check
	@$(MAKE) test
	@echo '$(GREEN)CI pipeline passed$(RESET)'

pre-commit: ## Run pre-commit hooks
	@echo '$(CYAN)Running pre-commit hooks...$(RESET)'
	@$(POETRY) run pre-commit run -c ../.pre-commit-config.yaml --all-files
	@echo '$(GREEN)Pre-commit hooks passed$(RESET)'

install-hooks: ## Install pre-commit git hooks
	@$(POETRY) run pre-commit install -c ../.pre-commit-config.yaml

# ============================================================================
# Alembic / Database Migrations
# ============================================================================

.PHONY: alembic-upgrade alembic-downgrade alembic-current \
        alembic-history alembic-heads alembic-stamp alembic-revision

alembic-upgrade: ## Apply all pending Alembic migrations
	@$(POETRY) run $(ALEMBIC) upgrade head

alembic-downgrade: ## Rollback last Alembic migration (prompts for confirmation)
	@read -p "$(YELLOW)⚠  Downgrade database? [y/N] $(RESET)" and; \
	[ "$$and" = "y" ] || exit 1
	@$(POETRY) run $(ALEMBIC) downgrade -1

alembic-current: ## Show current Alembic revision
	@$(POETRY) run $(ALEMBIC) current

alembic-history: ## Show Alembic migration history
	@$(POETRY) run $(ALEMBIC) history

alembic-heads: ## Show current Alembic heads
	@$(POETRY) run $(ALEMBIC) heads

alembic-stamp: ## Stamp database to a revision [rev=<rev|head>]
ifndef rev
	$(error Usage: make alembic-stamp rev=head)
endif
	@$(POETRY) run $(ALEMBIC) stamp $(rev)

alembic-revision: ## Create autogenerated Alembic revision [msg="..."]
ifndef msg
	$(error Usage: make alembic-revision msg="add stations table")
endif
	@$(POETRY) run $(ALEMBIC) revision \
	  --autogenerate \
	  -m "$(msg)"

# ============================================================================
# Local dev DB role separation
# ============================================================================

.PHONY: db-setup-role

db-setup-role: ## Create/sync the restricted local-dev runtime role (APP_DB_USER) -- safe to re-run, needed once per Postgres volume
	@chmod +x scripts/bash/setup_app_role.sh
	@./scripts/bash/setup_app_role.sh

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
	@$(POETRY) run sam build \
	  --template-file $(TEMPLATE)

cf-deploy: docker-up cf-build ## Build and deploy SAM stack
	@$(AWS_ENV) $(POETRY) run sam deploy \
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

cf-delete: ## Clean local Docker/SAM resources
	@echo "$(RED)Cleaning local resources for stack: $(STACK_NAME)$(RESET)"
	@$(MAKE) docker-clean || true
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

iac-apply: docker-up iac-init ## Apply the Terraform configuration [PROVIDER=aws]
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
	@$(PYTEST) $(TARGET) -v -s

test-unit: ## Run unit tests [TARGET=<path>]
	@if [ -z "$(TARGET)" ]; then \
		$(PYTEST) tests/unit -v -s; \
	elif [ -e "$(TARGET)" ]; then \
		$(PYTEST) "$(TARGET)" -v -s; \
	else \
		$(PYTEST) "tests/unit/$(TARGET)" -v -s; \
	fi

test-integration: ## Run integration tests [TARGET=<path>]
	@if [ -z "$(TARGET)" ]; then \
		$(PYTEST) tests/integration -v; \
	elif [ -e "$(TARGET)" ]; then \
		$(PYTEST) "$(TARGET)" -v; \
	else \
		$(PYTEST) "tests/integration/$(TARGET)" -v; \
	fi

test-e2e: ## Run e2e tests [TARGET=<path>]
	@if [ -z "$(TARGET)" ]; then \
		$(PYTEST) tests/e2e -v; \
	elif [ -e "$(TARGET)" ]; then \
		$(PYTEST) "$(TARGET)" -v; \
	else \
		$(PYTEST) "tests/e2e/$(TARGET)" -v; \
	fi

test-smoke: ## Run smoke tests [TARGET=<path>]
	@if [ -z "$(TARGET)" ]; then \
		$(PYTEST) tests/smoke -v -s; \
	elif [ -e "$(TARGET)" ]; then \
		$(PYTEST) "$(TARGET)" -v -s; \
	else \
		$(PYTEST) "tests/smoke/$(TARGET)" -v -s; \
	fi

test-cov: ## Run unit tests with coverage [TARGET=<path>]
	@$(PYTEST) tests/unit$(if $(TARGET),/$(TARGET),) \
	  -v \
	  --cov=src \
	  --cov-report=term-missing \
	  --cov-report=html \
	  --cov-report=xml

test-failed: ## Re-run previously failed tests
	@$(PYTEST) --lf -v

test-path: ## Run any test path [TARGET=<path>]
ifndef TARGET
	$(error Usage: make test-path TARGET=<path>)
endif
	@$(PYTEST) "$(TARGET)" -v

test-watch: ## Watch unit tests [TARGET=<path>]
	@$(POETRY) run ptw \
	  $(if $(TARGET),$(TARGET),tests/unit)

# ============================================================================
# Local Cleanup / Reset
# ============================================================================

.PHONY: clean-local restart-hard

clean-local: ## Remove SAM artifacts and Floci persistent data
	@echo "$(CYAN)Cleaning SAM artifacts and Floci data...$(RESET)"
	@rm -rf .aws-sam
	@docker run --rm \
	  -v "$$(pwd)/../docker/.volumes/floci:/data" \
	  alpine \
	  sh -c "rm -rf /data/*"

restart-hard: ## Wipe local environment and redeploy
	@echo "$(YELLOW)HARD RESET — wiping local environment$(RESET)"
	@echo ''
	@echo "1) Stopping Docker services..."
	@$(MAKE) docker-clean || true
	@echo "2) Cleaning Floci persistent data..."
	@$(MAKE) clean-local || true
	@echo "3) Starting application services..."
	@$(MAKE) docker-up MODE=dev
	@echo "4) Waiting for Floci..."
	@sleep 10
	@echo "5) Starting observability..."
	@$(MAKE) infra-up MODE=dev
	@echo "6) Setting up local dev DB role separation..."
	@$(MAKE) db-setup-role
	@echo "7) Setting up Ollama local model..."
	@$(MAKE) ollama-setup
	@echo "8) Applying database migrations..."
	@$(MAKE) alembic-upgrade
	@echo "9) Deploying SAM stack..."
	@$(MAKE) cf-deploy MODE=dev

# ============================================================================
# Development Mode
# ============================================================================

.PHONY: dev-start dev-build dev-deploy dev

dev-start: ## Start development Docker services
	@$(MAKE) docker-up MODE=dev

dev-build: ## Build development SAM application
	@$(MAKE) cf-build MODE=dev

dev-deploy: ## Deploy development SAM stack
	@$(MAKE) cf-deploy MODE=dev

dev: ## Start complete local development environment
	@$(MAKE) dev-start
	@$(MAKE) infra-up MODE=dev
	@$(MAKE) db-setup-role
	@$(MAKE) ollama-setup
	@$(MAKE) alembic-upgrade
	@$(MAKE) dev-deploy

# ===
# Utilities
# ===
.PHONY: project-tree

project-tree: ## Show current project directory
	tree -a -I '__pycache__|*.pyc|.git|.pytest_cache|.volumes|.venv|.vscode|.aws-sam|floci*|node_modules|htmlcov|*.egg-info|dist|build|.ruff_cache|.mypy_cache'

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

	@echo "  Override: $(YELLOW)make <target> MODE=dev|snd FILES=main|both|local$(RESET)"
	@echo ''
	@echo '$(YELLOW)Usage:$(RESET)'
	@echo '  $(GREEN)make <target>$(RESET) [MODE=dev|snd] [FILES=main|both|local]'
	@echo ''

	@awk 'BEGIN {FS = ":.*?## "} \
	  /^## / { \
	    printf "\n$(CYAN)%s$(RESET)\n", substr($$0, 4) \
	  } \
	  /^[a-zA-Z_-]+:.*?##/ { \
	    printf "  $(YELLOW)%-22s$(RESET) %s\n", $$1, $$2 \
	  }' $(MAKEFILE_LIST)

	@echo ''
	@echo "  Run $(GREEN)make env-info$(RESET) to see resolved configuration."
	@echo ''
