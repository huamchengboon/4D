#!/usr/bin/env bash
# Build Rust extension (if Rust is available via mise) then run scrape_history.
# Usage: ./run_with_rust.sh [extra args for scrape_history.py]

set -e
cd "$(dirname "$0")"

echo "Building Rust extension (mise provides Rust)..."
mise exec -- uv run maturin develop

echo "Running scrape_history..."
mise exec -- uv run python scrape_history.py "$@"
