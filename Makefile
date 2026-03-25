# ============================================
# Colors for output
# ============================================
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
WHITE  := $(shell tput -Txterm setaf 7)
CYAN   := $(shell tput -Txterm setaf 6)
RED    := $(shell tput -Txterm setaf 1)
RESET  := $(shell tput -Txterm sgr0)

# ============================================
# Variables
# ============================================
PROJECT_NAME := juris-ai
DOCKER_COMPOSE_FILE := docker-compose.yml
DOCKER_COMPOSE := docker compose
POETRY := poetry

APP_CONTAINER := api
DB_CONTAINER := db
ALEMBIC := alembic

# ============================================
# Help
# ============================================
.DEFAULT_GOAL := help
SHELL := /bin/bash

help: ## Show this help message
	@echo ''
	@echo '${CYAN}juris-ai Microservices - Make Targets${RESET}'
	@echo ''
	@echo '${YELLOW}Usage:${RESET}'
	@echo '  ${YELLOW}make${RESET} ${GREEN}<target>${RESET}'
	@echo ''
	@echo '${YELLOW}Targets:${RESET}'
	@awk 'BEGIN {FS = ":.*?## "} { \
		if (/^[a-zA-Z_-]+:.*?##.*$$/) {printf "    ${YELLOW}%-30s${GREEN}%s${RESET}\n", $$1, $$2} \
		else if (/^## .*$$/) {printf "\n  ${CYAN}%s${RESET}\n", substr($$1,4)} \
		}' $(MAKEFILE_LIST)
	@echo ''


# ============================================
# Docker
# ============================================

docker-build: ## Build Docker images without starting containers
	@$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up -d --build

docker-up: ## Start all Docker services
	@$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up -d

docker-down: ## Stop all Docker services
	@$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) down

docker-restart: ## Restart Docker services
	@$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) down
	@$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up -d --build

docker-app-logs: ## Follow app logs
	@$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) logs -f $(APP_CONTAINER)

docker-db-logs: ## Follow database logs
	@$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) logs -f $(DB_CONTAINER)

docker-ps: ## Show running containers
	@$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) ps

docker-exec-app: ## Open shell in app container
	@$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) exec $(APP_CONTAINER) bash

docker-exec-db: ## Open shell in db container
	@$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) exec $(DB_CONTAINER) bash

docker-clean: ## Remove all stopped containers and dangling images
	@$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) down --rmi local --volumes --remove-orphans
	@docker volume prune -f
	@docker network prune -f

# ============================================
# Poetry / Python
# ============================================
poetry-install: ## Install Python dependencies via Poetry
	@$(POETRY) install

poetry-update: ## Update Python dependencies via Poetry
	@$(POETRY) update

poetry-lock: ## Generate poetry.lock from pyproject.toml
	@poetry lock

poetry-check: ## Validate pyproject.toml configuration
	@poetry check

poetry-show: ## Show dependency tree
	@poetry show --tree

poetry-activate: ## Activate Poetry virtual environment in current shell
	@VENV="$$(poetry env info --path)"; \
	echo "Activating $$VENV"; \
	exec bash --rcfile <(echo "source $$VENV/bin/activate")


# ============================================
## Code Quality
# ============================================
lint: ## Run ruff linter
	@echo '${CYAN}Running linter...${RESET}'
	@poetry run ruff check .
	@echo '${GREEN}✓ Linting passed${RESET}'

format: ## Format code with ruff
	@echo '${CYAN}Formatting code...${RESET}'
	@poetry run ruff format .
	@echo '${GREEN}✓ Code formatted${RESET}'

type-check: ## Run mypy type checker
	@echo '${CYAN}Running type checks...${RESET}'
	@poetry run mypy src/
	@echo '${GREEN}✓ Type checking passed${RESET}'

pre-commit: ## Run all pre-commit hooks
	@echo '${CYAN}Running pre-commit checks...${RESET}'
	@poetry run pre-commit run --all-files
	@echo '${GREEN}✓ Pre-commit checks passed${RESET}'

ci: ## Full CI pipeline — lint + type-check + test
	@echo '${CYAN}Running CI pipeline...${RESET}'
	@$(MAKE) lint
	@$(MAKE) type-check
	@$(MAKE) test
	@echo '${GREEN}✓ CI pipeline passed${RESET}'

install-hooks: ## Install pre-commit git hooks
	@echo '${CYAN}Installing git hooks...${RESET}'
	@poetry run pre-commit install
	@echo '${GREEN}✓ Git hooks installed${RESET}'

# ============================================
# Alembic / Database Migrations
# ============================================

alembic-upgrade: ## Apply all Alembic migrations
	@$(POETRY) run $(ALEMBIC) upgrade head

alembic-downgrade: ## Rollback last Alembic migration
	@read -p "⚠️  Downgrade database? [y/N] " and; \
	[ "$$and" = "y" ] || exit 1
	@$(POETRY) run $(ALEMBIC) downgrade -1

alembic-current: ## Show current Alembic revision
	@$(POETRY) run $(ALEMBIC) current

alembic-history: ## Show Alembic migration history
	@$(POETRY) run $(ALEMBIC) history

alembic-heads: ## Show current Alembic heads (detect branches)
	@$(POETRY) run $(ALEMBIC) heads

alembic-stamp: ## Stamp database with a revision without running migrations (rev=...)
ifndef rev
	$(error Please provide a revision: make alembic-stamp rev=head)
endif
	@$(POETRY) run $(ALEMBIC) stamp $(rev)

alembic-revision: ## Create new Alembic revision (msg="...")
ifndef msg
	$(error Please provide a message: make alembic-revision msg="add stations table")
endif
	@$(POETRY) run $(ALEMBIC) revision --autogenerate -m "$(msg)"


# ============================================================================
## Docs
# ============================================================================
docs: ## Show quick start guide
	@echo ''
	@echo '${CYAN}╔════════════════════════════════════════════════════════════╗${RESET}'
	@echo '${CYAN}║        Juris AI				  - Quick Start Guide          ║${RESET}'
	@echo '${CYAN}╚════════════════════════════════════════════════════════════╝${RESET}'
	@echo ''
	@echo '   ${YELLOW}6. Code quality:${RESET}'
	@echo '   ${GREEN}make lint${RESET}                Ruff linter'
	@echo '   ${GREEN}make format${RESET}              Ruff formatter'
	@echo '   ${GREEN}make type-check${RESET}          Mypy'
	@echo '   ${GREEN}make test${RESET}                All tests'
	@echo '   ${GREEN}make ci${RESET}                  Full CI pipeline'
	@echo ''
	@echo '   ${YELLOW}7. Docker:${RESET}'
	@echo '   ${GREEN}make docker-build${RESET}        Build Docker images'
	@echo '   ${GREEN}make docker-up${RESET}           Start Docker services'
	@echo '   ${GREEN}make docker-down${RESET}         Stop Docker services'
	@echo '   ${GREEN}make docker-restart${RESET}      Restart Docker services'
	@echo '   ${GREEN}make docker-app-logs${RESET}     Follow app logs'
	@echo '   ${GREEN}make docker-db-logs${RESET}      Follow db logs'
	@echo '   ${GREEN}make docker-ps${RESET}           Show running containers'
	@echo '   ${GREEN}make docker-exec-app${RESET}     Open shell in app container'
	@echo '   ${GREEN}make docker-exec-db${RESET}      Open shell in db container'
	@echo '   ${GREEN}make docker-clean${RESET}       Clean up Docker environment'
	@echo ''
	@echo '   ${YELLOW}8. Alembic / Database Migrations:${RESET}'
	@echo '   ${GREEN}make alembic-upgrade${RESET}     Apply all migrations'
	@echo '   ${GREEN}make alembic-downgrade${RESET}   Rollback last migration'
	@echo '   ${GREEN}make alembic	current${RESET}     Show current migration'
	@echo '   ${GREEN}make alembic-history${RESET}     Show migration history'
	@echo '   ${GREEN}make alembic-heads${RESET}       Show current heads'
	@echo '   ${GREEN}make alembic-stamp${RESET}       Stamp database'
	@echo '   ${GREEN}make alembic-revision${RESET}    Create new migration'
	@echo ''
	@echo '   ${YELLOW}9. Poetry / Python:${RESET}'
	@echo '   ${GREEN}make poetry-install${RESET}      Install Python dependencies'
	@echo '   ${GREEN}make poetry-update${RESET}       Update Python dependencies'
	@echo '   ${GREEN}make poetry-lock${RESET}         Generate poetry.lock'
	@echo '   ${GREEN}make poetry-check${RESET}        Validate pyproject.toml'
	@echo '   ${GREEN}make poetry-show${RESET}         Show dependency tree'
	@echo '   ${GREEN}make poetry-activate${RESET}     Activate virtual environment'
	@echo ''
	@echo '${YELLOW}All targets:${RESET}  ${GREEN}make help${RESET}'
	@echo ''

# ============================================================================
.PHONY: help \
	lint format type-check pre-commit ci install-hooks docs \
	docker-up docker-down docker-restart docker-app-logs docker-db-logs \
	docker-ps docker-exec-app docker-exec-db docker-clean \
	alembic-upgrade alembic-downgrade alembic-current \
	alembic-history alembic-heads alembic-stamp alembic-revision \
	poetry-install poetry-update poetry-check poetry-show poetry-activate poetry-lock
