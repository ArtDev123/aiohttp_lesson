# Шаг 6 — Alembic: миграции схемы

**Предыдущий:** [step-05-models.md](step-05-models.md) · **Следующий:** [step-07-routes.md](step-07-routes.md)

## Задача

Создать таблицы `genres`, `authors`, `books` в PostgreSQL через Alembic — не через `create_all()` в рантайме.

---

## Теория: зачем Alembic, а не `create_all`

| Способ | Когда ок | Минус |
|--------|----------|--------|
| `Base.metadata.create_all` | прототип на один вечер | не умеет *менять* уже существующие таблицы |
| **Alembic** | любой живой проект | нужен `env.py` + файлы ревизий |

Приложение ходит в БД через **asyncpg**. Alembic проще крутить **синхронно** (`postgresql://` + `psycopg2`) — тот же хост/имя БД, другой драйвер. URL берём из `settings.database_url_sync`.

```text
models.py (Base.metadata)
        │
        ▼
alembic/env.py  →  target_metadata = Base.metadata
        │
        ▼
alembic/versions/0001_initial.py  →  CREATE TABLE ...
        │
        ▼
alembic upgrade head  →  PostgreSQL
```

---

## 1. `alembic.ini`

В корне проекта:

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = postgresql://library_user:library_pass@localhost:5432/library_db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

`sqlalchemy.url` в ini — запасной. Реальный URL подставим в `env.py` из `.env`.

---

## 2. `alembic/script.py.mako`

Шаблон новых ревизий (`alembic revision`):

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

---

## 3. `alembic/env.py`

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


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

`prepend_sys_path = .` в ini добавляет корень проекта в `sys.path`, поэтому `from app.models import Base` работает.

---

## 4. Первая ревизия — `alembic/versions/0001_initial.py`

Пишем руками (без `alembic revision --autogenerate`), чтобы видеть SQL:

```python
"""initial tables: genres, authors, books

Revision ID: 0001
Revises:
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "genres",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "authors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
    )
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("genre_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["authors.id"]),
        sa.ForeignKeyConstraint(["genre_id"], ["genres.id"]),
    )


def downgrade() -> None:
    op.drop_table("books")
    op.drop_table("authors")
    op.drop_table("genres")
```

`books` создаём последней: FK ссылаются на уже существующие таблицы.

---

## 5. Применить миграцию

```bash
source .venv/bin/activate
alembic upgrade head
# или: make migrate
```

---

## ✅ Проверка

```bash
alembic current
psql -h localhost -U library_user -d library_db -c "\dt"
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | `alembic upgrade head` | `Running upgrade -> 0001` |
| ☐ | `alembic current` | `0001` |
| ☐ | `\dt` | `authors`, `books`, `genres` (+ `alembic_version`) |

**Все пункты отмечены?** → [step-07-routes.md](step-07-routes.md)
