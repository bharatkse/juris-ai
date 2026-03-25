#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================================
# station-hygiene-service development environment setup
#
# Aligns with pyproject.toml:
# - Python: ^3.11 (pinned via pyenv for local dev)
# - Poetry: pipx-managed
# - pre-commit: via Poetry
# ============================================================================


PYTHON_VERSION="3.11.12"

SKIP_PYTHON=false
SKIP_DOCKER=false
WRITE_PYTHON_VERSION=false
CI_MODE=false

# ------------------ Parse CLI arguments ------------------
for arg in "$@"; do
  case "$arg" in
    --skip-python) SKIP_PYTHON=true ;;
    --skip-docker) SKIP_DOCKER=true ;;
    --write-python-version) WRITE_PYTHON_VERSION=true ;;
    *) echo "Unknown option: $arg"; exit 1 ;;
  esac
done

if [[ "${CI:-false}" == "true" ]]; then
  CI_MODE=true
fi

# ------------------ Logging ------------------
log()  { echo "▶ $1"; }
warn() { echo "⚠ $1"; }

trap 'warn "Failed at line $LINENO"' ERR

# ------------------ PATH ------------------
export PATH="$HOME/.local/bin:$PATH"
export PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"
export PATH="$PYENV_ROOT/bin:$PATH"

# ============================================================================
# OS Detection (Ubuntu / Debian)
# ============================================================================
check_os() {
  command -v lsb_release >/dev/null 2>&1 || {
    warn "Unsupported OS (lsb_release not found)"
    exit 1
  }

  local os_id
  os_id="$(lsb_release -is)"

  [[ "$os_id" == "Ubuntu" || "$os_id" == "Debian" ]] || {
    warn "Unsupported OS: $os_id"
    exit 1
  }
}

# ============================================================================
# System dependencies
# ============================================================================
install_system_deps() {
  if $CI_MODE; then
    return
  fi

  local pkgs=(
    build-essential curl git make unzip
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev
    libsqlite3-dev libffi-dev liblzma-dev libncurses-dev
    libgdbm-dev libnss3-dev libdb-dev uuid-dev
    llvm xz-utils tk-dev pipx make
  )

  local missing=()
  for p in "${pkgs[@]}"; do
    dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p")
  done

  if [[ ${#missing[@]} -eq 0 ]]; then
    log "System deps OK"
    return
  fi

  log "Installing system deps"
  sudo apt update
  sudo apt install -y "${missing[@]}"
}

# ============================================================================
# pyenv
# ============================================================================
install_pyenv() {
  if command -v pyenv >/dev/null 2>&1; then
    log "pyenv OK"
    return
  fi

  if $CI_MODE; then
    warn "Skipping pyenv in CI"
    return
  fi

  log "Installing pyenv"
  curl -fsSL https://pyenv.run | bash

  # ----------------------------
  # Current shell setup (only once)
  # ----------------------------
  export PYENV_ROOT="$HOME/.pyenv"
  export PATH="$PYENV_ROOT/bin:$PATH"
  eval "$(pyenv init -)"

  # ----------------------------
  # Persist for future shells (append if missing)
  # ----------------------------
  if ! grep -q "pyenv init" "$HOME/.bashrc"; then
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> "$HOME/.bashrc"
    echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> "$HOME/.bashrc"
    echo 'eval "$(pyenv init -)"' >> "$HOME/.bashrc"
  fi
}

# ============================================================================
# Python via pyenv
# ============================================================================
install_python() {
  if $SKIP_PYTHON; then
    log "Skipping Python"
    return
  fi

  command -v pyenv >/dev/null || { warn "pyenv missing"; exit 1; }

  if pyenv versions --bare | grep -qx "$PYTHON_VERSION"; then
    log "Python $PYTHON_VERSION OK"
  else
    log "Installing Python $PYTHON_VERSION"
    pyenv install "$PYTHON_VERSION"
  fi

  pyenv local "$PYTHON_VERSION"
  export PATH="$PYENV_ROOT/versions/$PYTHON_VERSION/bin:$PATH"
}

# ============================================================================
# .python-version
# ============================================================================
write_python_version_file() {
  if ! $WRITE_PYTHON_VERSION; then
    return
  fi

  echo "$PYTHON_VERSION" > .python-version
  log ".python-version written"
}

# ============================================================================
# Docker
# ============================================================================
install_docker() {
  if $SKIP_DOCKER; then
    log "Skipping Docker"
    return
  fi

  if command -v docker >/dev/null 2>&1; then
    log "Docker OK"
    return
  fi

  if $CI_MODE; then
    warn "Skipping Docker in CI"
    return
  fi

  log "Installing Docker"
  sudo apt update
  sudo apt install -y ca-certificates curl gnupg

  sudo install -m 0755 -d /etc/apt/keyrings

  curl -fsSL https://download.docker.com/linux/ubuntu/gpg |
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" |
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

  sudo apt update
  sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  sudo usermod -aG docker "$USER"

  warn "Log out or run: newgrp docker"
}

# ============================================================================
# Poetry
# ============================================================================
install_poetry() {
  command -v pipx >/dev/null || { warn "pipx missing"; exit 1; }

  if command -v poetry >/dev/null; then
    log "Poetry OK"
    return
  fi

  log "Installing Poetry"
  pipx install poetry==2.0.1
  poetry config virtualenvs.create true
  poetry config virtualenvs.in-project true
}

# ============================================================================
# Python dependencies
# ============================================================================
install_dependencies() {
  if [[ ! -f pyproject.toml ]]; then
    warn "No pyproject.toml"
    return
  fi

  log "Installing deps"
  poetry install --no-interaction
}

# ============================================================================
# pre-commit
# ============================================================================
setup_precommit() {
  if [[ ! -f .pre-commit-config.yaml ]]; then
    return
  fi

  if [[ -f .git/hooks/pre-commit ]]; then
    log "pre-commit OK"
    return
  fi

  log "Installing pre-commit"
  poetry run pre-commit install
}

# ============================================================================
# Environment file
# ============================================================================
create_env_file() {
  if [[ -f .env ]]; then
    log ".env file exists"
    return
  fi

  if [[ ! -f .env.example ]]; then
    warn ".env.example not found"
    return
  fi

  cp .env.example .env
  log ".env file created from .env.example"
}

# ============================================================================
# Main
# ============================================================================
main() {
  log "Setting up station-hygiene-service development environment"

  check_os
  install_system_deps
  install_pyenv
  install_python
  write_python_version_file
  install_docker
  install_poetry
  install_dependencies
  # setup_precommit
  create_env_file

  log "Setup complete"
}

main "$@"
