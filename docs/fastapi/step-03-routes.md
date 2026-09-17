# Шаг 3 — CRUD «как есть»: схемы и роуты

**Предыдущий:** [step-02-app.md](step-02-app.md) · **Следующий:** [step-04-repos.md](step-04-repos.md)

## Задача

Перенести те же три ресурса (жанры, авторы, книги) на FastAPI и добавить **PATCH** (частичное обновление). SQL **пока остаётся в роутах** — как в aiohttp-хендлерах. Меняется способ получить сессию, body и ответ.

Слой репозиториев — следующий шаг. Не выносите `select` заранее.

---

## Теория: body — это тип в сигнатуре

В aiohttp swagger3 инжектил `body: dict`, вы сами звали `parse_body(GenreCreate, body)`.

В FastAPI аргумент с типом Pydantic-модели **и есть** JSON-тело:

```python
async def create_genre(payload: GenreCreate, session: SessionDep) -> GenreRead:
    ...
```

| Откуда значение | Как FastAPI понимает |
|-----------------|----------------------|
| `{genre_id}` в пути | аргумент `genre_id: int` |
| JSON POST | аргумент с типом `BaseModel` |
| сессия | `SessionDep` = `Depends(get_session)` |

`parse_body` удаляем: невалидный JSON (пустой `name`) FastAPI сам превратит в **422**. Формат ответа другой:

```json
{"detail":[{"type":"string_too_short","loc":["body","name"],"msg":"...","input":""}]}
```

В aiohttp это был JSON из `ValidationError.json()`. Контракт 404 (`{"error":"..."}`) сохраняем через `NotFoundError` с шага 2. Контракт 422 сознательно отдаём «по-fastapi» — так устроен фреймворк, отдельный exception handler ради байт-в-байт совместимости здесь не нужен.

---

## Теория: `APIRouter` и `response_model`

Не вешайте все URL на объект `app` в `main.py`. Как папка `app/routes/` раньше собирала `web.RouteDef`, так теперь каждый файл даёт `APIRouter`.

```python
router = APIRouter(prefix="/genres", tags=["genres"])

@router.get("", response_model=list[GenreRead])
async def list_genres(...): ...
```

`prefix="/genres"` + `""` → `GET /genres`. `tags` попадают в Swagger как группы.

Возврат `GenreRead` (или `list[GenreRead]`) — и сериализация, и схема в OpenAPI. Для 404 добавим `responses={404: {"model": ErrorRead}}`, чтобы в UI осталась схема `Error`.

`status_code=201` на POST — иначе FastAPI по умолчанию поставит 200.

Path-параметр `{genre_id}` FastAPI сам достанет из URL и приведёт к `int`. В aiohttp без swagger3 этого не было.

---

## Теория: PATCH и `exclude_unset`

В aiohttp-уроке обновления не было. Здесь добавляем частичный апдейт — это хорошо ложится на Pydantic.

| Метод | Смысл | Тело |
|-------|--------|------|
| POST | создать | все обязательные поля (`GenreCreate`) |
| PUT | заменить целиком | тоже все поля (мы PUT не делаем) |
| **PATCH** | поменять только присланное | каждое поле необязательно (`GenreUpdate`) |

```python
class GenreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
```

Клиент шлёт `{"name": "лирика"}` — меняем имя. Шлёт `{}` — ничего не трогаем, отвечаем 200 с текущим объектом.

Ключ — `model_dump(exclude_unset=True)`:

- поля, которых **не было в JSON**, в dict не попадут;
- `{"bio": null}` у автора **попадёт** (`bio: None`) — так можно очистить биографию;
- без `exclude_unset` дефолтный `None` затёр бы имя, которое клиент не присылал.

Пустой `name: ""` по-прежнему 422: `Field(min_length=1)` работает и в Update.

---

## 1. `app/schemas.py`

Уберите импорт aiohttp и `parse_body`. Модели Create/Read те же, плюс **Update** для PATCH.

```python
from pydantic import BaseModel, ConfigDict, Field

from app.models import Book


class ErrorRead(BaseModel):
    error: str


class GenreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class GenreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class GenreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)


class AuthorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    bio: str | None = None


class AuthorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    bio: str | None


class AuthorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    bio: str | None = None


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    year: int | None = Field(default=None, ge=1, le=2100)
    author_id: int = Field(ge=1)
    genre_id: int = Field(ge=1)


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    year: int | None = Field(default=None, ge=1, le=2100)
    author_id: int | None = Field(default=None, ge=1)
    genre_id: int | None = Field(default=None, ge=1)


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
```

`from_book` никуда не делся: у ORM `book.author` — объект, а в JSON нужна строка-имя.

---

## 2. `app/routes/genres.py`

```python
from fastapi import APIRouter, status
from sqlalchemy import select

from app.db import SessionDep
from app.errors import NotFoundError
from app.models import Genre
from app.schemas import ErrorRead, GenreCreate, GenreRead, GenreUpdate

router = APIRouter(prefix="/genres", tags=["genres"])


@router.get("", response_model=list[GenreRead])
async def list_genres(session: SessionDep) -> list[GenreRead]:
    result = await session.execute(select(Genre).order_by(Genre.id))
    genres = result.scalars().all()
    return [GenreRead.model_validate(genre) for genre in genres]


@router.get(
    "/{genre_id}",
    response_model=GenreRead,
    responses={404: {"model": ErrorRead}},
)
async def get_genre(genre_id: int, session: SessionDep) -> GenreRead:
    genre = await session.get(Genre, genre_id)
    if genre is None:
        raise NotFoundError("Жанр не найден")
    return GenreRead.model_validate(genre)


@router.post(
    "",
    response_model=GenreRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_genre(payload: GenreCreate, session: SessionDep) -> GenreRead:
    genre = Genre(name=payload.name)
    session.add(genre)
    await session.commit()
    await session.refresh(genre)
    return GenreRead.model_validate(genre)


@router.patch(
    "/{genre_id}",
    response_model=GenreRead,
    responses={404: {"model": ErrorRead}},
)
async def patch_genre(
    genre_id: int, payload: GenreUpdate, session: SessionDep
) -> GenreRead:
    genre = await session.get(Genre, genre_id)
    if genre is None:
        raise NotFoundError("Жанр не найден")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(genre, field, value)
    await session.commit()
    await session.refresh(genre)
    return GenreRead.model_validate(genre)
```

Сравните с aiohttp: тот же `select` / `session.get` / `commit`, но без `async with session_factory()` — сессию закрывает `get_session` после ответа.

---

## 3. `app/routes/authors.py`

```python
from fastapi import APIRouter, status
from sqlalchemy import select

from app.db import SessionDep
from app.errors import NotFoundError
from app.models import Author
from app.schemas import AuthorCreate, AuthorRead, AuthorUpdate, ErrorRead

router = APIRouter(prefix="/authors", tags=["authors"])


@router.get("", response_model=list[AuthorRead])
async def list_authors(session: SessionDep) -> list[AuthorRead]:
    result = await session.execute(select(Author).order_by(Author.id))
    authors = result.scalars().all()
    return [AuthorRead.model_validate(author) for author in authors]


@router.get(
    "/{author_id}",
    response_model=AuthorRead,
    responses={404: {"model": ErrorRead}},
)
async def get_author(author_id: int, session: SessionDep) -> AuthorRead:
    author = await session.get(Author, author_id)
    if author is None:
        raise NotFoundError("Автор не найден")
    return AuthorRead.model_validate(author)


@router.post(
    "",
    response_model=AuthorRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_author(payload: AuthorCreate, session: SessionDep) -> AuthorRead:
    author = Author(name=payload.name, bio=payload.bio)
    session.add(author)
    await session.commit()
    await session.refresh(author)
    return AuthorRead.model_validate(author)


@router.patch(
    "/{author_id}",
    response_model=AuthorRead,
    responses={404: {"model": ErrorRead}},
)
async def patch_author(
    author_id: int, payload: AuthorUpdate, session: SessionDep
) -> AuthorRead:
    author = await session.get(Author, author_id)
    if author is None:
        raise NotFoundError("Автор не найден")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(author, field, value)
    await session.commit()
    await session.refresh(author)
    return AuthorRead.model_validate(author)
```

---

## 4. `app/routes/books.py`

```python
from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import SessionDep
from app.errors import NotFoundError
from app.models import Author, Book, Genre
from app.schemas import BookCreate, BookRead, BookUpdate, ErrorRead

router = APIRouter(prefix="/books", tags=["books"])


def _book_query():
    return select(Book).options(selectinload(Book.author), selectinload(Book.genre))


@router.get("", response_model=list[BookRead])
async def list_books(session: SessionDep) -> list[BookRead]:
    result = await session.execute(_book_query().order_by(Book.id))
    books = result.scalars().all()
    return [BookRead.from_book(book) for book in books]


@router.get(
    "/{book_id}",
    response_model=BookRead,
    responses={404: {"model": ErrorRead}},
)
async def get_book(book_id: int, session: SessionDep) -> BookRead:
    result = await session.execute(_book_query().where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if book is None:
        raise NotFoundError("Книга не найдена")
    return BookRead.from_book(book)


@router.post(
    "",
    response_model=BookRead,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorRead}},
)
async def create_book(payload: BookCreate, session: SessionDep) -> BookRead:
    author = await session.get(Author, payload.author_id)
    genre = await session.get(Genre, payload.genre_id)
    if author is None:
        raise NotFoundError("Автор не найден")
    if genre is None:
        raise NotFoundError("Жанр не найден")

    book = Book(
        title=payload.title,
        year=payload.year,
        author_id=author.id,
        genre_id=genre.id,
    )
    session.add(book)
    await session.commit()

    result = await session.execute(_book_query().where(Book.id == book.id))
    created = result.scalar_one()
    return BookRead.from_book(created)


@router.patch(
    "/{book_id}",
    response_model=BookRead,
    responses={404: {"model": ErrorRead}},
)
async def patch_book(
    book_id: int, payload: BookUpdate, session: SessionDep
) -> BookRead:
    result = await session.execute(_book_query().where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if book is None:
        raise NotFoundError("Книга не найдена")

    data = payload.model_dump(exclude_unset=True)
    if "author_id" in data:
        author = await session.get(Author, data["author_id"])
        if author is None:
            raise NotFoundError("Автор не найден")
    if "genre_id" in data:
        genre = await session.get(Genre, data["genre_id"])
        if genre is None:
            raise NotFoundError("Жанр не найден")

    for field, value in data.items():
        setattr(book, field, value)
    await session.commit()

    result = await session.execute(_book_query().where(Book.id == book.id))
    updated = result.scalar_one()
    return BookRead.from_book(updated)
```

Перед вставкой книги проверяем FK сами — иначе Postgres вернёт IntegrityError, а клиент увидит 500. Это то же правило, что в aiohttp-гайде.

`selectinload` нужен, чтобы `BookRead.from_book` мог прочитать `book.author.name` без ленивой загрузки (в async-сессии lazy load запрещён).

---

## 5. `app/routes/__init__.py`

```python
from fastapi import APIRouter, FastAPI

from app.db import SessionDep
from app.routes import authors, books, genres


def health_router() -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    async def health(session: SessionDep) -> dict[str, str]:
        return {"status": "ok"}

    return router


def register_routes(app: FastAPI) -> None:
    app.include_router(health_router())
    app.include_router(genres.router)
    app.include_router(authors.router)
    app.include_router(books.router)
```

`/health` переезжает сюда из `main.py`, чтобы все URL собирались в одном месте — как список `routes()` в aiohttp.

---

## 6. Обновить `app/main.py`

Уберите локальный `/health`. Подключите роуты.

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import make_engine, make_session_factory
from app.errors import NotFoundError
from app.routes import register_routes


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = make_engine()
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Mini Library API",
        version="1.0.0",
        description="Учебное API библиотеки на FastAPI.",
        lifespan=lifespan,
    )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(
        request: Request, exc: NotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": exc.message})

    register_routes(app)
    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
```

Файл `app/openapi_components.yaml` больше не читается — удалите его. Docstring с `---` в роутах тоже не нужен: схема берётся из типов.

Пакет `aiohttp-swagger3` из `requirements.txt` можно убрать (aiohttp оставьте для клиента).

---

## Разбор цепочки `POST /books`

1. FastAPI парсит JSON в `BookCreate` (`Field`, типы). Пустой `title` → 422, хендлер не вызывается.
2. `Depends(get_session)` открывает `AsyncSession` из `app.state.session_factory`.
3. Хендлер проверяет, что автор и жанр существуют.
4. `session.add(Book(...))` → `commit`.
5. Повторный SELECT с `selectinload` → `BookRead.from_book` → JSON `201`.
6. Генератор `get_session` закрывает сессию.

На фазе 2 пункты 3–5 уедут в репозитории. Пока оставьте SQL здесь — так проще увидеть, что поменялся только «каркас», не доменная логика.

---

## ✅ Проверка

```bash
source .venv/bin/activate
python -m app.main
```

Другой терминал (если в БД уже есть строки с шага 9 aiohttp — POST с тем же именем жанра может упереться в unique; это ок, главное что GET живой):

```bash
curl -s http://127.0.0.1:8080/health
curl -s -X POST http://127.0.0.1:8080/genres \
  -H 'Content-Type: application/json' \
  -d '{"name":"учебный-жанр"}'
curl -s -X POST http://127.0.0.1:8080/authors \
  -H 'Content-Type: application/json' \
  -d '{"name":"Тестовый Автор","bio":"fastapi"}'
curl -s http://127.0.0.1:8080/books
curl -s -X PATCH http://127.0.0.1:8080/genres/1 \
  -H 'Content-Type: application/json' \
  -d '{"name":"фантастика (правка)"}'
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/books/999
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8080/genres \
  -H 'Content-Type: application/json' \
  -d '{"name":""}'
```

В браузере: [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs) — Try it out на `GET /books`.

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | POST жанр / автор | `201` и JSON с `id` |
| ☐ | PATCH `/genres/{id}` с `{"name":"..."}` | `200`, имя изменилось |
| ☐ | PATCH несуществующего id | `404` и `{"error":"..."}` |
| ☐ | GET `/books` | книги с полями `author` и `genre` (имена) |
| ☐ | GET `/books/999` | `404` и `{"error":"..."}` — не `{"detail":...}` |
| ☐ | POST `/genres` с `{"name":""}` | `422`, ключ `detail`, не 500 |
| ☐ | POST книги с `author_id: 999` | `404`, не 500 |
| ☐ | `/docs` | три группы тегов: health, genres, authors, books |
| ☐ | В роутах нет `web.Request` / `parse_body` | — |

**Все пункты отмечены?** → [step-04-repos.md](step-04-repos.md)
