#!/usr/bin/env bash

set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"
RSA_BITS="${RSA_BITS:-3072}"

usage() {
    cat <<EOF
Usage:
  $0 [OPTIONS]

Options:
  -a, --algorithm ALGORITHM   JWT algorithm (default: HS256)
  -e, --env FILE              Environment file (default: .env)
  -b, --bits BITS             RSA key size (default: 3072)
  -h, --help                  Show this help

Supported algorithms:

  HMAC:
    HS256
    HS384
    HS512

  RSA:
    RS256
    RS384
    RS512

Examples:

  $0
  $0 --algorithm HS256
  $0 --algorithm HS384
  $0 --algorithm HS512

  $0 --algorithm RS256
  $0 --algorithm RS384
  $0 --algorithm RS512

  $0 --algorithm RS256 --bits 4096
  $0 --algorithm RS256 --env .env.local
EOF
}

ALGORITHM="HS256"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -a|--algorithm)
            if [[ $# -lt 2 ]]; then
                echo "Error: --algorithm requires a value."
                exit 1
            fi

            ALGORITHM="$2"
            shift 2
            ;;

        -e|--env)
            if [[ $# -lt 2 ]]; then
                echo "Error: --env requires a file."
                exit 1
            fi

            ENV_FILE="$2"
            shift 2
            ;;

        -b|--bits)
            if [[ $# -lt 2 ]]; then
                echo "Error: --bits requires a value."
                exit 1
            fi

            RSA_BITS="$2"
            shift 2
            ;;

        -h|--help)
            usage
            exit 0
            ;;

        *)
            echo "Error: Unknown option '$1'"
            echo
            usage
            exit 1
            ;;
    esac
done

ALGORITHM="$(echo "$ALGORITHM" | tr '[:lower:]' '[:upper:]')"


# ---------------------------------------------------------------------------
# Validate algorithm
# ---------------------------------------------------------------------------

case "$ALGORITHM" in
    HS256|HS384|HS512)
        KEY_TYPE="HMAC"
        ;;

    RS256|RS384|RS512)
        KEY_TYPE="RSA"
        ;;

    *)
        echo "Error: Unsupported JWT algorithm '$ALGORITHM'"
        echo
        echo "Supported algorithms:"
        echo "  HS256 HS384 HS512"
        echo "  RS256 RS384 RS512"
        exit 1
        ;;
esac


# ---------------------------------------------------------------------------
# Validate dependencies
# ---------------------------------------------------------------------------

if ! command -v openssl >/dev/null 2>&1; then
    echo "Error: openssl is required."
    exit 1
fi


# ---------------------------------------------------------------------------
# HMAC
# ---------------------------------------------------------------------------

generate_hmac_key() {
    local secret_bytes

    case "$ALGORITHM" in
        HS256)
            secret_bytes=32
            ;;

        HS384)
            secret_bytes=48
            ;;

        HS512)
            secret_bytes=64
            ;;
    esac

    JWT_SECRET_KEY="$(openssl rand -hex "$secret_bytes")"

    if [[ -f "$ENV_FILE" ]] && grep -q '^JWT_ALGORITHM=' "$ENV_FILE"; then
        sed -i \
            "s|^JWT_ALGORITHM=.*|JWT_ALGORITHM=${ALGORITHM}|" \
            "$ENV_FILE"
    else
        printf '\nJWT_ALGORITHM=%s\n' "$ALGORITHM" >> "$ENV_FILE"
    fi

    if [[ -f "$ENV_FILE" ]] && grep -q '^JWT_SECRET_KEY=' "$ENV_FILE"; then
        sed -i \
            "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${JWT_SECRET_KEY}|" \
            "$ENV_FILE"
    else
        printf 'JWT_SECRET_KEY=%s\n' "$JWT_SECRET_KEY" >> "$ENV_FILE"
    fi

    echo "JWT HMAC key generated successfully."
    echo
    echo "Algorithm : $ALGORITHM"
    echo "Key type  : HMAC"
    echo "Key size  : $((secret_bytes * 8)) bits"
    echo "Env file  : $ENV_FILE"
}


# ---------------------------------------------------------------------------
# RSA
# ---------------------------------------------------------------------------

generate_rsa_key() {
    local key_directory=".secrets"
    local private_key="${key_directory}/jwt-private.pem"
    local public_key="${key_directory}/jwt-public.pem"

    mkdir -p "$key_directory"

    chmod 700 "$key_directory"

    echo "Generating ${RSA_BITS}-bit RSA private key..."

    openssl genrsa \
        -out "$private_key" \
        "$RSA_BITS" \
        >/dev/null 2>&1

    echo "Generating RSA public key..."

    openssl rsa \
        -in "$private_key" \
        -pubout \
        -out "$public_key" \
        >/dev/null 2>&1

    chmod 600 "$private_key"
    chmod 644 "$public_key"

    if [[ -f "$ENV_FILE" ]] && grep -q '^JWT_ALGORITHM=' "$ENV_FILE"; then
        sed -i \
            "s|^JWT_ALGORITHM=.*|JWT_ALGORITHM=${ALGORITHM}|" \
            "$ENV_FILE"
    else
        printf '\nJWT_ALGORITHM=%s\n' "$ALGORITHM" >> "$ENV_FILE"
    fi

    if [[ -f "$ENV_FILE" ]] && grep -q '^JWT_PRIVATE_KEY_FILE=' "$ENV_FILE"; then
        sed -i \
            "s|^JWT_PRIVATE_KEY_FILE=.*|JWT_PRIVATE_KEY_FILE=${private_key}|" \
            "$ENV_FILE"
    else
        printf 'JWT_PRIVATE_KEY_FILE=%s\n' "$private_key" >> "$ENV_FILE"
    fi

    if [[ -f "$ENV_FILE" ]] && grep -q '^JWT_PUBLIC_KEY_FILE=' "$ENV_FILE"; then
        sed -i \
            "s|^JWT_PUBLIC_KEY_FILE=.*|JWT_PUBLIC_KEY_FILE=${public_key}|" \
            "$ENV_FILE"
    else
        printf 'JWT_PUBLIC_KEY_FILE=%s\n' "$public_key" >> "$ENV_FILE"
    fi

    echo "JWT RSA key pair generated successfully."
    echo
    echo "Algorithm : $ALGORITHM"
    echo "Key type  : RSA"
    echo "Key size  : ${RSA_BITS} bits"
    echo "Private   : $private_key"
    echo "Public    : $public_key"
    echo "Env file  : $ENV_FILE"
}


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

echo
echo "JWT Key Generator"
echo "================="
echo "Algorithm: $ALGORITHM"
echo

case "$KEY_TYPE" in
    HMAC)
        generate_hmac_key
        ;;

    RSA)
        generate_rsa_key
        ;;
esac

echo
echo "Done."
