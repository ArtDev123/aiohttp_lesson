# Шаг 6 — Финальный прогон

**Предыдущий:** [step-05-exports.md](step-05-exports.md) · **К карте:** [guide.md](guide.md)

## Задача

Прогнать весь набор одним `pytest` против `library_test` и понять, что зелёный прогон доказывает.

---

## 1. Команда

Контейнер `library-test-db` (или свой `createdb`) запущен. Uvicorn, Redis, воркер — не обязательны.

```bash
source .venv/bin/activate
pytest
```

Другой порт:

```bash
TEST_POSTGRES_PORT=5432 pytest -q
```

Один файл:

```bash
pytest tests/test_books.py
```

Makefile по желанию:

```makefile
test:
	$(BIN)/pytest
```

---

## 2. Чеклист

| ☐ | Проверка |
|---|----------|
| ☐ | `pytest` → `0 failed` |
| ☐ | есть health, книги, 422, 404, экспорт (если делали шаг 5) |
| ☐ | без `library_test` прогон красный |
| ☐ | `library_db` после прогона с сидами, как была |
| ☐ | в `library_test` после прогона таблицы пустые, `alembic_version` на месте |
| ☐ | `python -m app.main` открывает сидовую базу, не тестовую |
| ☐ | повторный `pytest` снова зелёный (id с 1) |
| ☐ | 404 книги — `{"error":"..."}`, не `{"detail":"..."}` |
| ☐ | `POST /exports` в тесте — `202` и файл с книгами из `POST /books` |

---

## 3. Что покрыли

```text
GET  /health                 живая сессия в library_test
GET  /books  (пусто)         []
POST /genres /authors /books каталог
GET  /books                  selectinload, имена в JSON
GET  /books/999              NotFoundError
POST /books чужой author_id  404 репозитория
PATCH /books/{id}            exclude_unset + UPDATE
POST /genres ""              422
POST /exports                eager SELECT + файл
GET  /exports/{id}/file      FileResponse
GET  /exports/нет/file       404
```

Цепочка:

```text
conftest: POSTGRES_DB=library_test
  → alembic upgrade
  → TestClient + настоящий Depends
  → PostgreSQL :5434
  → TRUNCATE
```

---

## 4. Было / стало

| Тема | До | После |
|------|----|--------|
| Проверка | `curl` в `library_db` | `pytest` в `library_test` |
| Данные | сиды руками | `POST` в тесте, потом `TRUNCATE` |
| Очередь | Redis + worker | eager, тот же SQL |
| Риск стереть сиды | высокий, если «почистить таблицу» | низкий: другой каталог и порт |

`dependency_overrides` из FastAPI-гайда никуда не делись — ими пишут юнит-тесты роута без SQL. Здесь сознательно не использовали.

---

## 5. Типичные ошибки

| Симптом | Что проверить |
|---------|----------------|
| `connection refused` :5434 | контейнер не запущен, опечатка в порту |
| тесты пишут в `library_db` | импорт `app` раньше, чем `os.environ` в conftest |
| `alembic: Can't locate revision` | `pytest` не из корня, не видит `alembic.ini` |
| `id == 2` во втором прогоне | нет `RESTART IDENTITY` |
| тесты видят чужие книги | нет `TRUNCATE` или режете не те таблицы |
| сиды пропали | TRUNCATE ушёл в `library_db` — URL settings |
| `export` пишет в `exports/` репо | не патчили `EXPORT_DIR` в **двух** модулях |
| `POST /exports` лезет в Redis | нет `task_always_eager` |
| `relation "books" does not exist` | миграции не отработали на тестовой базе |

---

## 6. Куда расти (не в этом уроке)

- Отдельный `docker-compose.test.yml` и CI: `compose up db_test` → `pytest` → `down`.
- Транзакция на тест вместо `TRUNCATE` (сложно, пока репозиторий сам делает `commit`).
- `coverage run -m pytest`.
- Юнит-тесты роутов через `dependency_overrides`, когда SQL уже закрыт этим гайдом.

Карта раздела: [guide.md](guide.md) · Celery: [../celery/README.md](../celery/README.md) · FastAPI: [../fastapi/README.md](../fastapi/README.md)
