#!/bin/sh
set -e

echo ">>> alembic upgrade head"
alembic upgrade head

echo ">>> python -m app.seed"
python -m app.seed

echo ">>> python -m app.main"
exec python -m app.main
