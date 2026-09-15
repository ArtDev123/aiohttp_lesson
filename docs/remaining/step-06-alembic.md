# Шаг 6 — Alembic: `init` и autogenerate

**Предыдущий:** [step-05-models.md](step-05-models.md) · **Следующий:** [step-07-routes.md](step-07-routes.md)

## Задача

Инициализировать Alembic командой, поправить `env.py` под наши модели и `.env`, затем **сгенерировать** первую миграцию и применить её. Файлы `alembic.ini` / `env.py` / ревизии руками не пишем.

---

## Теория: три команды

| Команда | Что делает | Когда |
|---------|------------|--------|
| `alembic init alembic` | каркас: `alembic.ini`, `alembic/env.py`, пустой `versions/` | один раз |
| `revision --autogenerate` | сравнивает `Base.metadata` с БД, пишет Python-ревизию | после изменения моделей |
| `upgrade head` | выполняет `upgrade()` у ещё не применённых ревизий | чтобы схема в Postgres догнала код |

```text
make alembic-init
        │
        ▼
env.py: target_metadata = Base.metadata
        + URL из settings
        │
        ▼
make migrations m="initial tables"   # autogenerate
        │
        ▼
смотрите alembic/versions/*.py
        │
        ▼
make migrate                         # upgrade head
```

`create_all()` в рантайме для живого проекта не подходит: не умеет *менять* уже существующие таблицы. Autogenerate тоже не магия — **всегда читайте** сгенерированный файл (rename колонки, типы Enum он часто не видит).

Приложение ходит в БД через **asyncpg**. Alembic проще крутить **синхронно** (`postgresql://` + `psycopg2`) — URL из `settings.database_url_sync`.

---

## 1. Каркас — один раз

Из корня репозитория, venv активен:

```bash
make alembic-init
# то же самое: alembic init alembic
```

Появятся `alembic.ini` и каталог `alembic/` (`env.py`, `script.py.mako`, `versions/`). Если папка уже есть — команда упадёт: не запускайте init повторно.

Windows:

```powershell
.\.venv\Scripts\alembic init alembic
```

В свежем `alembic.ini` уже есть `prepend_sys_path = .` — корень проекта в `sys.path`, `from app.models import Base` сработает. `sqlalchemy.url` в ini можно не трогать: URL подставим в `env.py`.

---

## 2. Подключить модели и `.env` в `alembic/env.py`

После `init` в файле примерно так:

```python
# target_metadata = mymodel.Base.metadata
target_metadata = None
```

Замените верх файла (импорты + metadata + URL) на:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
```

Функции `run_migrations_offline` / `run_migrations_online` **оставьте как сгенерировал init** — они уже используют `target_metadata` и `sqlalchemy.url`.

Если autogenerate выдаст пустую ревизию (`pass` в `upgrade`) — `target_metadata` всё ещё `None` или модели не импортированы.

---

## 3. Сгенерировать и применить

```bash
make migrations m="initial tables"
# откройте alembic/versions/0001_*.py — должны быть create_table genres/authors/books
make migrate
```

Цели из Makefile шага 1:

- `migrations` → `alembic revision --autogenerate -m "..." --rev-id 0001`
- `migrate` → `alembic upgrade head`

Следующая ревизия получит `0002`, если не передать `id=`:

```bash
make migrations m="add book isbn"
make migrations m="add book isbn" id=0005
```

Windows:

```powershell
.\.venv\Scripts\alembic revision --autogenerate -m "initial tables"
.\.venv\Scripts\alembic upgrade head
```

Дальше тот же цикл: поменяли `models.py` → `make migrations m="..."` → глянули файл → `make migrate`.

---

## ✅ Проверка

```bash
alembic current
psql -h localhost -U library_user -d library_db -c "\dt"
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | `make alembic-init` | есть `alembic.ini` и `alembic/env.py` |
| ☐ | В `env.py` `target_metadata = Base.metadata` | да |
| ☐ | `make migrations m="initial tables"` | файл в `alembic/versions/` с `create_table` |
| ☐ | `make migrate` | `Running upgrade -> 0001` (id может чуть отличаться) |
| ☐ | `alembic current` | ревизия не `None` |
| ☐ | `\dt` | `authors`, `books`, `genres` (+ `alembic_version`) |

**Все пункты отмечены?** → [step-07-routes.md](step-07-routes.md)
