# Шаг 1 — Окружение, PostgreSQL, каркас репозитория

**Предыдущий:** [README](README.md) · **Следующий:** [step-02-client.md](step-02-client.md)

## Задача

Поднять изолированное Python-окружение, БД PostgreSQL и пустые файлы проекта, в которые на следующих шагах положим клиент и сервер.

Без этого шага остальные файлы гайда не к чему применять.

---

## Теория: зачем venv и зачем PostgreSQL

**venv** — папка с «личным» Python и пакетами проекта. Системный aiohttp 3.8 и проектный 3.14 не будут конфликтовать.

**PostgreSQL** вместо SQLite:

- ближе к продакшену;
- так же, как в `TMS_drf_online_shop` и `TMS_django_courses`;
- удобно смотреть данные через `psql` / DBeaver.

---

## 1. Проверка инструментов

```bash
python3 --version    # желательно 3.12+
psql --version
```

Windows: `python --version` и `psql --version` в PowerShell. Если `psql` нет — установите PostgreSQL и добавьте `bin` в PATH.

---

## 2. Каталог проекта и venv

```bash
cd aiohttp_lesson
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

В приглашении терминала должно появиться `(.venv)`.

---

## 3. Зависимости

Создайте в корне `requirements.txt`:

```text
aiohttp>=3.9,<4
aiohttp-swagger3>=0.10.0
sqlalchemy>=2.0
alembic>=1.13
asyncpg
psycopg2-binary
pydantic>=2.0
pydantic-settings>=2.0
pyyaml>=6.0
```

```bash
pip install -r requirements.txt
```

**Разбор пакетов:**

| Пакет | Зачем |
|-------|--------|
| `aiohttp` | клиент (`ClientSession`) и сервер (`web.Application`) |
| `aiohttp-swagger3` | OpenAPI 3 + Swagger UI (шаг 7) |
| `sqlalchemy` | async ORM |
| `alembic` | миграции таблиц |
| `asyncpg` | драйвер Postgres для приложения (`postgresql+asyncpg://`) |
| `psycopg2-binary` | sync-драйвер для Alembic (`postgresql://`) |
| `pydantic` | модели вход/выход API, проверка типов |
| `pydantic-settings` | `.env` → `Settings` с типами (шаг 3) |
| `pyyaml` | зависимость swagger3 / components.yaml |

---

## 4. PostgreSQL: база и пользователь

SQL уже лежит в `scripts/init_postgres.sql`. Учётки как везде: отдельный пользователь, своя БД, `CREATEDB` (Alembic может создавать служебные объекты).

Выполните **один раз** — скрипт под вашу ОС:

### Linux

```bash
./scripts/init_postgres.sh
```

Эквивалент вручную (как в магазине и Educa):

```bash
sudo -u postgres psql -v ON_ERROR_STOP=1 -f scripts/init_postgres.sql
```

### macOS

```bash
brew install postgresql@16
brew services start postgresql@16
# если psql не находится:
echo 'export PATH="$(brew --prefix postgresql@16)/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

./scripts/init_postgres_mac.sh
```

Homebrew не создаёт роль `postgres`: суперпользователь — ваш macOS-логин. Скрипт подключается к БД `postgres` текущим пользователем и при неудаче пробует `-U postgres`.

### Windows

1. Установите [PostgreSQL](https://www.postgresql.org/download/windows/) (запомните пароль пользователя `postgres`).
2. Добавьте в PATH что-то вроде `C:\Program Files\PostgreSQL\16\bin`.
3. Из корня репозитория:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\init_postgres.ps1
```

или двойной клик по `scripts\init_postgres.bat`.

Если спросит пароль — это пароль **суперпользователя** `postgres`, не `library_pass`. Можно заранее:

```powershell
$env:PGPASSWORD = "пароль_из_установщика"
```

Проверка (все ОС, пароль `library_pass`):

```bash
psql -h localhost -U library_user -d library_db -c "SELECT 1;"
```

> Если peer-auth мешает на Linux: обязательно `-h localhost`, чтобы пошёл парольный вход через TCP.

---

## 5. Файл `.env`

В корне уже есть `.env.example`. Скопируйте:

```bash
cp .env.example .env
```

Windows:

```powershell
Copy-Item .env.example .env
```

Содержимое:

```text
POSTGRES_DB=library_db
POSTGRES_USER=library_user
POSTGRES_PASSWORD=library_pass
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
APP_HOST=127.0.0.1
APP_PORT=8080
```

`.gitignore` уже игнорирует `.env` и `.venv`. Если создаёте файл сами, туда должны попасть:

```text
.venv/
__pycache__/
*.pyc
.env
*.db
```

---

## 6. Makefile

Создайте в корне `Makefile` (на Windows команды из него можно набирать вручную):

```makefile
PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: venv install migrate seed run client

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
```

Windows без make:

```powershell
.\.venv\Scripts\python -m app.main
.\.venv\Scripts\python -m task_1_client.main
.\.venv\Scripts\alembic upgrade head
```

---

## 7. Пустые пакеты

```bash
mkdir -p app/routes task_1_client alembic/versions
touch app/__init__.py app/routes/__init__.py task_1_client/__init__.py
```

Windows (PowerShell):

```powershell
New-Item -ItemType Directory -Force -Path app\routes, task_1_client, alembic\versions | Out-Null
New-Item -ItemType File -Force -Path app\__init__.py, app\routes\__init__.py, task_1_client\__init__.py | Out-Null
```

Структура сейчас:

```text
aiohttp_lesson/
├── .env
├── .env.example
├── .gitignore
├── Makefile
├── requirements.txt
├── app/
├── task_1_client/
├── alembic/versions/
├── scripts/
└── docs/
```

---

## ✅ Проверка

```bash
source .venv/bin/activate
python -c "import aiohttp, sqlalchemy, alembic, asyncpg, pydantic; print(aiohttp.__version__, pydantic.VERSION)"
psql -h localhost -U library_user -d library_db -c "SELECT 1;"
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | Импорт пакетов | версия aiohttp печатается без ошибки |
| ☐ | `psql … SELECT 1` | `1` |
| ☐ | В корне есть `.env` и `requirements.txt` | да |

**Все пункты отмечены?** → [step-02-client.md](step-02-client.md)
