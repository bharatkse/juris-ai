# ============================================================================
# Juris AI - Local Development Makefile
#
# Purpose:
#   - Manage local development using LocalStack, SAM, and Poetry
#   - Provide developer-friendly commands for setup, testing, deployment
#   - Keep CI-friendly, reproducible workflows
#
# Philosophy:
#   - Makefile is the single entry point
#   - Intent-based commands (not raw AWS CLI usage)
#   - Safe defaults, override-friendly
#   - Auto-detects environment (dev vs snd) based on LocalStack health
# ============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ============================================
# Colors
# ============================================
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
WHITE  := $(shell tput -Txterm setaf 7)
CYAN   := $(shell tput -Txterm setaf 6)
RED    := $(shell tput -Txterm setaf 1)
BOLD   := $(shell tput bold)
RESET  := $(shell tput -Txterm sgr0)

# ============================================
# Auto-detect MODE unless explicitly set
#
#   Probes LocalStack health endpoint.
#   Override anytime: make <target> MODE=snd
# ============================================
LOCALSTACK_HEALTH_URL := http://localhost:4566/_localstack/health

_LOCALSTACK_UP := $(shell curl -sf --max-time 2 $(LOCALSTACK_HEALTH_URL) > /dev/null 2>&1 && echo "yes" || echo "no")

ifndef MODE
  ifeq ($(_LOCALSTACK_UP),yes)
    MODE := dev
  else
    MODE := snd
  endif
endif

# ============================================
# FILES default: follows MODE unless overridden
# ============================================
ifndef FILES
  ifeq ($(MODE),dev)
    FILES := both
  else
    FILES := main
  endif
endif

# ============================================
# Configuration
# ============================================
MAIN_STACK_NAME := juris-ai-service-main
ECS_STACK_NAME  := juris-ai-service-ecs

API_NAME   := juris-ai-api-snd

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

# ============================================
# Docker
# ============================================
DOCKER_PROJECT_NAME := juris-ai
DOCKER_COMPOSE      := docker compose --env-file .env -p $(DOCKER_PROJECT_NAME)

DOCKER_COMPOSE_MAIN_FILE       := docker/docker-compose.yml
DOCKER_COMPOSE_LOCALSTACK_FILE := docker/docker-compose-localstack.yml

LOCALSTACK_APP_CONTAINER := localstack
API_APP_CONTAINER        := api

# Default values (safe fallback)
COMPOSE_FILES   :=
APP_CONTAINERS  :=

TEST  ?=
S3_BUCKET ?= juris-ai-document-snd

# ============================================
# Mode + Files → compose file selection
# ============================================
ifeq ($(MODE),dev)
  ifeq ($(FILES),main)
    COMPOSE_FILES  := -f $(DOCKER_COMPOSE_MAIN_FILE)
    APP_CONTAINERS := $(API_APP_CONTAINER)
  else ifeq ($(FILES),both)
    COMPOSE_FILES  := -f $(DOCKER_COMPOSE_LOCALSTACK_FILE) -f $(DOCKER_COMPOSE_MAIN_FILE)
    APP_CONTAINERS := $(API_APP_CONTAINER)
  else
	COMPOSE_FILES  := -f $(DOCKER_COMPOSE_LOCALSTACK_FILE)
	APP_CONTAINERS := $(LOCALSTACK_APP_CONTAINER)
  endif
else ifeq ($(MODE),snd)
  COMPOSE_FILES  := -f $(DOCKER_COMPOSE_MAIN_FILE)
  APP_CONTAINERS := $(API_APP_CONTAINER)
endif

ifeq ($(STACK_DEPLOY),main)
  STACK_NAME := $(MAIN_STACK_NAME)-$(MODE)
  TEMPLATE  := $(MAIN_TEMPLATE)
else
  STACK_NAME := $(ECS_STACK_NAME)-$(MODE)
  TEMPLATE  := $(ECS_TEMPLATE)
endif

# ============================================
# AWS credentials
#   dev  → LocalStack dummy creds + local endpoint
#   snd  → real AWS profile; endpoint unset
# ============================================
ifeq ($(MODE),dev)
  AWS_ENV := AWS_ACCESS_KEY_ID=test \
             AWS_SECRET_ACCESS_KEY=test \
             AWS_DEFAULT_REGION=$(AWS_REGION) \
             AWS_ENDPOINT_URL=$(ENDPOINT)
else
  AWS_ENV := AWS_DEFAULT_REGION=$(AWS_REGION)
endif

# ============================================
# Guards — prevent accidental cross-env ops
# ============================================

# Abort if caller expects dev but LocalStack is down
.PHONY: _require-dev
_require-dev:
	@if [ "$(MODE)" != "dev" ]; then \
	  echo "$(RED) This target requires MODE=dev$(RESET)"; \
	  exit 1; \
	fi; \
	if [ "$(_LOCALSTACK_UP)" != "yes" ]; then \
	  echo "$(YELLOW)⚠ LocalStack is not running, but MODE=dev is forced$(RESET)"; \
	fi

# Confirm before touching real AWS
.PHONY: _confirm-snd
_confirm-snd:
	@if [ "$(MODE)" = "snd" ]; then \
	  read -p "$(YELLOW)⚠  You are targeting the SND (real AWS) environment. Continue? [y/N] $(RESET)" and; \
	  [ "$$and" = "y" ] || exit 1; \
	fi

# ============================================
# API Gateway Auto-Discovery (LocalStack)
# ============================================
define GET_API_ID
$(shell $(AWS_ENV) aws apigateway get-rest-apis \
  --query "items[?name=='$(API_NAME)'].id | [0]" \
  --output text 2>/dev/null)
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
# env-info — show resolved configuration at a glance
# ============================================================================
.PHONY: env-info
env-info: ## Show active environment, mode, and resolved config
	@echo ''
	@echo '$(CYAN)$(BOLD)╔══════════════════════════════════════════════╗$(RESET)'
	@echo '$(CYAN)$(BOLD)║           Juris AI — Active Config           ║$(RESET)'
	@echo '$(CYAN)$(BOLD)╚══════════════════════════════════════════════╝$(RESET)'
	@echo ''
	@if [ "$(MODE)" = "dev" ]; then \
	  echo "  $(GREEN) ENV$(RESET)            dev  $(CYAN)(LocalStack — local)$(RESET)"; \
	else \
	  echo "  $(YELLOW) ENV$(RESET)            snd  $(RED)(real AWS — be careful)$(RESET)"; \
	fi
	@echo "  $(GREEN) MODE$(RESET)           $(MODE)"
	@echo "  $(GREEN) ENV$(RESET)            $(ENV)"
	@echo "  $(GREEN) FILES$(RESET)          $(FILES)"
	@echo "  $(GREEN) REGION$(RESET)         $(AWS_REGION)"
	@echo "  $(GREEN) COMPOSE_FILES$(RESET)  $(COMPOSE_FILES)"
	@echo "  $(GREEN) APP_CONTAINERS$(RESET) $(APP_CONTAINERS)"
	@echo "  $(GREEN) S3_BUCKET$(RESET)      $(S3_BUCKET)"
	@if [ "$(MODE)" = "dev" ]; then \
	  echo "  $(GREEN) ENDPOINT$(RESET)       $(ENDPOINT)"; \
	fi
	@echo "  $(GREEN) LocalStack$(RESET)     $(_LOCALSTACK_UP)"
	@echo ''
	@echo "  Override with:  $(YELLOW)make <target> MODE=dev|snd FILES=local|both$(RESET)"
	@echo ''

# ============================================
# Bootstrap
# ============================================

bootstrap:
	@chmod +x scripts/bootstrap.sh
	@./scripts/bootstrap.sh

# ============================================
# Docker
# ============================================
.PHONY: docker-networks docker-build docker-up docker-down \
        docker-restart docker-app-logs docker-ps docker-exec-app docker-clean

docker-networks: ## Create Docker networks
	@docker network inspect juris_ai_network >/dev/null 2>&1 \
	  || docker network create juris_ai_network

docker-build: ## Build Docker images without starting containers
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) build

docker-up: docker-networks ## Start all Docker services (detached)
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) up -d

docker-down: ## Stop all Docker services
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) down

docker-restart: ## Rebuild and restart Docker services
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) down
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) up -d --build

docker-app-logs: ## Follow app container logs
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) logs -f $(APP_CONTAINERS)

docker-ps: ## Show running containers
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) ps

docker-exec-app: ## Open shell in app container
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) exec $(APP_CONTAINERS) bash

docker-clean: ## Remove containers, volumes, images, and networks
	@$(DOCKER_COMPOSE) $(COMPOSE_FILES) down --rmi local --volumes --remove-orphans
	@docker volume prune -f

# ============================================
# Poetry / Python
# ============================================
.PHONY: poetry-install poetry-update poetry-lock \
        poetry-check poetry-show poetry-activate

poetry-install: ## Install Python dependencies via Poetry
	@$(POETRY) install

poetry-update: ## Update Python dependencies via Poetry
	@$(POETRY) update

poetry-lock: ## Regenerate poetry.lock from pyproject.toml
	@poetry lock

poetry-check: ## Validate pyproject.toml configuration
	@poetry check

poetry-show: ## Show full dependency tree
	@poetry show --tree

poetry-activate: ## Activate Poetry virtual environment in current shell
	@VENV="$$(poetry env info --path)"; \
	echo "Activating $$VENV"; \
	exec bash --rcfile <(echo "source $$VENV/bin/activate")

poetry-export:
	@poetry export --only main -f requirements.txt -o src/requirements.txt

# ============================================
# Code Quality
# ============================================
.PHONY: lint format type-check ci install-hooks

lint: ## Run ruff linter
	@echo '$(CYAN)Running linter...$(RESET)'
	@poetry run ruff check .
	@echo '$(GREEN) Linting passed$(RESET)'

format: ## Auto-fix formatting and lint issues
	@echo '$(CYAN)Running auto-formatters...$(RESET)'
	@poetry run ruff check . --fix
	@poetry run ruff format .
	@poetry run pre-commit run --all-files
	@echo '$(GREEN) Auto-formatting complete$(RESET)'

type-check: ## Run mypy type checker
	@echo '$(CYAN)Running type checks...$(RESET)'
	@poetry run mypy src/
	@echo '$(GREEN) Type checking passed$(RESET)'

ci: ## Full CI pipeline: lint → type-check → test
	@echo '$(CYAN)Running CI pipeline...$(RESET)'
	@$(MAKE) lint
	@$(MAKE) type-check
	@$(MAKE) test
	@echo '$(GREEN) CI pipeline passed$(RESET)'

pre-commit: ## Run pre-commit hooks on all files
	@echo '$(CYAN)Running pre-commit hooks...$(RESET)'
	@poetry run pre-commit run --all-files
	@echo '$(GREEN) Pre-commit hooks passed$(RESET)'

install-hooks: ## Install pre-commit git hooks
	@echo '$(CYAN)Installing git hooks...$(RESET)'
	@poetry run pre-commit install
	@echo '$(GREEN) Git hooks installed$(RESET)'

# ============================================
# Alembic / Database Migrations
# ============================================
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

alembic-history: ## Show full Alembic migration history
	@$(POETRY) run $(ALEMBIC) history

alembic-heads: ## Show current Alembic heads (detects branch divergence)
	@$(POETRY) run $(ALEMBIC) heads

alembic-stamp: ## Stamp DB to a revision without running migrations  [rev=<rev|head>]
ifndef rev
	$(error Usage: make alembic-stamp rev=head)
endif
	@$(POETRY) run $(ALEMBIC) stamp $(rev)

alembic-revision: ## Create a new autogenerated Alembic revision  [msg="..."]
ifndef msg
	$(error Usage: make alembic-revision msg="add stations table")
endif
	@$(POETRY) run $(ALEMBIC) revision --autogenerate -m "$(msg)"

# ============================================================================
# LocalStack Resource Inspection  (dev only)
# ============================================================================
.PHONY: ls-s3 ls-api-id ls-api-key ls-api ls-resources ls-s3-objects

ls-s3: _require-dev ## List all S3 buckets (LocalStack)
	@$(AWS_ENV) aws s3 ls

ls-api-id: _require-dev ## List all API Gateway REST APIs (LocalStack)
	@$(AWS_ENV) aws apigateway get-rest-apis \
	  --query 'items[*].[name,id]' --output table

ls-api-key: _require-dev ## Show API key for configured API_NAME (LocalStack)
	@API_ID=$$($(AWS_ENV) aws apigateway get-rest-apis \
	  --query "items[?name=='$(API_NAME)'].id | [0]" --output text); \
	USAGE_PLAN_ID=$$($(AWS_ENV) aws apigateway get-usage-plans \
	  --query "items[?apiStages[?apiId=='$$API_ID']].id | [0]" --output text); \
	API_KEY_ID=$$($(AWS_ENV) aws apigateway get-usage-plan-keys \
	  --usage-plan-id $$USAGE_PLAN_ID --query "items[0].id" --output text); \
	API_KEY_VALUE=$$($(AWS_ENV) aws apigateway get-api-key \
	  --api-key $$API_KEY_ID --include-value --query 'value' --output text); \
	BLUE='\033[34m'; RESET='\033[0m'; \
	echo "+------------------------------------------------------------------------+"; \
	echo "|  API Key Lookup                                                        |"; \
	echo "+------------------------+-----------------------------------------------+"; \
	printf "|  %b%-20s%b  |  %b%-38s%b  |\n" \
	  "$$BLUE" "$(API_NAME)" "$$RESET" \
	  "$$BLUE" "$$API_KEY_VALUE" "$$RESET"; \
	echo "+------------------------+-----------------------------------------------+"

ls-api: ls-api-id ls-api-key ## List API IDs and keys (LocalStack)

ls-resources: ls-s3 ls-api-id ## List all key LocalStack resources

ls-s3-objects: _require-dev ## List objects in S3_BUCKET  [S3_BUCKET=<name>]
	@echo "$(CYAN)Listing objects in: $(S3_BUCKET)$(RESET)"
	@$(AWS_ENV) aws s3 ls s3://$(S3_BUCKET) --recursive

# ============================================================================
# CloudFormation / SAM
# ============================================================================
.PHONY: cf-build cf-deploy cf-status cf-logs cf-delete

cf-build: poetry-export ## Build SAM application
	@poetry run sam build --template-file $(TEMPLATE)

cf-deploy: docker-up docker-networks cf-build ## Build and deploy SAM stack (prompts in snd)
	@$(AWS_ENV) poetry run sam deploy \
	  --template-file $(BUILD_TEMPLATE) \
	  --stack-name $(STACK_NAME) \
	  --resolve-s3 \
	  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
	  --region $(AWS_REGION) \
	  --no-confirm-changeset \
	  --no-fail-on-empty-changeset

cf-status: ## Show CloudFormation stack status
	@$(AWS_ENV) aws cloudformation describe-stacks --stack-name $(STACK_NAME)

cf-logs: ## Show CloudFormation stack events
	@$(AWS_ENV) aws cloudformation describe-stack-events \
	  --stack-name $(STACK_NAME) --output table

cf-delete: ## Delete CloudFormation stack and clean up
	@echo "$(RED)Deleting stack: $(STACK_NAME)$(RESET)"
	@$(MAKE) docker-clean || true
	@$(MAKE) clean-local  || true

# ============================================================================
# Convenience
# ============================================================================
.PHONY: clean-local restart-hard

clean-local: ## Remove .aws-sam artifacts and wipe LocalStack persistent data
	@echo "$(CYAN)Cleaning SAM artifacts and LocalStack data...$(RESET)"
	@rm -rf .aws-sam
	@docker run --rm \
	  -v "$$(pwd)/localstack-data:/var/lib/localstack" \
	  alpine \
	  sh -c "rm -rf /var/lib/localstack/*"

restart-hard: ## Hard reset: wipe LocalStack, redeploy from scratch
	@echo "$(YELLOW)HARD RESET — wiping LocalStack and redeploying$(RESET)"
	@echo ""
	@echo "1) Stopping Docker services..."
	@$(MAKE) docker-clean || true
	@echo "2) Cleaning LocalStack persistent data..."
	@$(MAKE) clean-local  || true
	@echo "3) Starting LocalStack..."
	@$(MAKE) docker-up
	@echo "4) Waiting for LocalStack to be healthy..."
	@sleep 10
	@echo "5) Deploying stack..."
	@$(MAKE) cf-deploy

# ============================================================================
# Development Mode
# ============================================================================
.PHONY: dev-start dev-build dev-deploy dev

dev-start:
	@$(MAKE) docker-up MODE=dev

dev-build:
	@$(MAKE) cf-build MODE=dev

dev-deploy:
	@$(MAKE) cf-deploy MODE=dev

dev:
	@$(MAKE) dev-start
	@$(MAKE) alembic-upgrade
	@$(MAKE) dev-deploy

# ============================================================================
# Help
# ============================================================================
.PHONY: help

help: ## Show this help message
	@echo ''
	@echo '$(CYAN)$(BOLD)Juris AI — Make Targets$(RESET)'
	@echo ''
	@if [ "$(_LOCALSTACK_UP)" = "yes" ]; then \
	  echo "  $(GREEN) Active env:$(RESET) $(BOLD)dev$(RESET)  (LocalStack is running — MODE auto-set to dev)"; \
	else \
	  echo "  $(YELLOW) Active env:$(RESET) $(BOLD)snd$(RESET)  $(RED)(LocalStack not detected — MODE auto-set to snd)$(RESET)"; \
	fi
	@echo "  Override anytime:  $(YELLOW)make <target> MODE=dev|snd FILES=local|both$(RESET)"
	@echo ''
	@echo '$(YELLOW)Usage:$(RESET)'
	@echo '  $(YELLOW)make$(RESET) $(GREEN)<target>$(RESET) [MODE=dev|snd] [FILES=local|both]'
	@echo ''
	@awk 'BEGIN {FS = ":.*?## "} \
	  /^## / { \
	    printf "\n$(CYAN)%s$(RESET)\n", substr($$0, 4) \
	  } \
	  /^[a-zA-Z_-]+:.*?##/ { \
	    printf "  $(YELLOW)%-22s$(RESET) %s\n", $$1, $$2 \
	  }' $(MAKEFILE_LIST)
	@echo ''
	@echo "  Run $(GREEN)make env-info$(RESET) to see the full resolved config."
	@echo ''
