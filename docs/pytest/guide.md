# Автотесты — обзор и архитектура

Пошаговая реализация — в [README.md](README.md). Этот файл — **карта**: зачем своя база, чем тест отличается от `curl`, как не стереть сиды.

> **Правило:** не пишите код «вперёд гайда». Сначала pytest живой. Потом пустая `library_test`. Потом фикстуры. Потом кейсы.

---

## 1. Зачем четвёртый гайд

В каждом предыдущем шаге был блок «✅ Проверка» с `curl`. Он ломается, как только вы меняете код и забываете прогнать чеклист.

Тест — тот же чеклист, только его запускает программа:

```text
pytest
  → настроила Settings на library_test
  → alembic upgrade head
  → TestClient(app) → настоящие роуты → настоящий SQL
  → TRUNCATE после каждого теста
  → 0 failed  или  красная строка с diff
```

| | `curl` руками | pytest + тестовая БД |
|---|---------------|----------------------|
| Когда гоняете | когда вспомнили | перед коммитом, в CI |
| Что сравнивает | глаз | `assert` |
| Какая база | `library_db` (сиды) | `library_test` (пустая, режем) |
| Скорость | секунды + вы | секунды, но без вас |

Это **интеграционные** тесты: падает репозиторий — падает тест. Не «роут вернул JSON, если подсунуть утку». Так ловятся сломанный `selectinload`, забытый `commit`, кривой FK.

Фейк-репозиторий и `dependency_overrides` остаются полезны для узких юнит-тестов. В этом уроке их нет: цель — прогнать цепочку до Postgres.

---

## 2. Почему не `library_db`

Тесты будут **удалять все строки** после каждого кейса (`TRUNCATE`). Если ткнуть в базу, куда вы залили сиды и ходите из Swagger:

```text
pytest → TRUNCATE books, authors, genres
make run → GET /books → []
```

Сиды пропали. Поэтому вторая база с другим именем и, лучше, другим портом.

```text
library_db      :5432  (хост) / :5433 (Compose db)
    ↑ сиды, ручной curl, DBeaver «как живу»

library_test    :5434  (контейнер db_test)  или  та же Postgres, другая БД
    ↑ только pytest, можно резать
```

Один пользователь `library_user` — две базы. Права те же, данные разные.

---

## 3. Цепочка запроса в тесте

```text
TestClient → тот же FastAPI (без отдельного Uvicorn)
                → Depends(get_session)   настоящий
                → BookRepository         настоящий
                → PostgreSQL library_test
```

```text
POST /exports  (eager)
  → export_catalog()  в том же процессе
  → sync SELECT в library_test
  → файл во временной папке
```

Uvicorn на 8080 не нужен. Redis и воркер на шаге 5 тоже не нужны: Celery выполняет задачу сразу (`task_always_eager`).

---

## 4. Что не тестируем

| Не делаем | Почему |
|-----------|--------|
| Живой Redis + воркер | очередь проверяем eager-режимом; брокер — отдельный чеклист Celery |
| `task_1_client` | ходит на jsonplaceholder |
| Покрытие 100% | учебный набор: health, CRUD, 404, 422, экспорт |
| Тесты в `library_db` | сотрёте сиды |

---

## 5. Структура после гайда

```text
aiohttp_lesson/
├── pytest.ini
├── tests/
│   ├── conftest.py           # env → library_test, migrate, truncate, client
│   ├── test_health.py
│   ├── test_books.py
│   └── test_exports.py
├── app/                      # не меняем ради тестов
└── docs/pytest/
```

`tests/` — не пакет приложения. Имена: `test_*.py`, функции `test_*`.

---

## 6. Этапы

| Этап | Файл | Что реализуете |
|------|------|----------------|
| 1 | [step-01-setup.md](step-01-setup.md) | pytest, пустой тест |
| 2 | [step-02-testdb.md](step-02-testdb.md) | поднять `library_test` |
| 3 | [step-03-fixtures.md](step-03-fixtures.md) | conftest + health |
| 4 | [step-04-api.md](step-04-api.md) | книги через HTTP |
| 5 | [step-05-exports.md](step-05-exports.md) | экспорт в тестовую БД |
| 6 | [step-06-final.md](step-06-final.md) | чеклист |

**Начните здесь:** [README.md](README.md)
