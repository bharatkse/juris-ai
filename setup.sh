#!/usr/bin/env bash
# Juris AI lifecycle manager.
#
# The installer is bundle-aware and dependency-aware.
#
# Bundles:
#   server         Core FastAPI application only
#   dependencies   Optional local PostgreSQL / Redis / Floci
#   observability  OpenTelemetry Collector + Prometheus + Tempo + Grafana
#   development    Ollama + SearXNG (MCP currently disabled)
#   clients        First-party clients (currently reserved; no Docker stack yet)
#
# Modes:
#   release  Install the core server stack by default.
#   dev      Install every currently available stack.
#
# Examples:
#   ./setup.sh
#   ./setup.sh --mode dev
#   ./setup.sh --install
#   ./setup.sh --install --bundle observability
#   ./setup.sh --reinstall --bundle server
#   ./setup.sh --cleanup --bundle observability
#   ./setup.sh --uninstall --bundle server
#
# Size/split policy for this file and Makefile: see
# server/CONTRIBUTING.md ("Splitting large scripts").
#
# IMPORTANT:
#   Never run this script with sudo or as root.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ACTION=""
MODE="dev"
NON_INTERACTIVE=false
REQUESTED_BUNDLES=()
REQUESTED_DEPENDENCIES=()

DOCKER_DIR="$SCRIPT_DIR/docker"
SERVER_DIR="$DOCKER_DIR/server"
DEPENDENCIES_DIR="$DOCKER_DIR/dependencies"
DEVELOPMENT_DIR="$DOCKER_DIR/development"
OBSERVABILITY_DIR="$DOCKER_DIR/observability"
CLIENTS_DIR="$DOCKER_DIR/clients"

SERVER_COMPOSE="$SERVER_DIR/docker-compose.yml"
POSTGRES_COMPOSE="$DEPENDENCIES_DIR/docker-compose-postgres.yml"
REDIS_COMPOSE="$DEPENDENCIES_DIR/docker-compose-redis.yml"
FLOCI_COMPOSE="$DEPENDENCIES_DIR/docker-compose-floci.yml"

OBSERVABILITY_COMPOSE="$OBSERVABILITY_DIR/docker-compose.yml"
LLM_COMPOSE="$DEVELOPMENT_DIR/docker-compose-llm.yml"
SEARXNG_COMPOSE="$DEVELOPMENT_DIR/docker-compose-searxng.yml"

ENV_FILE="$SCRIPT_DIR/server/.env"
ENV_EXAMPLE="$SCRIPT_DIR/server/env.example"
STATE_FILE="$DOCKER_DIR/.setup-state"

log() {
    printf '[setup] %s\n' "$*"
}

warn() {
    printf '[setup] WARNING: %s\n' "$*" >&2
}

fail() {
    printf '[setup] ERROR: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Usage: ./setup.sh [OPTIONS]

Without an explicit lifecycle operation, an interactive menu is displayed.

Lifecycle:
  --install
      Install/start selected bundles.

  --reinstall
      Recreate selected bundles and pull current images.
      Persistent data and server/.env are preserved.

  --cleanup
      Stop/remove selected bundles.
      Persistent data and server/.env are preserved.

  --uninstall
      Remove selected bundles and their persistent data.
      Requires interactive confirmation.

Mode:
  --mode release
      Default mode. Installs the core server bundle unless another
      bundle is explicitly selected.

  --mode dev
      Development mode. Installs every currently available bundle.

Bundle:
  --bundle server
  --bundle dependencies
  --bundle observability
  --bundle development
  --bundle clients
      Operate on a specific bundle. Repeat --bundle to select several.

Dependency:
  --dependency postgres
  --dependency redis
  --dependency floci
      Operate on a specific local dependency. Repeat --dependency as needed.

Other:
  --non-interactive
      Do not prompt for GROQ_API_KEY or confirmations.
      Uninstall is not permitted in non-interactive mode.

  -h, --help
      Show this help.

Examples:
  ./setup.sh
  ./setup.sh --mode dev
  ./setup.sh --install --bundle server
  ./setup.sh --install --bundle observability
  ./setup.sh --reinstall --bundle server
  ./setup.sh --cleanup --bundle observability
  ./setup.sh --uninstall --bundle observability
  GROQ_API_KEY=... ./setup.sh --install --bundle server --non-interactive
EOF
}

die_on_root() {
    [[ "${EUID}" -ne 0 ]] || \
        fail "do not run setup.sh as root or with sudo. Run it as your normal user: ./setup.sh"
}

check_dependencies() {
    command -v docker >/dev/null 2>&1 || \
        fail "Docker is not installed or not available in PATH."

    docker compose version >/dev/null 2>&1 || \
        fail "Docker Compose v2 is required. Verify: docker compose version"

    docker info >/dev/null 2>&1 || \
        fail "the current user cannot access the Docker daemon. Configure Docker access and rerun without sudo."

    if [[ "$ACTION" == "install" || "$ACTION" == "reinstall" ]]; then
        command -v openssl >/dev/null 2>&1 || \
            fail "openssl is required to generate application secrets."

        command -v curl >/dev/null 2>&1 || \
            fail "curl is required for health checks."
    fi
}

parse_args() {
    while (($#)); do
        case "$1" in
            --install|--reinstall|--cleanup|--uninstall)
                [[ -z "$ACTION" ]] || fail "only one lifecycle operation can be selected."
                ACTION="${1#--}"
                ;;
            --mode|--bundle|--dependency)
                [[ $# -gt 1 ]] || fail "$1 requires a value."
                set_option "$1" "$2"
                shift
                ;;
            --mode=*|--bundle=*|--dependency=*)
                set_option "${1%%=*}" "${1#*=}"
                ;;
            --non-interactive)
                NON_INTERACTIVE=true
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                fail "unknown option '$1'. Use --help for usage."
                ;;
        esac
        shift
    done
}

set_option() {
    case "$1" in
        --mode)
            case "$2" in
                release|dev) MODE="$2" ;;
                *) fail "invalid mode '$2'; expected release or dev." ;;
            esac
            ;;
        --bundle) add_bundle "$2" ;;
        --dependency) add_dependency "$2" ;;
    esac
}

add_bundle() {
    case "$1" in
        server|dependencies|observability|development|clients)
            REQUESTED_BUNDLES+=("$1")
            ;;
        *)
            fail "unknown bundle '$1'. Expected: server, dependencies, observability, development, clients."
            ;;
    esac
}

add_dependency() {
    case "$1" in
        postgres|redis|floci)
            REQUESTED_DEPENDENCIES+=("$1")
            ;;
        *)
            fail "unknown dependency '$1'. Expected: postgres, redis, floci."
            ;;
    esac
}

contains() {
    local needle="$1"
    shift
    local item
    for item in "$@"; do
        [[ "$item" == "$needle" ]] && return 0
    done
    return 1
}

unique_bundles() {
    local result=()
    local item
    for item in "$@"; do
        contains "$item" "${result[@]}" || result+=("$item")
    done
    printf '%s\n' "${result[@]}"
}

show_menu() {
    printf '\n'
    printf '%s\n' '======================================'
    printf '%s\n' '          Juris AI Setup'
    printf '%s\n' '======================================'
    printf '\n'
    printf '  1) Install / Start\n'
    printf '  2) Reinstall\n'
    printf '  3) Cleanup\n'
    printf '  4) Uninstall\n'
    printf '  5) Exit\n'
    printf '\n'
}

select_action() {
    while true; do
        show_menu
        printf 'Select an option [1-5]: '
        IFS= read -r choice
        case "$choice" in
            1) ACTION="install"; break ;;
            2) ACTION="reinstall"; break ;;
            3) ACTION="cleanup"; break ;;
            4) ACTION="uninstall"; break ;;
            5) log "Exiting."; exit 0 ;;
            *) printf 'Invalid option. Please select 1, 2, 3, 4, or 5.\n' ;;
        esac
    done
}

compose() {
    local file="$1"
    shift

    # Project name comes from the top-level `name:` in each Compose file.
    docker compose --env-file "$ENV_FILE" -f "$file" "$@"
}

require_file() {
    [[ -f "$1" ]] || fail "missing Compose file: $1"
}

ensure_compose_files() {
    if contains server "${SELECTED_BUNDLES[@]}"; then
        require_file "$SERVER_COMPOSE"
        compose "$SERVER_COMPOSE" config >/dev/null
    fi

    if contains dependencies "${SELECTED_BUNDLES[@]}"; then
        if contains postgres "${SELECTED_DEPENDENCIES[@]}"; then
            require_file "$POSTGRES_COMPOSE"
            compose "$POSTGRES_COMPOSE" config >/dev/null
        fi
        if contains redis "${SELECTED_DEPENDENCIES[@]}"; then
            require_file "$REDIS_COMPOSE"
            compose "$REDIS_COMPOSE" config >/dev/null
        fi
        if contains floci "${SELECTED_DEPENDENCIES[@]}"; then
            require_file "$FLOCI_COMPOSE"
            compose "$FLOCI_COMPOSE" config >/dev/null
        fi
    fi

    if contains observability "${SELECTED_BUNDLES[@]}"; then
        require_file "$OBSERVABILITY_COMPOSE"
        compose "$OBSERVABILITY_COMPOSE" config >/dev/null
    fi

    if contains development "${SELECTED_BUNDLES[@]}"; then
        require_file "$LLM_COMPOSE"
        require_file "$SEARXNG_COMPOSE"
        compose "$LLM_COMPOSE" config >/dev/null
        compose "$SEARXNG_COMPOSE" config >/dev/null
    fi
}

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
mark_installed() {
    local bundle="$1"
    mkdir -p "$(dirname "$STATE_FILE")"
    touch "$STATE_FILE"
    grep -v "^${bundle}=" "$STATE_FILE" > "${STATE_FILE}.tmp" || true
    printf '%s=installed\n' "$bundle" >> "${STATE_FILE}.tmp"
    mv -- "${STATE_FILE}.tmp" "$STATE_FILE"
}

mark_uninstalled() {
    local bundle="$1"
    [[ -f "$STATE_FILE" ]] || return 0
    grep -v "^${bundle}=" "$STATE_FILE" > "${STATE_FILE}.tmp" || true
    mv -- "${STATE_FILE}.tmp" "$STATE_FILE"
}

bundle_installed() {
    local bundle="$1"
    [[ -f "$STATE_FILE" ]] &&
        grep -q "^${bundle}=installed$" "$STATE_FILE"
}

show_state() {
    printf '\nCurrent installation:\n'

    local item
    for item in server postgres redis floci observability development clients; do
        if bundle_installed "$item"; then
            printf '  %-15s installed\n' "$item"
        else
            printf '  %-15s not installed\n' "$item"
        fi
    done
    printf '\n'
}

# ---------------------------------------------------------------------------
# Environment / secrets
# ---------------------------------------------------------------------------
env_value() {
    local key="$1"
    local line=""
    local value=""

    line="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 || true)"
    value="${line#*=}"

    if [[ "${#value}" -ge 2 ]]; then
        if [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]]; then
            value="${value:1:${#value}-2}"
        elif [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
            value="${value:1:${#value}-2}"
        fi
    fi

    printf '%s' "$value"
}

set_env_value() {
    local key="$1"
    local value="$2"
    local tmp

    tmp="$(mktemp "${ENV_FILE}.XXXXXX")"

    awk -v key="$key" -v value="$value" '
        BEGIN { found = 0 }
        $0 ~ "^" key "=" {
            print key "=" value
            found = 1
            next
        }
        { print }
        END {
            if (!found) print key "=" value
        }
    ' "$ENV_FILE" > "$tmp"

    chmod 600 "$tmp"
    mv -- "$tmp" "$ENV_FILE"
}

prepare_env() {
    [[ -f "$ENV_EXAMPLE" ]] || fail "missing $ENV_EXAMPLE"

    if [[ ! -f "$ENV_FILE" ]]; then
        log "Creating $ENV_FILE from $ENV_EXAMPLE"
        cp -- "$ENV_EXAMPLE" "$ENV_FILE"
    else
        log "Preserving existing $ENV_FILE"
    fi

    chmod 600 "$ENV_FILE"

    local key value
    for key in SECRET_KEY JWT_SECRET_KEY DB_PASSWORD APP_DB_PASSWORD; do
        value="$(env_value "$key")"
        if [[ -z "$value" || "$value" == CHANGE_ME* || "$value" == replace-with-* ]]; then
            value="$(openssl rand -hex 32)"
            set_env_value "$key" "$value"
            log "Generated $key"
        fi
    done

    local groq
    groq="$(env_value GROQ_API_KEY)"

    if [[ -z "$groq" || "$groq" == "CHANGE_ME" ]]; then
        groq="${GROQ_API_KEY:-}"

        if [[ -z "$groq" ]]; then
            if [[ "$NON_INTERACTIVE" == true ]]; then
                fail "GROQ_API_KEY is required. Set it in server/.env or the environment."
            fi

            printf '\nGROQ_API_KEY is required for Juris AI.\n'
            printf 'Enter GROQ_API_KEY: '
            IFS= read -r groq
            [[ -n "$groq" ]] || fail "GROQ_API_KEY cannot be empty."
        fi

        set_env_value GROQ_API_KEY "$groq"
    fi
}

VOLUMES_DIR="$DOCKER_DIR/.volumes"

prepare_storage() {
    echo "Preparing persistent storage in $VOLUMES_DIR"
    # mkdir -p \
    #     "$VOLUMES_DIR/postgres" \
    #     "$VOLUMES_DIR/redis" \
    #     "$VOLUMES_DIR/floci" \
    #     "$VOLUMES_DIR/ollama" \
    #     "$VOLUMES_DIR/searxng" \
    #     "$VOLUMES_DIR/prometheus" \
    #     "$VOLUMES_DIR/tempo" \
    #     "$VOLUMES_DIR/grafana"
}

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
ensure_network() {
    if ! docker network inspect juris_ai_network >/dev/null 2>&1; then
        log "Creating shared Docker network: juris_ai_network"
        docker network create juris_ai_network >/dev/null
    fi
}

# ---------------------------------------------------------------------------
# Dependency model
#
# Server is the application only. PostgreSQL, Redis and Floci are optional
# local dependencies with independent lifecycles.
#
# Observability and development are independent stacks.
# ---------------------------------------------------------------------------
expand_dependencies() {
    SELECTED_BUNDLES=(
        $(unique_bundles "${REQUESTED_BUNDLES[@]}")
    )

    SELECTED_DEPENDENCIES=(
        $(unique_bundles "${REQUESTED_DEPENDENCIES[@]}")
    )
}

# ---------------------------------------------------------------------------
# Generic Compose operations
# ---------------------------------------------------------------------------
pull_file() {
    local name="$1"
    local file="$2"

    require_file "$file"

    log "Pulling images: $name"
    compose "$file" pull
}

up_file() {
    local name="$1"
    local file="$2"

    require_file "$file"

    log "Starting: $name"

    # Do not use --remove-orphans here: each stack file sets its own
    # project `name:` and must never remove containers owned by another stack.
    compose "$file" up -d --force-recreate
}

remove_persistent_data() {
    local directory="$1"

    [[ -d "$directory" ]] || return 0

    log "Removing persistent data: $directory"

    # Persistent data is created by containers that may run as a different
    # UID/GID (for example Ollama runs as root). Do not chown/chmod the host
    # directory. Use a temporary root container to remove its contents.
    docker run --rm \
        -v "$directory:/data" \
        alpine:latest \
        sh -c 'rm -rf /data/* /data/.[!.]* /data/..?*'

    # The mount point itself was created by setup.sh and remains host-owned.
    rmdir "$directory" 2>/dev/null || true
}

down_file() {
    local name="$1"
    local file="$2"
    shift 2

    [[ -f "$file" ]] || return 0

    log "Stopping: $name"

    # Do not use --remove-orphans here either; extra args (e.g. --volumes)
    # are passed through to `down`.
    compose "$file" down "$@"
}

down_development() {
    down_file "SearXNG" "$SEARXNG_COMPOSE"
    down_file "Ollama" "$LLM_COMPOSE"
}

wait_for_service_health() {
    local file="$1"
    local service="$2"
    local timeout="${3:-120}"
    local elapsed=0
    local status

    log "Waiting for $service to become healthy"

    while ((elapsed < timeout)); do
        status="$(
            compose "$file" ps --format json "$service" 2>/dev/null |
                grep -o '"Health":"[a-zA-Z0-9_-]*"' |
                head -n1 |
                cut -d'"' -f4 || true
        )"

        if [[ "$status" == "healthy" ]]; then
            log "$service is healthy"
            return 0
        fi

        sleep 2
        elapsed=$((elapsed + 2))
    done

    warn "$service did not report healthy within ${timeout}s"
    compose "$file" logs --tail 80 "$service" 2>&1 || true
    return 1
}

wait_for_floci() {
    local timeout="${1:-120}"
    local elapsed=0

    log "Waiting for Floci to become ready"

    while (( elapsed < timeout )); do
        if curl -sf \
            --max-time 5 \
            "http://localhost:4566/_localstack/health" \
            >/dev/null 2>&1; then
            log "Floci is ready"
            return 0
        fi

        sleep 2
        elapsed=$((elapsed + 2))
    done

    warn "Floci did not become ready within ${timeout}s"
    docker logs --tail 80 juris_ai_floci 2>&1 || true
    return 1
}

dependency_display_name() {
    case "$1" in
        floci) printf 'Floci' ;;
        postgres) printf 'PostgreSQL' ;;
        redis) printf 'Redis' ;;
        *) printf '%s' "$1" ;;
    esac
}

dependency_compose_file() {
    case "$1" in
        floci) printf '%s' "$FLOCI_COMPOSE" ;;
        postgres) printf '%s' "$POSTGRES_COMPOSE" ;;
        redis) printf '%s' "$REDIS_COMPOSE" ;;
        *) return 1 ;;
    esac
}

dependency_container_name() {
    case "$1" in
        floci) printf 'juris_ai_floci' ;;
        postgres) printf 'juris_ai_postgres' ;;
        redis) printf 'juris_ai_redis' ;;
        *) return 1 ;;
    esac
}

dependency_running() {
    local dependency="$1"
    local container

    container="$(dependency_container_name "$dependency")"

    docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null |
        grep -q '^true$'
}

pull_dependencies() {
    local dependency

    # Floci must be pulled first.
    for dependency in floci postgres redis; do
        if contains "$dependency" "${SELECTED_DEPENDENCIES[@]}"; then
            pull_file \
                "$(dependency_display_name "$dependency")" \
                "$(dependency_compose_file "$dependency")"
        fi
    done
}

start_dependencies() {
    local dependency
    local file

    # Start order is explicit, while each dependency remains an independent
    # Compose project.
    for dependency in floci postgres redis; do
        if contains "$dependency" "${SELECTED_DEPENDENCIES[@]}"; then
            if dependency_running "$dependency"; then
                log "$(dependency_display_name "$dependency") is already running; leaving it unchanged."
                mark_installed "$dependency"
                continue
            fi

            file="$(dependency_compose_file "$dependency")"
            up_file "$(dependency_display_name "$dependency")" "$file"

            if [[ "$dependency" == "floci" ]]; then
                wait_for_floci 120 || \
                    fail "Floci did not become ready."
            else
                wait_for_service_health "$file" "$dependency" 120 || \
                    fail "$(dependency_display_name "$dependency") did not become healthy."
            fi

            mark_installed "$dependency"
        fi
    done
}

cleanup_dependencies() {
    local dependency

    for dependency in floci postgres redis; do
        if contains "$dependency" "${SELECTED_DEPENDENCIES[@]}"; then
            down_file \
                "$(dependency_display_name "$dependency")" \
                "$(dependency_compose_file "$dependency")"

            mark_uninstalled "$dependency"
        fi
    done
}

uninstall_dependencies() {
    local dependency

    cleanup_dependencies

    for dependency in floci postgres redis; do
        if contains "$dependency" "${SELECTED_DEPENDENCIES[@]}"; then
            case "$dependency" in
                postgres)
                    remove_persistent_data "$VOLUMES_DIR/postgres"
                    ;;
                redis)
                    remove_persistent_data "$VOLUMES_DIR/redis"
                    ;;
                floci)
                    # docker-compose-floci.yml mounts ./.volumes/floci, i.e.
                    # docker/dependencies/.volumes/floci -- not docker/.volumes.
                    remove_persistent_data "$DEPENDENCIES_DIR/.volumes/floci"
                    ;;
            esac
        fi
    done
}

server_running() {
    docker inspect -f '{{.State.Running}}' juris_ai_api 2>/dev/null |
        grep -q '^true$'
}

normalize_local_endpoint() {
    local key="$1"
    local service_name="$2"

    local current
    current="$(env_value "$key")"

    if [[ "$current" == "localhost" ||
          "$current" == "127.0.0.1" ||
          -z "$current" ]]; then
        set_env_value "$key" "$service_name"
        log "Using local Docker service for $key: $service_name"
    fi
}

configure_local_dependency_endpoints() {
    # Only normalize localhost/empty values when the corresponding local
    # dependency is explicitly selected. Clearly external endpoints are
    # preserved.
    if contains postgres "${SELECTED_DEPENDENCIES[@]}"; then
        normalize_local_endpoint DB_HOST postgres
    fi

    if contains redis "${SELECTED_DEPENDENCIES[@]}"; then
        normalize_local_endpoint REDIS_HOST redis
    fi
}

validate_server_endpoints() {
    local db_host
    local redis_host

    db_host="$(env_value DB_HOST)"
    redis_host="$(env_value REDIS_HOST)"

    [[ -n "$db_host" ]] || fail "DB_HOST is missing from $ENV_FILE"
    [[ -n "$redis_host" ]] || fail "REDIS_HOST is missing from $ENV_FILE"

    if [[ "$db_host" == "postgres" ]] && ! bundle_installed postgres; then
        fail "DB_HOST=postgres but local PostgreSQL is not installed. Install it with: ./setup.sh --install --dependency postgres, or configure DB_HOST for an external PostgreSQL/RDS instance."
    fi

    if [[ "$redis_host" == "redis" ]] && ! bundle_installed redis; then
        fail "REDIS_HOST=redis but local Redis is not installed. Install it with: ./setup.sh --install --dependency redis, or configure REDIS_HOST for an external Redis instance."
    fi

    log "Database endpoint: $db_host:$(env_value DB_PORT)"
    log "Redis endpoint:    $redis_host:$(env_value REDIS_PORT)"
}

ensure_server_running() {
    prepare_storage
    ensure_network

    configure_local_dependency_endpoints
    validate_server_endpoints

    if server_running; then
        log "Server is already running; leaving it unchanged."
        return 0
    fi

    log "Starting: server"
    compose "$SERVER_COMPOSE" up -d --build

    run_server_migrations
    wait_for_api
}

run_server_migrations() {
    log "Running database migrations"
    compose "$SERVER_COMPOSE" exec -T api alembic upgrade head
}

wait_for_api() {
    local api_port
    local attempt

    api_port="$(env_value API_PORT)"
    api_port="${api_port:-8001}"

    log "Waiting for API health at http://localhost:${api_port}/api/v1/health"

    for attempt in $(seq 1 60); do
        if curl -sf "http://localhost:${api_port}/api/v1/health" >/dev/null 2>&1; then
            log "API is healthy"
            return 0
        fi
        sleep 2
    done

    fail "API did not become healthy. Check: docker logs juris_ai_api"
}

pull_server() {
    log "Server API uses the repository Dockerfile; image will be built during startup."
}

pull_selected() {
    if contains dependencies "${SELECTED_BUNDLES[@]}"; then
        pull_dependencies
    fi

    if contains server "${SELECTED_BUNDLES[@]}"; then
        pull_server
    fi

    if contains observability "${SELECTED_BUNDLES[@]}"; then
        pull_file "observability" "$OBSERVABILITY_COMPOSE"
    fi

    if contains development "${SELECTED_BUNDLES[@]}"; then
        pull_file "Ollama" "$LLM_COMPOSE"
        pull_file "SearXNG" "$SEARXNG_COMPOSE"
    fi

    if contains clients "${SELECTED_BUNDLES[@]}"; then
        log "Clients bundle: no Docker assets currently exist; nothing to pull."
    fi
}

start_selected() {
    if contains dependencies "${SELECTED_BUNDLES[@]}"; then
        start_dependencies
    fi

    if contains server "${SELECTED_BUNDLES[@]}"; then
        ensure_server_running
        mark_installed server
    fi

    if contains development "${SELECTED_BUNDLES[@]}"; then
        up_file "Ollama" "$LLM_COMPOSE"
        up_file "SearXNG" "$SEARXNG_COMPOSE"
        mark_installed development
    fi

    if contains observability "${SELECTED_BUNDLES[@]}"; then
        up_file "observability" "$OBSERVABILITY_COMPOSE"
        mark_installed observability
    fi

    if contains clients "${SELECTED_BUNDLES[@]}"; then
        log "Clients bundle is reserved for future first-party client apps."
        log "No client Docker stack exists yet; nothing was started."
        mark_installed clients
    fi
}

cleanup_selected() {
    if contains clients "${SELECTED_BUNDLES[@]}"; then
        log "Clients cleanup: no Docker assets currently exist."
        mark_uninstalled clients
    fi

    if contains observability "${SELECTED_BUNDLES[@]}"; then
        down_file "observability" "$OBSERVABILITY_COMPOSE"
        mark_uninstalled observability
    fi

    if contains development "${SELECTED_BUNDLES[@]}"; then
        down_development
        mark_uninstalled development
    fi

    if contains server "${SELECTED_BUNDLES[@]}"; then
        down_file "server" "$SERVER_COMPOSE"
        mark_uninstalled server
    fi

    if contains dependencies "${SELECTED_BUNDLES[@]}"; then
        cleanup_dependencies
    fi
}

confirm_uninstall() {
    [[ "$NON_INTERACTIVE" == false ]] || \
        fail "uninstall requires interactive confirmation."

    printf '\n'
    printf '%s\n' 'WARNING: This is destructive.'
    printf '%s\n' 'Selected bundles/dependencies and their persistent data may be removed.'
    printf '\n'

    if ((${#SELECTED_BUNDLES[@]} > 0)); then
        printf 'Bundles:\n'
        local bundle
        for bundle in "${SELECTED_BUNDLES[@]}"; do
            printf '  - %s\n' "$bundle"
        done
    fi

    if ((${#SELECTED_DEPENDENCIES[@]} > 0)); then
        printf '\nDependencies:\n'
        local dependency
        for dependency in "${SELECTED_DEPENDENCIES[@]}"; do
            printf '  - %s\n' "$dependency"
        done
    fi

    printf '\nType UNINSTALL to continue: '

    local confirmation
    IFS= read -r confirmation

    [[ "$confirmation" == "UNINSTALL" ]] || {
        log "Uninstall cancelled."
        exit 0
    }
}

uninstall_selected() {
    # Dependents first; no dependency is implicitly removed by uninstalling
    # the server.
    if contains clients "${SELECTED_BUNDLES[@]}"; then
        log "Removing clients"
        mark_uninstalled clients
    fi

    if contains observability "${SELECTED_BUNDLES[@]}"; then
        # Prometheus/Tempo/Grafana data lives in named volumes.
        down_file "observability" "$OBSERVABILITY_COMPOSE" --volumes
        mark_uninstalled observability
    fi

    if contains development "${SELECTED_BUNDLES[@]}"; then
        down_development
        remove_persistent_data "$VOLUMES_DIR/ollama"
        remove_persistent_data "$VOLUMES_DIR/searxng"
        mark_uninstalled development
    fi

    if contains server "${SELECTED_BUNDLES[@]}"; then
        down_file "server" "$SERVER_COMPOSE"
        mark_uninstalled server
    fi

    if contains dependencies "${SELECTED_BUNDLES[@]}"; then
        uninstall_dependencies
    fi

    if [[ -f "$STATE_FILE" ]] && [[ ! -s "$STATE_FILE" ]]; then
        rm -f -- "$STATE_FILE"
    fi
}

reinstall_selected() {
    # Reinstall only the selected components. Server reinstall never touches
    # PostgreSQL, Redis or Floci unless they were explicitly selected.
    cleanup_selected

    prepare_storage
    ensure_network
    pull_selected
    start_selected
}

install_selected() {
    prepare_storage
    ensure_network

    pull_selected
    start_selected
}

# ---------------------------------------------------------------------------
# Interactive selection tracking.
# ---------------------------------------------------------------------------
select_interactive_action_if_needed() {
    if [[ -z "$ACTION" ]]; then
        [[ "$NON_INTERACTIVE" == false ]] || \
            fail "--non-interactive requires an explicit lifecycle operation."
        select_action
    fi
}

prompt_bundles() {
    show_state

    printf 'Select bundle(s):\n'
    printf '  1) Server\n'
    printf '  2) Dependencies\n'
    printf '  3) Observability\n'
    printf '  4) Development\n'
    printf '  5) Clients\n'
    printf '  6) All\n'
    printf '\n'
    printf 'Select bundle(s) [1-6, comma-separated]: '

    local selection
    local normalized
    local parts=()
    local part

    IFS= read -r selection
    normalized="${selection// /}"

    case "$normalized" in
        1) REQUESTED_BUNDLES=(server) ;;
        2) REQUESTED_BUNDLES=(dependencies) ;;
        3) REQUESTED_BUNDLES=(observability) ;;
        4) REQUESTED_BUNDLES=(development) ;;
        5) REQUESTED_BUNDLES=(clients) ;;
        6)
            REQUESTED_BUNDLES=(server dependencies observability development clients)
            REQUESTED_DEPENDENCIES=(floci postgres redis)
            ;;
        *)
            REQUESTED_BUNDLES=()
            IFS=',' read -ra parts <<< "$normalized"

            for part in "${parts[@]}"; do
                case "$part" in
                    1) add_bundle server ;;
                    2) add_bundle dependencies ;;
                    3) add_bundle observability ;;
                    4) add_bundle development ;;
                    5) add_bundle clients ;;
                    *) fail "invalid bundle selection '$part'." ;;
                esac
            done
            ;;
    esac
}

select_bundles() {
    # With no explicit CLI mode/bundle/dependency selection, show the mode
    # selector first. Dev is the default.
    if [[ "$NON_INTERACTIVE" == false ]] &&
       ((${#REQUESTED_BUNDLES[@]} == 0)) &&
       ((${#REQUESTED_DEPENDENCIES[@]} == 0)); then
        printf '\n'
        printf 'Select mode:\n'
        printf '  1) Development (dev) [default]\n'
        printf '  2) Release (release)\n'
        printf '\n'
        printf 'Select mode [1-2]: '

        local mode_selection
        IFS= read -r mode_selection
        case "${mode_selection:-1}" in
            1) MODE="dev" ;;
            2) MODE="release" ;;
            *) fail "invalid mode selection '$mode_selection'." ;;
        esac
    fi

    # A direct dependency selection implicitly targets the dependencies
    # bundle; it does not install or restart the API.
    if ((${#REQUESTED_DEPENDENCIES[@]} > 0)) &&
       ! contains dependencies "${REQUESTED_BUNDLES[@]}"; then
        REQUESTED_BUNDLES+=(dependencies)
    fi

    if ((${#REQUESTED_BUNDLES[@]} == 0)); then
        if [[ "$NON_INTERACTIVE" == false ]]; then
            prompt_bundles
        elif [[ "$MODE" == "dev" ]]; then
            REQUESTED_BUNDLES=(server dependencies observability development clients)
            REQUESTED_DEPENDENCIES=(floci postgres redis)
        else
            REQUESTED_BUNDLES=(server)
        fi
    fi

    if contains dependencies "${REQUESTED_BUNDLES[@]}" &&
       ((${#REQUESTED_DEPENDENCIES[@]} == 0)); then
        if [[ "$NON_INTERACTIVE" == true ]]; then
            REQUESTED_DEPENDENCIES=(floci postgres redis)
        else
            printf '\nSelect local dependencies:\n'
            printf '  1) PostgreSQL\n'
            printf '  2) Redis\n'
            printf '  3) Floci\n'
            printf '  4) All\n'
            printf '\n'
            printf 'Select dependency(s) [1-4, comma-separated]: '

            local dependency_selection
            local dependency_normalized
            local dependency_parts=()
            local dependency_part

            IFS= read -r dependency_selection
            dependency_normalized="${dependency_selection// /}"

            case "$dependency_normalized" in
                1) add_dependency postgres ;;
                2) add_dependency redis ;;
                3) add_dependency floci ;;
                4) REQUESTED_DEPENDENCIES=(floci postgres redis) ;;
                *)
                    IFS=',' read -ra dependency_parts <<< "$dependency_normalized"

                    for dependency_part in "${dependency_parts[@]}"; do
                        case "$dependency_part" in
                            1) add_dependency postgres ;;
                            2) add_dependency redis ;;
                            3) add_dependency floci ;;
                            *) fail "invalid dependency selection '$dependency_part'." ;;
                        esac
                    done
                    ;;
            esac
        fi
    fi

    ((${#REQUESTED_BUNDLES[@]} > 0)) || \
        fail "no bundle selected."

    expand_dependencies
}

service_running() {
    local file="$1"
    local service="$2"

    compose "$file" ps --status running --services 2>/dev/null |
        grep -qx "$service"
}

main() {
    parse_args "$@"
    select_interactive_action_if_needed

    die_on_root
    check_dependencies

    select_bundles

    # Compose interpolation is evaluated before service-level env_file is
    # loaded, so server/.env must be available to Compose itself.
    if [[ "$ACTION" == "install" || "$ACTION" == "reinstall" ]]; then
        prepare_env
    elif [[ ! -f "$ENV_FILE" ]]; then
        fail "missing $ENV_FILE. Install the server bundle first."
    fi

    ensure_compose_files

    printf '\n'
    log "Action: $ACTION"
    log "Mode:   $MODE"
    log "Bundles: ${SELECTED_BUNDLES[*]}"

    case "$ACTION" in
        install)
            install_selected
            ;;
        reinstall)
            reinstall_selected
            ;;
        cleanup)
            cleanup_selected
            ;;
        uninstall)
            confirm_uninstall
            uninstall_selected
            ;;
        *)
            fail "unsupported lifecycle action: $ACTION"
            ;;
    esac

    printf '\n'
    log "Operation completed."
    show_state

    if contains server "${SELECTED_BUNDLES[@]}"; then
        local api_port
        api_port="$(env_value API_PORT 2>/dev/null || true)"
        api_port="${api_port:-8001}"

        if server_running &&
        curl -sf \
            --max-time 5 \
            "http://localhost:${api_port}/api/v1/health" \
            >/dev/null 2>&1; then
            printf '  Swagger UI: http://localhost:%s/docs\n' "$api_port"
            printf '  Health:     http://localhost:%s/api/v1/health\n' "$api_port"
        fi
    fi

    if contains observability "${SELECTED_BUNDLES[@]}"; then
        if service_running "$OBSERVABILITY_COMPOSE" grafana; then
            printf '  Grafana:    http://localhost:3000\n'
        fi

        if service_running "$OBSERVABILITY_COMPOSE" prometheus; then
            printf '  Prometheus: http://localhost:9090\n'
        fi

        if service_running "$OBSERVABILITY_COMPOSE" tempo; then
            printf '  Tempo:      http://localhost:3200\n'
        fi
    fi


}

main "$@"
