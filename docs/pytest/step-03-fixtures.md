# Шаг 3 — Фикстуры: Settings, Alembic, `TRUNCATE`, клиент

**Предыдущий:** [step-02-testdb.md](step-02-testdb.md) · **Следующий:** [step-04-api.md](step-04-api.md)

## Задача

Научить pytest открывать **`library_test`**, накатывать миграции один раз за сессию и после каждого теста вычищать таблицы. Закрыть `/health` живым запросом — уже в Postgres, без заглушки сессии.

---

## Теория: Settings создаётся один раз

```python
# app/config.py
settings = Settings()
```

Объект читает `.env` и переменные окружения **в момент импорта**. Если сначала сделать `from app.main import app`, в `settings.postgres_db` уже `library_db`. Поздняя правка `os.environ` его не пересоберёт.

Поэтому в `conftest.py` порядок жёсткий:

```text
1. os.environ["POSTGRES_DB"] = "library_test"
2. os.environ["POSTGRES_PORT"] = "5434"
3. только потом  from app.config import settings
4. потом        from app.main import app
```

pytest **сначала** грузит `conftest.py`, потом `test_*.py`. Не импортируйте `app` в тестовых файлах сверху — берите `client` из фикстуры. Тогда цепочка не разъедется.

`pydantic-settings` отдаёт приоритет **окружению** над файлом `.env`. Строка в conftest победит `POSTGRES_DB=library_db` на диске. Процесс `make run` conftest не видит — он по-прежнему на сидах.

---

## Теория: клиент без сервера

`TestClient` бьёт в ASGI **в том же процессе**. Uvicorn на 8080 не нужен.

```text
curl http://127.0.0.1:8080/health
        → сеть → Uvicorn → app → library_db

client.get("/health")
        → вызов ASGI → app → library_test
```

`with TestClient(app) as client:` запускает **lifespan**: `make_engine()` с уже подменённым URL. Engine ленивый — коннект на первом запросе. `/health` просит `SessionDep`, сессия откроется в тестовую базу.

Если база не запущена — тест красный. Это правильно: интеграция без Postgres бессмысленна.

---

## Теория: схема один раз, строки — каждый тест

| Как часто | Что | Зачем |
|-----------|-----|--------|
| раз на `pytest` | `alembic upgrade head` | таблицы как в проде |
| после **каждого** теста | `TRUNCATE ... RESTART IDENTITY` | кейсы не видят чужие строки |

`TRUNCATE` быстрее `DROP SCHEMA` и не трогает `alembic_version`. `RESTART IDENTITY` сбрасывает `id` в 1: после `POST` можно ждать `{"id": 1}`, не «зависит от того, сколько тестов уже прошло».

`CASCADE` нужен из-за FK: нельзя вычистить `authors`, пока на них смотрят `books`. Одна команда режет три таблицы в правильном порядке.

Не вызывайте `app.seed` в фикстуре. Сиды — для ручной игры. Тест сам создаёт жанр и автора через API: так вы ещё и `POST` проверяете.

Миграции гоняем **кодом**, не шеллом:

```python
from alembic import command
from alembic.config import Config

command.upgrade(Config("alembic.ini"), "head")
```

`alembic/env.py` берёт URL из `settings` — а settings уже смотрит на `library_test`. `make migrate` из другого терминала уйдёт в `.env` / `library_db`. Не путайте.

---

## Теория: фикстура

Фикстура — функция, которую pytest вызывает ради теста. Результат попадает в аргумент с тем же именем.

`scope="session"` — один раз на весь прогон (миграции). Без scope — на каждый тест (`TRUNCATE`, клиент).

`yield`, не `return`: код после `yield` — уборка.

`autouse=True` у очистки: не нужно писать `clean_tables` в каждом тесте. Забыли указать — таблицы всё равно вырежутся.

---

## 1. `tests/conftest.py`

Новый файл. Импорты `app` — **ниже** блока `os.environ`.

```python
from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

os.environ["POSTGRES_DB"] = "library_test"
os.environ["POSTGRES_PORT"] = os.environ.get("TEST_POSTGRES_PORT", "5434")

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

TABLES = "books, authors, genres"


@pytest.fixture(scope="session", autouse=True)
def apply_migrations() -> None:
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture(autouse=True)
def clean_tables(apply_migrations: None) -> Generator[None, None, None]:
    yield
    engine = create_engine(settings.database_url_sync)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    engine.dispose()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
```

`# noqa: E402` — импорт не наверху файла, линтер молчит. Это исключение осмысленное.

### Разбор `apply_migrations`

`scope="session"` + `autouse=True`: любой тест сначала получит схему. Повторный `upgrade head` дешёвый: Alembic видит текущую ревизию и ничего не делает.

`Config("alembic.ini")` ищет файл от **текущей директории**. Запускайте `pytest` из корня репозитория.

### Разбор `clean_tables`

Чистка **после** теста (`yield` первым). Упавший кейс тоже оставляет базу пустой для следующего.

Sync-движок здесь специально: короче, чем async, и тот же `database_url_sync`, что у Alembic. `engine.begin()` — одна транзакция на TRUNCATE.

Не режьте `alembic_version`. Иначе следующий тест решит, что схемы нет, а `upgrade` на session уже отработал.

### Разбор `client`

Никаких `dependency_overrides`. Сессия настоящая. Клиент не session-scoped: каждый тест входит и выходит из lifespan. Для учебного объёма это просто. Engine создаётся снова — чуть медленнее, зато нет сюрпризов с закрытым loop.

---

## 2. `tests/test_health.py`

Можно оставить `test_smoke.py`. Рядом — первый удар в приложение.

```python
from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

Если Postgres на 5434 не запущена — здесь будет ошибка соединения, не `{"status":"ok"}`.

---

## 3. Порт не 5434

Локальный `createdb` на 5432:

```bash
TEST_POSTGRES_PORT=5432 pytest
```

`os.environ.get("TEST_POSTGRES_PORT", "5434")` подхватит. `POSTGRES_PORT` в `.env` при этом 5432 — его перекрывает conftest только внутри pytest.

---

## Разбор: кто куда ходит во время `pytest`

```text
pytest-процесс
  Settings.postgres_db = library_test
  Settings.postgres_port = 5434
        │
        ├─ Alembic          → localhost:5434/library_test
        ├─ TestClient/async → тот же URL
        └─ TRUNCATE sync    → тот же URL

другой терминал: python -m app.main
  Settings из .env          → localhost:5432/library_db
```

Два процесса, два URL. Не используйте один и тот же `psql` «посмотреть, что тест написал», подключившись к сидовой базе.

---

## ✅ Проверка

Контейнер с шага 2 должен крутиться.

```bash
source .venv/bin/activate
pytest tests/test_health.py -vv
```

```bash
docker exec library-test-db \
  psql -U library_user -d library_test -c '\dt'
```

После прогона в `library_test` есть `authors`, `books`, `genres`, `alembic_version`. Строк в книгах нет (TRUNCATE).

```bash
psql -U library_user -d library_db -c "SELECT count(*) FROM books;"
```

Сиды на месте (если смотрите локальный 5432). Не 0 из-за тестов.

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | `pytest tests/test_health.py` | `passed` |
| ☐ | без контейнера | health **красный**, connection refused |
| ☐ | `\dt` в `library_test` | три таблицы + `alembic_version` |
| ☐ | строки в `library_db` | сиды не тронуты |
| ☐ | Uvicorn не запущен | тесты всё равно зелёные |

**Все пункты отмечены?** → [step-04-api.md](step-04-api.md)
