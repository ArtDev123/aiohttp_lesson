#!/usr/bin/env bash
# Linux: peer-auth от пользователя postgres, без пароля суперпользователя.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
sudo -u postgres psql -v ON_ERROR_STOP=1 -f "$ROOT/scripts/init_postgres.sql"
echo "OK: library_db / library_user"
