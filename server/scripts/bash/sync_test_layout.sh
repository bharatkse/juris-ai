#!/usr/bin/env bash

set -e

mkdir -p tests

find src -type d | while read dir; do
    mkdir -p "tests/${dir#src/}"
done

find src -type f -name "*.py" ! -name "__init__.py" | while read file; do
    test_file="tests/${file#src/}"
    test_file="$(dirname "$test_file")/test_$(basename "$test_file")"

    mkdir -p "$(dirname "$test_file")"
    touch "$test_file"
done

find tests -type d -exec touch {}/__init__.py \;

echo "Test layout generated."
