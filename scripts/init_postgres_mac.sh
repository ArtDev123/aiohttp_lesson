#!/usr/bin/env bash
# macOS: Homebrew Postgres обычно без роли postgres — суперпользователь = текущий логин.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SQL="$ROOT/scripts/init_postgres.sql"

find_psql() {
    if command -v psql >/dev/null 2>&1; then
        command -v psql
        return
    fi
    local candidate
    for candidate in \
        /opt/homebrew/opt/postgresql@16/bin/psql \
        /opt/homebrew/opt/postgresql@15/bin/psql \
        /opt/homebrew/opt/postgresql@14/bin/psql \
        /opt/homebrew/bin/psql \
        /usr/local/opt/postgresql@16/bin/psql \
        /usr/local/opt/postgresql@15/bin/psql \
        /usr/local/bin/psql \
        /Applications/Postgres.app/Contents/Versions/latest/bin/psql
    do
        if [[ -x "$candidate" ]]; then
            echo "$candidate"
            return
        fi
    done
    echo "psql не найден. Установите PostgreSQL: brew install postgresql@16" >&2
    echo "и добавьте bin в PATH, либо поставьте Postgres.app." >&2
    exit 1
}

PSQL="$(find_psql)"

run_sql() {
    "$PSQL" -d postgres -v ON_ERROR_STOP=1 -f "$SQL" "$@"
}

if run_sql; then
    echo "OK: library_db / library_user"
    exit 0
fi

echo "Повтор с ролью postgres…" >&2
if run_sql -U postgres; then
    echo "OK: library_db / library_user"
    exit 0
fi

echo "Не удалось выполнить SQL. Проверьте, что Postgres запущен:" >&2
echo "  brew services start postgresql@16" >&2
exit 1
