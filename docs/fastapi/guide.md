# Мини-библиотека на FastAPI — обзор и архитектура

Пошаговая реализация — в [README.md](README.md). Этот файл — **карта переписывания**: что оставляем, чем FastAPI отличается от aiohttp, куда смотрит DI.

> **Правило:** не пишите код «вперёд гайда». Фаза 1 — то же API на FastAPI плюс PATCH. Фаза 2 — слой репозиториев, затем общий базовый класс. Фаза 3 — query-фильтры книг. Не смешивайте.

---

## 1. Зачем второй гайд

Первый урок собрал API на aiohttp: handlers, `request.app["session_factory"]`, YAML-docstring для Swagger.

Теперь то же приложение на FastAPI, чтобы увидеть три вещи:

1. **Роут — обычная функция с типами**, а не `web.Request` / `web.Response`.
2. **Dependency injection** вместо словаря приложения: сессию (потом репозиторий) объявляют в сигнатуре через `Depends`.
3. **OpenAPI из кода**: схемы Pydantic сами попадают в `/docs`, YAML и `aiohttp-swagger3` больше не нужны.

Клиент на jsonplaceholder **не переписываем**. БД, модели, Alembic, сиды — те же.

---

## 2. Цепочка запроса: было / станет

В aiohttp:

```text
Application.router  →  handler(request)
                            ↓
              request.app["session_factory"]()
                            ↓
                       PostgreSQL
```

**Фаза 1 — FastAPI «как есть»:**

```text
APIRouter  →  endpoint(session: SessionDep, payload: GenreCreate)
                            ↓
                    Depends(get_session)
                            ↓
                       PostgreSQL
```

**Фаза 2 — репозитории:**

```text
APIRouter  →  endpoint(repo: GenreRepoDep, payload: GenreCreate)
                            ↓
              Depends(get_genre_repository)
                            ↓
              Depends(get_session)     # один раз на запрос
                            ↓
                       PostgreSQL
```

Хендлер больше не знает, откуда взялась сессия. На фазе 2 — и как именно пишется SQL. На шаге 5 общий SQL живёт в `BaseRepository`, потомки задают `model`.

---

## 3. Что не трогаем

| Файл | Почему |
|------|--------|
| `app/config.py` | `Settings` уже на pydantic-settings |
| `app/models.py` | таблицы те же |
| `alembic/` | схема БД не меняется |
| `app/seed.py` | сиды ходят в SQLAlchemy напрямую |
| `task_1_client/` | отдельная задача на `ClientSession` |
| `.env` | хост/порт/Postgres те же |

Карта API **та же плюс PATCH** и query на списке книг: `/health`, `/genres`, `/authors`, `/books`. Порт по-прежнему `8080`.

---

## 4. Что переписываем

| Было (aiohttp) | Станет (FastAPI) |
|----------------|------------------|
| `web.Application` + `on_startup` | `FastAPI(lifespan=...)` |
| `request.app["session_factory"]` | `session: SessionDep` |
| `parse_body(GenreCreate, body)` | `payload: GenreCreate` в сигнатуре |
| `web.json_response(...)` | вернуть Pydantic-модель |
| docstring YAML + `openapi_components.yaml` | `response_model` + типы |
| `aiohttp-swagger3` | встроенные `/docs` и `/redoc` |
| `web.run_app` | Uvicorn |

---

## 5. Карта API

Сервер: `http://127.0.0.1:8080`. Swagger UI: `/docs` (FastAPI отдаёт его сам).

| Метод | URL | Назначение |
|-------|-----|------------|
| GET | `/health` | жив ли сервер |
| GET | `/genres` | список жанров |
| GET | `/genres/{genre_id}` | жанр по id |
| POST | `/genres` | создать жанр |
| PATCH | `/genres/{genre_id}` | частично обновить жанр |
| GET | `/authors` | список авторов |
| GET | `/authors/{author_id}` | автор по id |
| POST | `/authors` | создать автора |
| PATCH | `/authors/{author_id}` | частично обновить автора |
| GET | `/books` | список книг (`?title`, `?year`, `?author_id`, `?genre_id`) |
| GET | `/books/{book_id}` | книга по id |
| POST | `/books` | создать книгу |
| PATCH | `/books/{book_id}` | частично обновить книгу |

Авторизации нет — учебный CRUD. PATCH в aiohttp-уроке не было: его добавляем на шаге 3.

404 по-прежнему `{"error": "..."}`. 422 на пустой `name` отдаёт FastAPI сам (формат чуть другой, чем у `parse_body` — это нормально, разберём на шаге 3).

---

## 6. Структура репозитория после фазы 2

```text
aiohttp_lesson/
├── .env
├── requirements.txt          # + fastapi, uvicorn
├── alembic/                  # как было
├── app/
│   ├── main.py               # FastAPI + lifespan + exception handler
│   ├── config.py             # без изменений
│   ├── db.py                 # + get_session, SessionDep
│   ├── errors.py             # NotFoundError
│   ├── models.py             # без изменений
│   ├── schemas.py            # Create / Read / Update + BookFilters
│   ├── seed.py               # без изменений
│   ├── deps.py               # фаза 2: Depends на репозитории
│   ├── routes/
│   │   ├── __init__.py       # include_router
│   │   ├── genres.py
│   │   ├── authors.py
│   │   └── books.py
│   └── repositories/         # фаза 2
│       ├── __init__.py
│       ├── base.py           # шаг 5
│       ├── genres.py
│       ├── authors.py
│       └── books.py
├── task_1_client/            # aiohttp-клиент, как было
├── Dockerfile                # гайд Docker, после FastAPI
├── docker-compose.yml
├── docker-entrypoint.sh
└── docs/
    ├── remaining/            # первый гайд (aiohttp)
    ├── fastapi/              # этот гайд
    ├── docker/               # контейнеры
    ├── celery/               # очередь после Docker
    ├── pytest/               # автотесты после Celery
    └── graphql/              # книги с автором и жанром
```

На фазе 1 папки `repositories/` ещё нет — не создавайте её заранее. `base.py` появляется только на шаге 5.

---

## 7. Этапы

| Этап | Файл | Что реализуете |
|------|------|----------------|
| 1 | [step-01-setup.md](step-01-setup.md) | пакеты, что оставляем |
| 2 | [step-02-app.md](step-02-app.md) | FastAPI, lifespan, `Depends(get_session)`, `/health` |
| 3 | [step-03-routes.md](step-03-routes.md) | CRUD + PATCH, SQL ещё в роутах |
| 4 | [step-04-repos.md](step-04-repos.md) | репозитории (`get_all` / `get` / `add` / `update`) |
| 5 | [step-05-base.md](step-05-base.md) | общий `BaseRepository` |
| 6 | [step-06-filters.md](step-06-filters.md) | query-фильтры `GET /books` |
| 7 | [step-07-final.md](step-07-final.md) | чеклист и сравнение |

**Начните здесь:** [README.md](README.md)

Когда FastAPI-чеклист закрыт — контейнеры: [../docker/README.md](../docker/README.md).
