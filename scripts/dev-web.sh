#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_DIR="$ROOT/apps/web"

if [[ ! -f "$WEB_DIR/.env.local" && -f "$ROOT/.env.example" ]]; then
  cp "$ROOT/.env.example" "$WEB_DIR/.env.local"
  echo "Created apps/web/.env.local from .env.example"
fi

cd "$WEB_DIR"
exec npm run dev
