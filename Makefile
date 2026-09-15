PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin
NEXT_REV_ID = $(shell $(PYTHON) -c "import pathlib; p=pathlib.Path('alembic/versions'); ids=[int(f.name.split('_')[0]) for f in p.glob('*.py') if f.name[:1].isdigit()] if p.exists() else []; print(f'{(max(ids)+1) if ids else 1:04d}')")

.PHONY: venv install alembic-init migrations migrate seed run client

venv:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -U pip
	$(BIN)/pip install -r requirements.txt

install: venv

alembic-init:
	$(BIN)/alembic init alembic

migrations:
	@test -n "$(m)" || (echo 'Usage: make migrations m="short description"' && exit 1)
	$(BIN)/alembic revision --autogenerate -m "$(m)" --rev-id "$(or $(id),$(NEXT_REV_ID))"

migrate:
	$(BIN)/alembic upgrade head

seed:
	$(BIN)/python -m app.seed

run:
	$(BIN)/python -m app.main

client:
	$(BIN)/python -m task_1_client.main