PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: venv install migrate seed run client setup clean

venv:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -U pip
	$(BIN)/pip install -r requirements.txt

install: venv

migrate:
	$(BIN)/alembic upgrade head

seed:
	$(BIN)/python -m app.seed

run:
	$(BIN)/python -m app.main

client:
	$(BIN)/python -m task_1_client.main

setup: install migrate seed

clean:
	rm -rf $(VENV) library.db
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
