# Шаг 9 — Сиды и финальный прогон

**Предыдущий:** [step-08-swagger.md](step-08-swagger.md) · **К карте:** [guide.md](../guide.md)

## Задача

Заполнить БД тремя жанрами, авторами и книгами и пройти чеклист двух задач урока.

---

## 1. `app/seed.py`

Скрипт идемпотентный: если жанры уже есть — выходим.

```python
import asyncio

from sqlalchemy import select

from app.db import make_engine, make_session_factory
from app.models import Author, Book, Genre

GENRES = ["фантастика", "детектив", "поэзия"]
AUTHORS = [
    {"name": "Аркадий Стругацкий", "bio": "Советский писатель-фантаст"},
    {"name": "Агата Кристи", "bio": "Детективы"},
    {"name": "Анна Ахматова", "bio": "Поэт"},
]
BOOKS = [
    {
        "title": "Пикник на обочине",
        "year": 1972,
        "author": "Аркадий Стругацкий",
        "genre": "фантастика",
    },
    {
        "title": "Убийство в «Восточном экспрессе»",
        "year": 1934,
        "author": "Агата Кристи",
        "genre": "детектив",
    },
    {
        "title": "Реквием",
        "year": 1963,
        "author": "Анна Ахматова",
        "genre": "поэзия",
    },
]


async def seed() -> None:
    engine = make_engine()
    session_factory = make_session_factory(engine)
    async with session_factory() as session:
        already = await session.scalar(select(Genre.id).limit(1))
        if already is not None:
            print("Сиды уже есть, пропускаем.")
            await engine.dispose()
            return

        genres = {name: Genre(name=name) for name in GENRES}
        session.add_all(genres.values())

        authors = {
            item["name"]: Author(name=item["name"], bio=item["bio"])
            for item in AUTHORS
        }
        session.add_all(authors.values())
        await session.flush()

        books = [
            Book(
                title=item["title"],
                year=item["year"],
                author_id=authors[item["author"]].id,
                genre_id=genres[item["genre"]].id,
            )
            for item in BOOKS
        ]
        session.add_all(books)
        await session.commit()
        print(
            f"Добавлено: {len(genres)} жанра, {len(authors)} автора, {len(books)} книги."
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
```

`flush()` после авторов/жанров нужен, чтобы у объектов появились `id` до сборки `Book`.

Если на шаге 6 уже создавали строки руками — сид пропустит всё (проверка «есть любой жанр»). Для чистого прогона:

```bash
psql -h localhost -U library_user -d library_db -c "TRUNCATE books, authors, genres RESTART IDENTITY CASCADE;"
python -m app.seed
```

---

## 2. Запуск

```bash
source .venv/bin/activate
alembic upgrade head
python -m app.seed
python -m app.main
```

Клиент (задача 1, jsonplaceholder):

```bash
python -m task_1_client.main
```

---

## ✅ Чеклист ТЗ

### Задача 1 — клиент

| ☐ | Проверка |
|---|----------|
| ☐ | Один `ClientSession` на несколько запросов |
| ☐ | Параллельные GET через `gather` |
| ☐ | POST JSON |
| ☐ | Демонстрация таймаута |

### Задача 2 — сервер

| ☐ | Проверка |
|---|----------|
| ☐ | PostgreSQL, учётка из `scripts/init_postgres.sql` |
| ☐ | `Settings` из pydantic-settings, не `os.getenv` |
| ☐ | Три модели SQLAlchemy + схемы Pydantic |
| ☐ | Alembic `upgrade head` |
| ☐ | GET/POST `/genres`, `/authors`, `/books` |
| ☐ | Пустой `name` на POST → `422` |
| ☐ | Swagger UI: [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs) |
| ☐ | Сиды: три книги в `GET /books` |

```bash
curl -s http://127.0.0.1:8080/books | python -m json.tool
```

Ожидание: три объекта, у каждого `author` и `genre` строками.

---

## Типичные ошибки

| Симптом | Что проверить |
|---------|----------------|
| `password authentication failed` | `.env` совпадает с SQL; `psql -h localhost` |
| `permission denied for schema public` | скрипт init не дошёл до `\c library_db` и `GRANT` (PG 15+) |
| `TypeError: health() missing ... '_request'` | параметр handler назовите `request` |
| `ValidationError` при импорте `settings` | `.env`: `APP_PORT` должен быть числом |
| POST пустого `name` даёт 500 | `parse_body` / `GenreCreate` не подключены |
| Swagger пустой / 404 на методах | роуты через `swagger.add_routes`, не `app.router.add_get` |
| Книга без имени автора в JSON | забыли `selectinload(Book.author)` |
| `alembic: No module named app` | запускаете не из корня репозитория |

Карта проекта: [guide.md](../guide.md)
