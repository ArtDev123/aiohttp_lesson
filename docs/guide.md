# Мини-библиотека на aiohttp — обзор и архитектура

Пошаговая реализация — в [`remaining/`](remaining/README.md). Этот файл — **карта проекта**: две задачи урока, модели, API, порядок сборки.

> **Правило:** не пишите код «вперёд гайда». Сначала клиент, потом каркас сервера, потом модели и миграции, потом CRUD и Swagger.

---

## 1. Две задачи урока

| # | Что | Зачем |
|---|-----|--------|
| 1 | aiohttp **клиент** | `ClientSession`, параллельные GET, POST, таймаут |
| 2 | Мини **веб-приложение** | async-сервер, PostgreSQL, 3 модели, Swagger |

Клиент ходит на публичный JSONPlaceholder — сервер библиотеки для него не нужен.

Сервер — учебное API библиотеки: жанры, авторы, книги.

---

## 2. Цепочка запроса в aiohttp

В Django / DRF:

```text
URL → View / ViewSet → Serializer → ORM → PostgreSQL
```

В aiohttp:

```text
Application.router  →  handler (async def)
                            ↓
                    SQLAlchemy AsyncSession
                            ↓
                       PostgreSQL
```

Handler — обычная async-функция: принимает `web.Request`, возвращает `web.Response`.

Вход и выход JSON проверяет **Pydantic** (`GenreCreate` / `GenreRead`). Настройки — `pydantic-settings.BaseSettings` (читает `.env`). Мини-гайд: [step-03-pydantic.md](remaining/step-03-pydantic.md).

Swagger (`aiohttp-swagger3`) **перехватывает регистрацию роутов**: их вешают через `swagger.add_routes()`, а не через `app.router.add_get` напрямую. Иначе UI их не увидит.

**Пример:** клиент создаёт книгу `POST /books`

1. Swagger инжектит JSON в `body: dict`.
2. `BookCreate.model_validate(body)` проверяет поля (`Field`, типы).
3. Handler достаёт `AsyncSession` из `request.app["session_factory"]`.
4. Проверяет, что автор и жанр существуют.
5. `session.add(Book(...))` → `commit`.
6. `BookRead.from_book(book).model_dump()` → ответ `201`.

---

## 3. Структура данных

```text
Genre
  └── Book (FK genre_id)
Author
  └── Book (FK author_id)
```

| Модель | Поля | Связи |
|--------|------|--------|
| `Genre` | `id`, `name` | один жанр → много книг |
| `Author` | `id`, `name`, `bio` | один автор → много книг |
| `Book` | `id`, `title`, `year`, `author_id`, `genre_id` | книга принадлежит автору и жанру |

---

## 4. Карта API (целевая)

Сервер: `http://127.0.0.1:8080`. Swagger UI (с шага 8): `/docs`.


| Метод | URL | Назначение |
|-------|-----|------------|
| GET | `/health` | жив ли сервер |
| GET | `/genres` | список жанров |
| GET | `/genres/{genre_id}` | жанр по id |
| POST | `/genres` | создать жанр |
| GET | `/authors` | список авторов |
| GET | `/authors/{author_id}` | автор по id |
| POST | `/authors` | создать автора |
| GET | `/books` | список книг |
| GET | `/books/{book_id}` | книга по id |
| POST | `/books` | создать книгу |

Авторизации нет — учебный CRUD.

---

## 5. Структура репозитория (целевая)

```text
aiohttp_lesson/
├── .env                      # секреты (не в git)
├── .env.example
├── .gitignore
├── Makefile
├── requirements.txt
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/0001_initial.py
├── app/
│   ├── main.py               # create_app + swagger
│   ├── config.py             # Settings (pydantic-settings)
│   ├── db.py
│   ├── models.py             # SQLAlchemy
│   ├── schemas.py            # Pydantic Create/Read
│   ├── seed.py
│   ├── openapi_components.yaml
│   └── routes/
│       ├── __init__.py
│       ├── genres.py
│       ├── authors.py
│       └── books.py
├── task_1_client/
│   └── main.py
├── scripts/
│   ├── init_postgres.sql
│   ├── init_postgres.sh          # Linux
│   ├── init_postgres_mac.sh      # macOS
│   ├── init_postgres.ps1         # Windows
│   └── init_postgres.bat
└── docs/                     # этот гайд
```

---

## 6. Этапы разработки


| Этап | Файл | Что реализуете |
|------|------|----------------|
| 1 | [step-01-env.md](remaining/step-01-env.md) | venv, пакеты, PostgreSQL, каркас |
| 2 | [step-02-client.md](remaining/step-02-client.md) | aiohttp `ClientSession` |
| 3 | [step-03-pydantic.md](remaining/step-03-pydantic.md) | Pydantic + `Settings` |
| 4 | [step-04-app.md](remaining/step-04-app.md) | `web.Application`, `/health` |
| 5 | [step-05-models.md](remaining/step-05-models.md) | Genre, Author, Book |
| 6 | [step-06-alembic.md](remaining/step-06-alembic.md) | миграции схемы |
| 7 | [step-07-routes.md](remaining/step-07-routes.md) | CRUD + Pydantic-схемы |
| 8 | [step-08-swagger.md](remaining/step-08-swagger.md) | Swagger UI |
| 9 | [step-09-final.md](remaining/step-09-final.md) | сиды и финальный прогон |

**Начните здесь:** [remaining/README.md](remaining/README.md)
