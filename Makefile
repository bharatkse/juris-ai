# ============================================================================
# Juris AI - Local Development Makefile
#
# Purpose:
#   - Manage local development using LocalStack, Docker, SAM, and Poetry
#   - Provide developer-friendly commands for setup, testing, deployment
#   - Keep workflows CI-friendly and reproducible
#
# Philosophy:
#   - Makefile is the single entry point
#   - Intent-based commands instead of raw CLI usage
#   - Safe defaults with override-friendly variables
#   - Auto-detects dev vs snd based on LocalStack health
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

# ============================================================================
# Environment Detection
#
# LocalStack running  -> MODE=dev
# LocalStack not found -> MODE=snd
#
# Override:
#   make <target> MODE=dev
#   make <target> MODE=snd
# ============================================================================
LOCALSTACK_HEALTH_URL := http://localhost:4566/_localstack/health

_LOCALSTACK_UP := $(shell curl -sf --max-time 2 $(LOCALSTACK_HEALTH_URL) > /dev/null 2>&1 && echo "yes" || echo "no")

ifndef MODE
  ifeq ($(_LOCALSTACK_UP),yes)
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
#   FILES=both  -> application + LocalStack
#   FILES=local -> LocalStack only
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
# Application / AWS Configuration
# ============================================================================
MAIN_STACK_NAME := juris-ai-service-main
ECS_STACK_NAME  := juris-ai-service-ecs

API_NAME := juris-ai-api-snd

AWS_REGION := us-east-1
ENDPOINT   := http://localhost:4566

MAIN_TEMPLATE  := infrastructure/cf_templates/template.yaml
ECS_TEMPLATE   := infrastructure/cf_templates/ecs-template.yaml
BUILD_TEMPLATE := .aws-sam/build/template.yaml

POETRY  := poetry
ALEMBIC := alembic

STACK_NAME :=
TEMPLATE  :=

STACK_DEPLOY := main
LLM_MODEL ?= qwen3:4b

# ============================================================================
# Docker Configuration
# ============================================================================
DOCKER_PROJECT_NAME := juris-ai

DOCKER_COMPOSE := docker compose \
	--env-file .env \
	-p $(DOCKER_PROJECT_NAME)

DOCKER_COMPOSE_MAIN_FILE       := docker/docker-compose.yml
DOCKER_COMPOSE_LOCALSTACK_FILE := docker/docker-compose-localstack.yml
DOCKER_COMPOSE_INFRA_FILE      := docker/docker-compose-infra.yml
DOCKER_COMPOSE_LLM_FILE        := docker/docker-compose-llm.yml
DOCKER_COMPOSE_SEARCHXNG_FILE  := docker/docker-compose-searxng.yml

# Complete local Compose definition.
#
# Used when commands need awareness of every service in the same
# Compose project, especially observability commands, to avoid
# orphan-container warnings.
DOCKER_COMPOSE_ALL_FILES := \
	-f $(DOCKER_COMPOSE_MAIN_FILE) \
	-f $(DOCKER_COMPOSE_LOCALSTACK_FILE) \
	-f $(DOCKER_COMPOSE_INFRA_FILE) \
	-f $(DOCKER_COMPOSE_LLM_FILE) \
	-f $(DOCKER_COMPOSE_SEARCHXNG_FILE)

LOCALSTACK_APP_CONTAINER := localstack
API_APP_CONTAINER        := api

# Default values (safe fallback)
COMPOSE_FILES  :=
APP_CONTAINERS :=

TEST      ?=
S3_BUCKET ?= juris-ai-document-snd

# ============================================================================
# Mode + Files -> Application Compose Selection
# ============================================================================
ifeq ($(MODE),dev)
  ifeq ($(FILES),main)
    COMPOSE_FILES  := -f $(DOCKER_COMPOSE_MAIN_FILE)
    APP_CONTAINERS := $(API_APP_CONTAINER)
  else ifeq ($(FILES),both)
    COMPOSE_FILES  := -f $(DOCKER_COMPOSE_LOCALSTACK_FILE) -f $(DOCKER_COMPOSE_LLM_FILE) -f $(DOCKER_COMPOSE_MAIN_FILE) -f $(DOCKER_COMPOSE_SEARCHXNG_FILE)
    APP_CONTAINERS := $(API_APP_CONTAINER)
  else
	COMPOSE_FILES  := -f $(DOCKER_COMPOSE_LOCALSTACK_FILE)
	APP_CONTAINERS := $(LOCALSTACK_APP_CONTAINER)
  endif
else ifeq ($(MODE),snd)
  COMPOSE_FILES  := -f $(DOCKER_COMPOSE_MAIN_FILE)
  APP_CONTAINERS := $(API_APP_CONTAINER)
endif

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
#   LocalStack endpoint + dummy credentials
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
	if [ "$(_LOCALSTACK_UP)" != "yes" ]; then \
	  echo "$(YELLOW)⚠ LocalStack is not running, but MODE=dev is forced$(RESET)"; \
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
	  echo "  $(GREEN)ENV$(RESET)             dev  $(CYAN)(LocalStack — local)$(RESET)"; \
	else \
	  echo "  $(YELLOW)ENV$(RESET)             snd  $(RED)(real AWS — be careful)$(RESET)"; \
	fi

	@echo "  $(GREEN)MODE$(RESET)            $(MODE)"
	@echo "  $(GREEN)FILES$(RESET)           $(FILES)"
	@echo "  $(GREEN)REGION$(RESET)          $(AWS_REGION)"
	@echo "  $(GREEN)STACK$(RESET)           $(STACK_NAME)"
	@echo "  $(GREEN)TEMPLATE$(RESET)        $(TEMPLATE)"
	@echo "  $(GREEN)COMPOSE_FILES$(RESET)   $(COMPOSE_FILES)"
	@echo "  $(GREEN)APP_CONTAINERS$(RESET)  $(APP_CONTAINERS)"
	@echo "  $(GREEN)S3_BUCKET$(RESET)       $(S3_BUCKET)"

	@if [ "$(MODE)" = "dev" ]; then \
	  echo "  $(GREEN)ENDPOINT$(RESET)        $(ENDPOINT)"; \
	fi

	@echo "  $(GREEN)LocalStack$(RESET)      $(_LOCALSTACK_UP)"
	@echo ''
	@echo "  Override with: $(YELLOW)make <target> MODE=dev|snd FILES=main|both|local$(RESET)"
	@echo ''

# ============================================================================
# Bootstrap
# ============================================================================

.PHONY: bootstrap

bootstrap:
	@chmod +x scripts/bootstrap.sh
	@./scripts/bootstrap.sh

# ============================================================================
# Docker - Application
# ============================================================================

.PHONY: docker-networks docker-build docker-up docker-down \
        docker-restart docker-app-logs docker-ps docker-exec-app docker-clean

docker-networks: ## Create shared Docker network
	@docker network inspect juris_ai_network >/dev/null 2>&1 \
	  || docker network create juris_ai_network

docker-build: ## Build application Docker images
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) build

docker-up: docker-networks ## Start application Docker services
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) up -d

docker-down: ## Stop application Docker services
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) down

docker-restart: ## Rebuild and restart application services
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) down
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) up -d --build

docker-app-logs: ## Follow application container logs
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) logs -f $(APP_CONTAINERS)

docker-ps: ## Show application containers
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) ps

docker-exec-app: ## Open shell in application container
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) exec $(APP_CONTAINERS) bash

docker-clean: ## Remove all local Compose services, volumes, and images
	@$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_ALL_FILES) down \
	  --rmi local \
	  --volumes \
	  --remove-orphans
	@docker volume prune -f

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

.PHONY: infra-build infra-up infra-down infra-restart infra-logs infra-ps

infra-build: docker-networks ## Pull observability infrastructure images
	@$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_ALL_FILES) \
	  pull \
	  otel-collector \
	  prometheus \
	  grafana

infra-up: docker-networks ## Start OpenTelemetry, Prometheus, and Grafana
	@$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_ALL_FILES) \
	  up -d \
	  otel-collector \
	  prometheus \
	  grafana

infra-down: ## Stop OpenTelemetry, Prometheus, and Grafana
	@$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_ALL_FILES) \
	  stop \
	  otel-collector \
	  prometheus \
	  grafana

infra-restart: ## Restart OpenTelemetry, Prometheus, and Grafana
	@$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_ALL_FILES) \
	  restart \
	  otel-collector \
	  prometheus \
	  grafana

infra-logs: ## Follow observability infrastructure logs
	@$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_ALL_FILES) \
	  logs -f \
	  otel-collector \
	  prometheus \
	  grafana

infra-ps: ## Show observability infrastructure containers
	@$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_ALL_FILES) \
	  ps \
	  otel-collector \
	  prometheus \
	  grafana

# ============================================================================
# Docker - LLM Infrastructure
#
# Services:
#   - Ollama
#
# Ollama provides local LLM inference for Juris-AI.
# The LLM infrastructure has an independent lifecycle from the application.
# ============================================================================

.PHONY: llm-build llm-up llm-down llm-restart llm-logs llm-ps llm-pull

llm-build: docker-networks ## Pull LLM infrastructure images
	@$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_LLM_FILE) \
	  pull \
	  ollama

llm-up: docker-networks ## Start Ollama and ensure the configured model is available
	@$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_LLM_FILE) \
	  up -d \
	  ollama
	@$(MAKE) llm-pull

llm-pull: ## Pull the configured local LLM model into Ollama
	@echo "Pulling Ollama model: $(LLM_MODEL)"
	@docker exec juris_ai_ollama \
	  ollama pull $(LLM_MODEL)

llm-down: ## Stop Ollama LLM infrastructure
	@$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_LLM_FILE) \
	  stop \
	  ollama

llm-restart: ## Restart Ollama LLM infrastructure
	@$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_LLM_FILE) \
	  restart \
	  ollama

llm-logs: ## Follow Ollama LLM infrastructure logs
	@$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_LLM_FILE) \
	  logs -f \
	  ollama

llm-ps: ## Show Ollama LLM infrastructure container
	@$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_LLM_FILE) \
	  ps \
	  ollama

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
	@$(POETRY) run pre-commit run --all-files
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
	@$(POETRY) run pre-commit run --all-files
	@echo '$(GREEN)Pre-commit hooks passed$(RESET)'

install-hooks: ## Install pre-commit git hooks
	@$(POETRY) run pre-commit install

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
# LocalStack Resource Inspection
# ============================================================================

.PHONY: ls-s3 ls-api-id ls-api-key ls-api ls-resources ls-s3-objects

ls-s3: _require-dev ## List LocalStack S3 buckets
	@$(AWS_ENV) aws s3 ls

ls-api-id: _require-dev ## List LocalStack API Gateway REST APIs
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

ls-resources: ls-s3 ls-api-id ## List LocalStack resources

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
# Testing
# ============================================================================

.PHONY: test test-unit test-integration test-e2e \
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

clean-local: ## Remove SAM artifacts and LocalStack persistent data
	@echo "$(CYAN)Cleaning SAM artifacts and LocalStack data...$(RESET)"
	@rm -rf .aws-sam
	@docker run --rm \
	  -v "$$(pwd)/localstack-data:/var/lib/localstack" \
	  alpine \
	  sh -c "rm -rf /var/lib/localstack/*"

restart-hard: ## Wipe local environment and redeploy
	@echo "$(YELLOW)HARD RESET — wiping local environment$(RESET)"
	@echo ''
	@echo "1) Stopping Docker services..."
	@$(MAKE) docker-clean || true
	@echo "2) Cleaning LocalStack persistent data..."
	@$(MAKE) clean-local || true
	@echo "3) Starting application services..."
	@$(MAKE) docker-up MODE=dev
	@echo "4) Waiting for LocalStack..."
	@sleep 10
	@echo "5) Starting observability..."
	@$(MAKE) infra-up MODE=dev
	@echo "6) Applying database migrations..."
	@$(MAKE) alembic-upgrade
	@echo "7) Deploying SAM stack..."
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
	@$(MAKE) alembic-upgrade
	@$(MAKE) dev-deploy

# ===
# Utilities
# ===
.PHONY: project-tree

project-tree: ## Show current project directory
	tree -a -I '__pycache__|*.pyc|.git|.pytest_cache|.volumes|.venv|.vscode|.aws-sam|localstack*|node_modules|htmlcov|*.egg-info|dist|build|tests|.ruff_cache|.mypy_cache'

# ============================================================================
# Help
# ============================================================================

.PHONY: help

help: ## Show available Make targets
	@echo ''
	@echo '$(CYAN)$(BOLD)Juris AI — Make Targets$(RESET)'
	@echo ''

	@if [ "$(_LOCALSTACK_UP)" = "yes" ]; then \
	  echo "  $(GREEN)Active env:$(RESET) $(BOLD)dev$(RESET)  (LocalStack detected)"; \
	else \
	  echo "  $(YELLOW)Active env:$(RESET) $(BOLD)snd$(RESET)  (LocalStack not detected)"; \
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
