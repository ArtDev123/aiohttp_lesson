# Шаг 7 — CRUD: жанры, авторы, книги

**Предыдущий:** [step-06-alembic.md](step-06-alembic.md) · **Следующий:** [step-08-swagger.md](step-08-swagger.md)

## Задача

Сделать JSON API: список / деталь / создание для трёх сущностей. Вход и выход — Pydantic (гайд на шаге 3). Docstring с `---` — заготовка OpenAPI для шага 8.

---

## Теория: handler + AsyncSession + Pydantic

```text
POST /genres  { "name": "..." }
    → swagger инжектит body: dict
    → GenreCreate.model_validate(body)   # типы и Field
    → session.add(Genre(name=payload.name))
    → GenreRead.model_validate(genre).model_dump()
    → web.json_response(...)
```

| Приём | Зачем |
|-------|--------|
| `async with session_factory()` | открыли транзакцию, закрыли соединение |
| `session.get(Model, id)` | PK lookup |
| `selectinload(Book.author)` | чтобы `BookRead.from_book` видел имя автора |
| `GenreCreate.model_validate` | не тащить сырой dict в ORM |
| `GenreRead.model_dump()` | стабильный JSON ответа |
| `status=404` | нет строки — не 500 |

Path-параметр `{book_id}` aiohttp сам не превратит в аргумент функции. Сразу пишем сигнатуры swagger3:

- `request: web.Request` — всегда
- `genre_id: int` / `author_id: int` / `book_id: int` — из path
- `body: dict` — JSON POST, дальше отдаём в Pydantic

Без swagger3 это **сломается** (`missing argument`). Компромисс: **уже здесь** `swagger.add_routes`, UI — на шаге 8.

---

## 1. `app/schemas.py`

Напоминание из [шага 3](step-03-pydantic.md): `Create` — вход, `Read` — выход. `from_attributes=True` читает поля с ORM.

```python
from aiohttp import web
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.models import Book


class ErrorRead(BaseModel):
    error: str


class GenreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class GenreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class AuthorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    bio: str | None = None


class AuthorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    bio: str | None


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    year: int | None = Field(default=None, ge=1, le=2100)
    author_id: int = Field(ge=1)
    genre_id: int = Field(ge=1)


class BookRead(BaseModel):
    id: int
    title: str
    year: int | None
    author_id: int
    genre_id: int
    author: str
    genre: str

    @classmethod
    def from_book(cls, book: Book) -> "BookRead":
        return cls(
            id=book.id,
            title=book.title,
            year=book.year,
            author_id=book.author_id,
            genre_id=book.genre_id,
            author=book.author.name,
            genre=book.genre.name,
        )


def parse_body(model_cls, data: dict):
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise web.HTTPUnprocessableEntity(
            text=exc.json(),
            content_type="application/json",
        ) from exc


def to_json(model: BaseModel) -> dict:
    return model.model_dump()
```

**Разбор:** `BookRead` не может взять `author: str` с ORM через `from_attributes` — там объект `Author`. Поэтому фабрика `from_book`. `parse_body` превращает `ValidationError` в `422`, не в 500.

---

## 2. `app/routes/genres.py`

```python
from aiohttp import web
from sqlalchemy import select

from app.models import Genre
from app.schemas import ErrorRead, GenreCreate, GenreRead, parse_body, to_json


async def list_genres(request: web.Request) -> web.Response:
    """
    ---
    summary: Список жанров
    tags:
      - genres
    responses:
      "200":
        description: Все жанры
        content:
          application/json:
            schema:
              type: array
              items:
                $ref: "#/components/schemas/Genre"
    """
    async with request.app["session_factory"]() as session:
        result = await session.execute(select(Genre).order_by(Genre.id))
        genres = result.scalars().all()
        return web.json_response([to_json(GenreRead.model_validate(genre)) for genre in genres])


async def get_genre(request: web.Request, genre_id: int) -> web.Response:
    """
    ---
    summary: Жанр по id
    tags:
      - genres
    parameters:
      - name: genre_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      "200":
        description: Найден
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Genre"
      "404":
        description: Нет такого жанра
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Error"
    """
    async with request.app["session_factory"]() as session:
        genre = await session.get(Genre, genre_id)
        if genre is None:
            return web.json_response(to_json(ErrorRead(error="Жанр не найден")), status=404)
        return web.json_response(to_json(GenreRead.model_validate(genre)))


async def create_genre(request: web.Request, body: dict) -> web.Response:
    """
    ---
    summary: Добавить жанр
    tags:
      - genres
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - name
            properties:
              name:
                type: string
    responses:
      "201":
        description: Создан
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Genre"
    """
    payload = parse_body(GenreCreate, body)
    async with request.app["session_factory"]() as session:
        genre = Genre(name=payload.name)
        session.add(genre)
        await session.commit()
        await session.refresh(genre)
        return web.json_response(to_json(GenreRead.model_validate(genre)), status=201)
```

---

## 3. `app/routes/authors.py`

Тот же каркас, что у жанров:

```python
from aiohttp import web
from sqlalchemy import select

from app.models import Author
from app.schemas import AuthorCreate, AuthorRead, ErrorRead, parse_body, to_json


async def list_authors(request: web.Request) -> web.Response:
    """
    ---
    summary: Список авторов
    tags:
      - authors
    responses:
      "200":
        description: Все авторы
        content:
          application/json:
            schema:
              type: array
              items:
                $ref: "#/components/schemas/Author"
    """
    async with request.app["session_factory"]() as session:
        result = await session.execute(select(Author).order_by(Author.id))
        authors = result.scalars().all()
        return web.json_response([to_json(AuthorRead.model_validate(author)) for author in authors])


async def get_author(request: web.Request, author_id: int) -> web.Response:
    """
    ---
    summary: Автор по id
    tags:
      - authors
    parameters:
      - name: author_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      "200":
        description: Найден
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Author"
      "404":
        description: Нет такого автора
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Error"
    """
    async with request.app["session_factory"]() as session:
        author = await session.get(Author, author_id)
        if author is None:
            return web.json_response(to_json(ErrorRead(error="Автор не найден")), status=404)
        return web.json_response(to_json(AuthorRead.model_validate(author)))


async def create_author(request: web.Request, body: dict) -> web.Response:
    """
    ---
    summary: Добавить автора
    tags:
      - authors
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - name
            properties:
              name:
                type: string
              bio:
                type: string
    responses:
      "201":
        description: Создан
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Author"
    """
    payload = parse_body(AuthorCreate, body)
    async with request.app["session_factory"]() as session:
        author = Author(name=payload.name, bio=payload.bio)
        session.add(author)
        await session.commit()
        await session.refresh(author)
        return web.json_response(to_json(AuthorRead.model_validate(author)), status=201)
```

---

## 4. `app/routes/books.py`

```python
from aiohttp import web
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Author, Book, Genre
from app.schemas import BookCreate, BookRead, ErrorRead, parse_body, to_json


async def list_books(request: web.Request) -> web.Response:
    """
    ---
    summary: Список книг
    tags:
      - books
    responses:
      "200":
        description: Все книги
        content:
          application/json:
            schema:
              type: array
              items:
                $ref: "#/components/schemas/Book"
    """
    async with request.app["session_factory"]() as session:
        result = await session.execute(
            select(Book)
            .options(selectinload(Book.author), selectinload(Book.genre))
            .order_by(Book.id)
        )
        books = result.scalars().all()
        return web.json_response([to_json(BookRead.from_book(book)) for book in books])


async def get_book(request: web.Request, book_id: int) -> web.Response:
    """
    ---
    summary: Книга по id
    tags:
      - books
    parameters:
      - name: book_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      "200":
        description: Найдена
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Book"
      "404":
        description: Нет такой книги
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Error"
    """
    async with request.app["session_factory"]() as session:
        result = await session.execute(
            select(Book)
            .options(selectinload(Book.author), selectinload(Book.genre))
            .where(Book.id == book_id)
        )
        book = result.scalar_one_or_none()
        if book is None:
            return web.json_response(to_json(ErrorRead(error="Книга не найдена")), status=404)
        return web.json_response(to_json(BookRead.from_book(book)))


async def create_book(request: web.Request, body: dict) -> web.Response:
    """
    ---
    summary: Добавить книгу
    tags:
      - books
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - title
              - author_id
              - genre_id
            properties:
              title:
                type: string
              year:
                type: integer
              author_id:
                type: integer
              genre_id:
                type: integer
    responses:
      "201":
        description: Создана
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Book"
      "404":
        description: Автор или жанр не найдены
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Error"
    """
    payload = parse_body(BookCreate, body)
    async with request.app["session_factory"]() as session:
        author = await session.get(Author, payload.author_id)
        genre = await session.get(Genre, payload.genre_id)
        if author is None:
            return web.json_response(to_json(ErrorRead(error="Автор не найден")), status=404)
        if genre is None:
            return web.json_response(to_json(ErrorRead(error="Жанр не найден")), status=404)

        book = Book(
            title=payload.title,
            year=payload.year,
            author_id=author.id,
            genre_id=genre.id,
        )
        session.add(book)
        await session.commit()

        result = await session.execute(
            select(Book)
            .options(selectinload(Book.author), selectinload(Book.genre))
            .where(Book.id == book.id)
        )
        created = result.scalar_one()
        return web.json_response(to_json(BookRead.from_book(created)), status=201)
```

Перед вставкой книги проверяем FK сами — иначе Postgres вернёт IntegrityError, а клиент увидит 500.

---

## 5. `app/routes/__init__.py`

```python
from aiohttp import web

from app.routes.authors import create_author, get_author, list_authors
from app.routes.books import create_book, get_book, list_books
from app.routes.genres import create_genre, get_genre, list_genres


async def health(request: web.Request) -> web.Response:
    """
    ---
    summary: Проверка, что сервер жив
    tags:
      - health
    responses:
      "200":
        description: ok
        content:
          application/json:
            schema:
              type: object
              properties:
                status:
                  type: string
    """
    return web.json_response({"status": "ok"})


def routes() -> list[web.RouteDef]:
    return [
        web.get("/health", health),
        web.get("/genres", list_genres),
        web.get("/genres/{genre_id}", get_genre),
        web.post("/genres", create_genre),
        web.get("/authors", list_authors),
        web.get("/authors/{author_id}", get_author),
        web.post("/authors", create_author),
        web.get("/books", list_books),
        web.get("/books/{book_id}", get_book),
        web.post("/books", create_book),
    ]
```

Перенесите `health` сюда из `app/main.py` — один список роутов.

---

## 6. Обновить `app/main.py`

Нужен `app/openapi_components.yaml` (схемы для `$ref`). Создайте файл — содержимое полное на шаге 8, а сейчас минимальное:

```yaml
components:
  schemas:
    Genre:
      type: object
      properties:
        id: {type: integer}
        name: {type: string}
    Author:
      type: object
      properties:
        id: {type: integer}
        name: {type: string}
        bio: {type: string, nullable: true}
    Book:
      type: object
      properties:
        id: {type: integer}
        title: {type: string}
        year: {type: integer, nullable: true}
        author_id: {type: integer}
        genre_id: {type: integer}
        author: {type: string, nullable: true}
        genre: {type: string, nullable: true}
    Error:
      type: object
      properties:
        error: {type: string}
```

`app/main.py`:

```python
from aiohttp import web
from aiohttp_swagger3 import SwaggerDocs, SwaggerInfo

from app.config import settings
from app.db import make_engine, make_session_factory
from app.routes import routes


async def on_startup(app: web.Application) -> None:
    engine = make_engine()
    app["engine"] = engine
    app["session_factory"] = make_session_factory(engine)


async def on_cleanup(app: web.Application) -> None:
    await app["engine"].dispose()


def create_app() -> web.Application:
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    swagger = SwaggerDocs(
        app,
        validate=True,
        info=SwaggerInfo(
            title="Mini Library API",
            version="1.0.0",
            description="Учебное API библиотеки на aiohttp.",
        ),
        components="app/openapi_components.yaml",
    )
    swagger.add_routes(routes())
    return app


def main() -> None:
    web.run_app(create_app(), host=settings.app_host, port=settings.app_port)


if __name__ == "__main__":
    main()
```

`app.router.add_get("/health", ...)` удалите — иначе дубль и swagger не увидит handler.

---

## ✅ Проверка

```bash
source .venv/bin/activate
python -m app.main
```

Другой терминал:

```bash
curl -s http://127.0.0.1:8080/health
curl -s -X POST http://127.0.0.1:8080/genres \
  -H 'Content-Type: application/json' \
  -d '{"name":"фантастика"}'
curl -s -X POST http://127.0.0.1:8080/authors \
  -H 'Content-Type: application/json' \
  -d '{"name":"Аркадий Стругацкий","bio":"фантаст"}'
curl -s -X POST http://127.0.0.1:8080/books \
  -H 'Content-Type: application/json' \
  -d '{"title":"Пикник на обочине","year":1972,"author_id":1,"genre_id":1}'
curl -s http://127.0.0.1:8080/books
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/books/999
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8080/genres \
  -H 'Content-Type: application/json' \
  -d '{"name":""}'
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | POST жанр / автор / книга | `201` и JSON с `id` |
| ☐ | GET `/books` | книга с полями `author` и `genre` (имена, не только id) |
| ☐ | GET `/books/999` | `404` и `{"error": "..."}` |
| ☐ | POST `/genres` с `{"name":""}` | `422` от Pydantic, не 500 |
| ☐ | POST книги с `author_id: 999` | `404`, не 500 |

**Все пункты отмечены?** → [step-08-swagger.md](step-08-swagger.md)
