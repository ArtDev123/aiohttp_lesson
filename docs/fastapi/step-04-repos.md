# Шаг 4 — Слой репозиториев

**Предыдущий:** [step-03-routes.md](step-03-routes.md) · **Следующий:** [step-05-base.md](step-05-base.md)

## Задача

Вынести SQL из роутов в репозитории. Роут остаётся тонким: принял DTO → позвал репозиторий → вернул DTO / кинул `NotFoundError`. Сессию роут больше не видит — её получает репозиторий через тот же `Depends`.

Поведение API не меняется (GET / POST / PATCH те же). Не вводите сервисный слой и не делайте общий базовый класс — это шаг 5. Здесь три похожих репозитория, чтобы было видно дублирование.

---

## Теория: зачем ещё один слой

На шаге 3 хендлер делает всё сразу:

```text
HTTP  +  валидация  +  select/commit  +  404  +  JSON
```

Это нормально, пока запросов мало. Как только появится второй способ прочитать книги (скрипт, админка, тест), SQL начнут копировать.

**Репозиторий** — объект, который умеет доставать и сохранять одну сущность. Он знает SQLAlchemy. Он не знает FastAPI, статус-коды и Pydantic-схемы ответа.

```text
роут (HTTP, DTO, 404)
        ↓
репозиторий (get_all, get, add, update)
        ↓
AsyncSession
        ↓
PostgreSQL
```

| Остаётся в роуте | Уходит в репозиторий |
|------------------|----------------------|
| `payload: BookCreate` / `BookUpdate` | `select(Book)`, `selectinload` |
| `raise NotFoundError` | `session.get`, `commit`, `refresh` |
| `BookRead.from_book(...)` | сборка ORM-объекта `Book(...)` |
| проверка FK автора/жанра | `setattr` полей при PATCH |

Список в репозитории называется **`get_all`**, не `list`: `list` слишком легко спутать со встроенным типом, а `get_all` рядом с `get` читается как пара «одна строка / все строки».

Роут решает, что «нет строки» — это 404. Репозиторий возвращает `None`. Так слой БД не зависит от HTTP.

---

## Теория: вложенный `Depends` и кэш на запрос

Репозиторию нужна сессия. Сессию уже умеет давать `get_session`. Зависимости **можно вкладывать**:

```python
def get_book_repository(session: SessionDep) -> BookRepository:
    return BookRepository(session)


BookRepoDep = Annotated[BookRepository, Depends(get_book_repository)]
```

```text
create_book(books, authors, genres)
        │
        ├─ get_book_repository  ─┐
        ├─ get_author_repository ┼─ все трое просят SessionDep
        └─ get_genre_repository  ┘
                    │
                    ▼
            get_session  →  одна AsyncSession
```

Важно: FastAPI **кэширует** результат зависимости внутри одного запроса. Три репозитория получат **один и тот же** объект сессии, не три соединения. Commit в `BookRepository.add` виден тем же запросом, потому что это та же транзакция.

Без кэша `Depends(get_session)` на каждый репозиторий открыл бы свою сессию — и проверка «автор есть» жила бы в другом соединении, чем `INSERT`. Поэтому не пишите «обходной» `get_session` без `Depends`: только через граф зависимостей FastAPI.

В тестах потом подмените `get_book_repository` (или `get_session`) через `app.dependency_overrides` — роуты трогать не придётся. Сейчас тесты писать не обязательно, но ради этого DI и затевался.

---

## Теория: где `commit`

Учебный вариант: **commit внутри репозитория** (`add` / `update` сами сохраняют). Проще читать.

В большом приложении часто делают Unit of Work: репозитории только `add`/`flush`, а `commit` — один раз в конце запроса (в `get_session` после `yield`, если не было исключения). Тогда «создать книгу и ещё что-то» — одна транзакция.

Для этого урока оставьте commit в `add` и `update`. Если позже понадобится несколько записей атомарно — вынесете commit из репозитория, не наоборот.

---

## 1. `app/repositories/genres.py`

```python
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Genre


class GenreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> Sequence[Genre]:
        result = await self._session.execute(select(Genre).order_by(Genre.id))
        return result.scalars().all()

    async def get(self, genre_id: int) -> Genre | None:
        return await self._session.get(Genre, genre_id)

    async def add(self, **fields: Any) -> Genre:
        genre = Genre(**fields)
        self._session.add(genre)
        await self._session.commit()
        await self._session.refresh(genre)
        return genre

    async def update(self, genre_id: int, **fields: Any) -> Genre | None:
        genre = await self.get(genre_id)
        if genre is None:
            return None
        for key, value in fields.items():
            setattr(genre, key, value)
        await self._session.commit()
        await self._session.refresh(genre)
        return genre
```

Репозиторий принимает `**fields`, не `GenreCreate`: схема API — деталь HTTP-слоя. Роут сделает `repo.add(**payload.model_dump())` и `repo.update(id, **payload.model_dump(exclude_unset=True))`.

---

## 2. `app/repositories/authors.py`

```python
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Author


class AuthorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> Sequence[Author]:
        result = await self._session.execute(select(Author).order_by(Author.id))
        return result.scalars().all()

    async def get(self, author_id: int) -> Author | None:
        return await self._session.get(Author, author_id)

    async def add(self, **fields: Any) -> Author:
        author = Author(**fields)
        self._session.add(author)
        await self._session.commit()
        await self._session.refresh(author)
        return author

    async def update(self, author_id: int, **fields: Any) -> Author | None:
        author = await self.get(author_id)
        if author is None:
            return None
        for key, value in fields.items():
            setattr(author, key, value)
        await self._session.commit()
        await self._session.refresh(author)
        return author
```

---

## 3. `app/repositories/books.py`

```python
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Book


class BookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _with_relations(self):
        return select(Book).options(
            selectinload(Book.author),
            selectinload(Book.genre),
        )

    async def get_all(self) -> Sequence[Book]:
        result = await self._session.execute(self._with_relations().order_by(Book.id))
        return result.scalars().all()

    async def get(self, book_id: int) -> Book | None:
        result = await self._session.execute(
            self._with_relations().where(Book.id == book_id)
        )
        return result.scalar_one_or_none()

    async def add(self, **fields: Any) -> Book:
        book = Book(**fields)
        self._session.add(book)
        await self._session.commit()
        created = await self.get(book.id)
        assert created is not None
        return created

    async def update(self, book_id: int, **fields: Any) -> Book | None:
        book = await self.get(book_id)
        if book is None:
            return None
        for key, value in fields.items():
            setattr(book, key, value)
        await self._session.commit()
        return await self.get(book.id)
```

`selectinload` живёт здесь, не в роуте: «книга всегда с автором и жанром» — правило доступа к данным. После `add`/`update` снова зовём `get`, чтобы в JSON попали актуальные имена, а не старый объект из identity map.

Проверку «автор/жанр существуют» **не** прячьте внутрь `add`/`update`. Пусть роут спросит `AuthorRepository.get` и `GenreRepository.get` и сам решит, какой 404 отдать. Иначе репозиторий книг начнёт знать про тексты ошибок HTTP.

---

## 4. `app/repositories/__init__.py`

```python
from app.repositories.authors import AuthorRepository
from app.repositories.books import BookRepository
from app.repositories.genres import GenreRepository

__all__ = ["AuthorRepository", "BookRepository", "GenreRepository"]
```

---

## 5. `app/deps.py`

Связка FastAPI ↔ репозитории. Роуты импортируют отсюда `*RepoDep`, а не конструируют классы руками.

```python
from typing import Annotated

from fastapi import Depends

from app.db import SessionDep
from app.repositories import AuthorRepository, BookRepository, GenreRepository


def get_genre_repository(session: SessionDep) -> GenreRepository:
    return GenreRepository(session)


def get_author_repository(session: SessionDep) -> AuthorRepository:
    return AuthorRepository(session)


def get_book_repository(session: SessionDep) -> BookRepository:
    return BookRepository(session)


GenreRepoDep = Annotated[GenreRepository, Depends(get_genre_repository)]
AuthorRepoDep = Annotated[AuthorRepository, Depends(get_author_repository)]
BookRepoDep = Annotated[BookRepository, Depends(get_book_repository)]
```

`SessionDep` уже содержит `Depends(get_session)` — FastAPI развернёт цепочку сам.

Короткий вариант без фабрик: `def __init__(self, session: SessionDep)` у класса и `Depends()` без аргумента. Явные `get_*_repository` проще отлаживать и проще подменять в `dependency_overrides`. Оставьте фабрики.

---

## 6. Роуты после выноса SQL

В каждом файле роутов не должно остаться `select`, `selectinload`, `session.add`.

### `app/routes/genres.py`

```python
from fastapi import APIRouter, status

from app.deps import GenreRepoDep
from app.errors import NotFoundError
from app.schemas import ErrorRead, GenreCreate, GenreRead, GenreUpdate

router = APIRouter(prefix="/genres", tags=["genres"])


@router.get("", response_model=list[GenreRead])
async def list_genres(repo: GenreRepoDep) -> list[GenreRead]:
    genres = await repo.get_all()
    return [GenreRead.model_validate(genre) for genre in genres]


@router.get(
    "/{genre_id}",
    response_model=GenreRead,
    responses={404: {"model": ErrorRead}},
)
async def get_genre(genre_id: int, repo: GenreRepoDep) -> GenreRead:
    genre = await repo.get(genre_id)
    if genre is None:
        raise NotFoundError("Жанр не найден")
    return GenreRead.model_validate(genre)


@router.post(
    "",
    response_model=GenreRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_genre(payload: GenreCreate, repo: GenreRepoDep) -> GenreRead:
    genre = await repo.add(**payload.model_dump())
    return GenreRead.model_validate(genre)


@router.patch(
    "/{genre_id}",
    response_model=GenreRead,
    responses={404: {"model": ErrorRead}},
)
async def patch_genre(
    genre_id: int, payload: GenreUpdate, repo: GenreRepoDep
) -> GenreRead:
    genre = await repo.update(genre_id, **payload.model_dump(exclude_unset=True))
    if genre is None:
        raise NotFoundError("Жанр не найден")
    return GenreRead.model_validate(genre)
```

### `app/routes/authors.py`

```python
from fastapi import APIRouter, status

from app.deps import AuthorRepoDep
from app.errors import NotFoundError
from app.schemas import AuthorCreate, AuthorRead, AuthorUpdate, ErrorRead

router = APIRouter(prefix="/authors", tags=["authors"])


@router.get("", response_model=list[AuthorRead])
async def list_authors(repo: AuthorRepoDep) -> list[AuthorRead]:
    authors = await repo.get_all()
    return [AuthorRead.model_validate(author) for author in authors]


@router.get(
    "/{author_id}",
    response_model=AuthorRead,
    responses={404: {"model": ErrorRead}},
)
async def get_author(author_id: int, repo: AuthorRepoDep) -> AuthorRead:
    author = await repo.get(author_id)
    if author is None:
        raise NotFoundError("Автор не найден")
    return AuthorRead.model_validate(author)


@router.post(
    "",
    response_model=AuthorRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_author(payload: AuthorCreate, repo: AuthorRepoDep) -> AuthorRead:
    author = await repo.add(**payload.model_dump())
    return AuthorRead.model_validate(author)


@router.patch(
    "/{author_id}",
    response_model=AuthorRead,
    responses={404: {"model": ErrorRead}},
)
async def patch_author(
    author_id: int, payload: AuthorUpdate, repo: AuthorRepoDep
) -> AuthorRead:
    author = await repo.update(author_id, **payload.model_dump(exclude_unset=True))
    if author is None:
        raise NotFoundError("Автор не найден")
    return AuthorRead.model_validate(author)
```

### `app/routes/books.py`

```python
from fastapi import APIRouter, status

from app.deps import AuthorRepoDep, BookRepoDep, GenreRepoDep
from app.errors import NotFoundError
from app.schemas import BookCreate, BookRead, BookUpdate, ErrorRead

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=list[BookRead])
async def list_books(repo: BookRepoDep) -> list[BookRead]:
    books = await repo.get_all()
    return [BookRead.from_book(book) for book in books]


@router.get(
    "/{book_id}",
    response_model=BookRead,
    responses={404: {"model": ErrorRead}},
)
async def get_book(book_id: int, repo: BookRepoDep) -> BookRead:
    book = await repo.get(book_id)
    if book is None:
        raise NotFoundError("Книга не найдена")
    return BookRead.from_book(book)


@router.post(
    "",
    response_model=BookRead,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorRead}},
)
async def create_book(
    payload: BookCreate,
    books: BookRepoDep,
    authors: AuthorRepoDep,
    genres: GenreRepoDep,
) -> BookRead:
    author = await authors.get(payload.author_id)
    genre = await genres.get(payload.genre_id)
    if author is None:
        raise NotFoundError("Автор не найден")
    if genre is None:
        raise NotFoundError("Жанр не найден")

    book = await books.add(**payload.model_dump())
    return BookRead.from_book(book)


@router.patch(
    "/{book_id}",
    response_model=BookRead,
    responses={404: {"model": ErrorRead}},
)
async def patch_book(
    book_id: int,
    payload: BookUpdate,
    books: BookRepoDep,
    authors: AuthorRepoDep,
    genres: GenreRepoDep,
) -> BookRead:
    data = payload.model_dump(exclude_unset=True)
    if "author_id" in data:
        author = await authors.get(data["author_id"])
        if author is None:
            raise NotFoundError("Автор не найден")
    if "genre_id" in data:
        genre = await genres.get(data["genre_id"])
        if genre is None:
            raise NotFoundError("Жанр не найден")

    book = await books.update(book_id, **data)
    if book is None:
        raise NotFoundError("Книга не найдена")
    return BookRead.from_book(book)
```

Три репозитория в `create_book` — не «слишком много DI», а явный список коллабораторов. Все трое делят одну сессию.

`app/routes/__init__.py` и `app/main.py` не меняются: роутеры те же, меняется только начинка файлов.

`health` по-прежнему принимает `SessionDep`. Это нормально: проверка живости БД может смотреть в сессию, а не в репозиторий жанров. Если хотите симметрии — оставьте как есть.

---

## Разбор: что должно пропасть из `app/routes/`

```bash
grep -n "select\|session\.add\|SessionDep" app/routes/*.py
```

Ожидание:

- `select` / `selectinload` / `session.add` — **нет**
- `SessionDep` — только в `health` (`routes/__init__.py`)
- в CRUD-файлах — `GenreRepoDep` / `AuthorRepoDep` / `BookRepoDep`

`app/seed.py` репозитории не использует: это одноразовый скрипт, не HTTP. Не тащите туда FastAPI-зависимости.

---

## ✅ Проверка

Перезапустите сервер (если без `--reload`).

```bash
curl -s http://127.0.0.1:8080/books | python -m json.tool
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/authors/999
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8080/books \
  -H 'Content-Type: application/json' \
  -d '{"title":"Нет такого автора","year":2000,"author_id":999,"genre_id":1}'
curl -s -X PATCH http://127.0.0.1:8080/books/1 \
  -H 'Content-Type: application/json' \
  -d '{"year":1973}'
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | GET `/books` | как на шаге 3, имена автора/жанра на месте |
| ☐ | GET несуществующего автора | `404` `{"error":"..."}` |
| ☐ | POST книги с `author_id: 999` | `404` «Автор не найден», не 500 |
| ☐ | PATCH книги с новым `year` | `200`, год изменился, `author`/`genre` на месте |
| ☐ | `/docs` | те же пути плюс PATCH |
| ☐ | `grep select app/routes` | пусто (кроме, возможно, ничего) |
| ☐ | Три файла в `app/repositories/` | `get_all` / `get` / `add` / `update`, без импорта FastAPI |

Если POST книги падает с ошибкой сессии / «already closed» — `get_session` вызывается больше одного раза без кэша, или репозиторий создаёте вручную `GenreRepository(await get_session(...))`. Только `Depends`.

**Все пункты отмечены?** → [step-05-base.md](step-05-base.md)
