# Шаг 6 — Query-фильтры на `GET /books`

**Предыдущий:** [step-05-base.md](step-05-base.md) · **Следующий:** [step-07-final.md](step-07-final.md)

## Задача

Научиться читать **query-параметры** так же декларативно, как body и path: `GET /books?year=1972&title=пикник`. SQL фильтрации — в `BookRepository`, не в `BaseRepository` и не в роуте.

Поведение без `?` остаётся прежним: все книги. Пустой результат — `200` и `[]`, не 404.

---

## Теория: path, query, body

В URL три разных места для данных:

```text
GET /books/1?year=1972
        │         └── query  (после ?)
        └── path   (кусок маршрута)

POST /books
        └── body   (JSON)
```

| Откуда | Пример | Как FastAPI узнаёт |
|--------|--------|---------------------|
| path | `/books/{book_id}` | имя аргумента совпало с `{book_id}` |
| query | `?year=1972` | простой тип (`int`, `str`), которого **нет** в пути |
| body | `{"title":"..."}` | тип — Pydantic `BaseModel` |
| зависимость | сессия, репозиторий | `Depends(...)` / `*Dep` |

```python
async def get_book(book_id: int, repo: BookRepoDep) -> BookRead:
    #          └── path              └── Depends

async def list_books(year: int | None = None, repo: BookRepoDep) -> list[BookRead]:
    #                └── query: /books?year=1972
```

Фильтр **не** кладут в путь (`/books/year/1972`): год необязательный, таких измерений несколько, комбинации взорвут маршруты. Query как раз для «может быть, а может не быть».

В aiohttp query доставали руками: `request.query.get("year")` → строка → сами `int()`. FastAPI приводит тип и, если не вышло, отвечает **422**, хендлер не вызывается.

---

## Теория: `None` = параметра не было

```python
year: int | None = None
```

| Запрос | Что придёт в аргумент |
|--------|------------------------|
| `GET /books` | `year is None` |
| `GET /books?year=1972` | `year == 1972` |
| `GET /books?year=abc` | 422, хендлер не вызван |
| `GET /books?year=` | 422 (`int` из пустой строки не собрать) |

Дефолт `None` значит «фильтр выключен», не «ищи книги без года». В SQL условие добавляют **только если значение не `None`**.

Несколько query складываются через **AND**: `?author_id=2&year=1934` — книги этого автора **и** этого года.

Пустой список — нормальный ответ. 404 оставляем для «конкретный id не найден» (`GET /books/999`). Иначе клиент не отличит «нет таких книг» от «нет такого URL».

---

## Теория: `Query()` — валидация и описание

Голого `year: int | None = None` достаточно, чтобы параметр появился в `/docs`. `Query` нужен, когда есть ограничения или текст для Swagger — тот же приём, что `Field` у body.

```python
from typing import Annotated

from fastapi import Query

year: Annotated[int | None, Query(ge=1, le=2100, description="Год издания")] = None
```

Это тот же `Annotated`, что у `SessionDep`: тип отдельно, «откуда взять и как проверить» отдельно.

| Что написали | Эффект |
|--------------|--------|
| `ge=1, le=2100` | `?year=0` → 422 |
| `min_length=1` на `title` | `?title=` → 422 |
| `description=...` | подпись в Swagger |
| без `Query` | всё равно query, но без этих проверок |

`Query(...)` без `default` сделает параметр **обязательным** — для фильтра это почти всегда ошибка. Пишите `= None`.

---

## Теория: модель фильтров через `Depends`

Четыре аргумента засоряют сигнатуру. Сворачиваем в Pydantic-модель и объявляем её зависимостью:

```python
class BookFilters(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    year: int | None = Field(default=None, ge=1, le=2100)
    author_id: int | None = Field(default=None, ge=1)
    genre_id: int | None = Field(default=None, ge=1)


async def list_books(
    repo: BookRepoDep,
    filters: Annotated[BookFilters, Depends()],
) -> list[BookRead]:
    ...
```

Обычный `payload: BookCreate` FastAPI считает **body**. Та же модель с `Depends()` — набор **query**. Поля попадают в OpenAPI как отдельные параметры `GET /books`.

`Depends()` без аргумента: «собери этот класс из query сам». Не пишите `Depends(BookFilters)` как фабрику с логикой — конструктор модели и есть сборка.

Эту же модель **прокидываем в репозиторий**. Разворачивать в `title=`, `year=` незачем: поля одни и те же, дублировать сигнатуру — лишние четыре места, которые разъедутся.

Pydantic ≠ FastAPI. В репозиторий не тащим `Request`, `Query()`, статус-коды. `BookFilters` — обычный объект с полями, как словарь, только с именами. `GenreCreate` в `add` по-прежнему не пихаем: create/update на шаге 4 остаются `**fields`, чтобы схема ответа/тела не протекла в SQL. Фильтры — отдельный вход, им как раз место аргументом.

```text
GET /books?title=пикник&year=1972
        │
        ▼
Depends() собирает BookFilters
        │
        ▼
роут: repo.get_all(filters)
        │
        ▼
BookRepository: WHERE только для не-None
```

В `BaseRepository.get_all` фильтры **не** тащим: у жанров и авторов своих query нет, а `ilike` по `title` жанру не принадлежит. Это как на шаге 5: особое поведение — метод потомка.

---

## 1. `BookFilters` в `app/schemas.py`

В конец файла, рядом с `BookRead`:

```python
class BookFilters(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=300,
        description="Подстрока в названии, без учёта регистра",
    )
    year: int | None = Field(
        default=None,
        ge=1,
        le=2100,
        description="Точный год издания",
    )
    author_id: int | None = Field(default=None, ge=1)
    genre_id: int | None = Field(default=None, ge=1)
```

Это не Create/Update: клиент ничего не создаёт. Имя `Filters`, чтобы не спутать с телом PATCH.

---

## 2. `BookRepository.get_all`

В `app/repositories/books.py` замените `get_all` (остальные методы не трогайте):

```python
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Book
from app.repositories.base import BaseRepository
from app.schemas import BookFilters


class BookRepository(BaseRepository[Book]):
    model = Book

    def _with_relations(self):
        return select(Book).options(
            selectinload(Book.author),
            selectinload(Book.genre),
        )

    async def get_all(self, filters: BookFilters) -> Sequence[Book]:
        stmt = self._with_relations()
        if filters.title is not None:
            stmt = stmt.where(Book.title.ilike(f"%{filters.title}%"))
        if filters.year is not None:
            stmt = stmt.where(Book.year == filters.year)
        if filters.author_id is not None:
            stmt = stmt.where(Book.author_id == filters.author_id)
        if filters.genre_id is not None:
            stmt = stmt.where(Book.genre_id == filters.genre_id)
        result = await self._session.execute(stmt.order_by(Book.id))
        return result.scalars().all()

    async def get(self, obj_id: int) -> Book | None:
        result = await self._session.execute(
            self._with_relations().where(Book.id == obj_id)
        )
        return result.scalar_one_or_none()
```

`ilike` — регистронезависимый `LIKE` Postgres. `%` по краям: «пикник» найдёт «Пикник на обочине». Условие не пишем заранее «на все колонки»: лишний `AND title ILIKE '%%'` только мешает планировщику.

Сигнатура `get_all` у базы и у книги теперь разная — это нормально. Жанры по-прежнему зовут `get_all()` без аргументов.

---

## 3. `list_books` в `app/routes/books.py`

Импорт `BookFilters` и `Depends` / `Annotated`. Остальные хендлеры не меняются.

```python
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.deps import AuthorRepoDep, BookRepoDep, GenreRepoDep
from app.errors import NotFoundError
from app.schemas import BookCreate, BookFilters, BookRead, BookUpdate, ErrorRead

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=list[BookRead])
async def list_books(
    repo: BookRepoDep,
    filters: Annotated[BookFilters, Depends()],
) -> list[BookRead]:
    books = await repo.get_all(filters)
    return [BookRead.from_book(book) for book in books]
```

Роут больше ничего не распаковывает: тот же объект, что собрал FastAPI, уходит в SQL.

В `/docs` у `GET /books` появятся четыре необязательных параметра. Try it out заполняет query, не JSON.

---

## Разбор

Цепочка:

```text
GET /books?title=пикник&year=1972
  → FastAPI: query → BookFilters (Field ge / min_length)
  → list_books → repo.get_all(filters)
  → BookRepository: filters.title / filters.year / ...
  → SELECT ... WHERE title ILIKE '%пикник%' AND year = 1972
  → list[BookRead]  (хоть пустой)
```

| Слой | Знает про |
|------|-----------|
| `BookFilters` | имена полей, `ge`, `min_length`, тексты для Swagger |
| роут | `Depends()` + отдать объект в репозиторий |
| `BookRepository` | `filters.title`, `ilike` / `==` |
| `BaseRepository` | ничего из этого |

Если сложить фильтры в базу (`get_all(**filters)` у всех моделей), жанр начнёт принимать `title` и молча его игнорировать — хуже, чем явный метод у книги.

`%` и `_` в строке `title` для `LIKE` — служебные символы. Для учебного поиска не экранируем; в проде либо экранируют, либо берут `ilike` с `escape`.

---

## ✅ Проверка

Сиды с шага 9 aiohttp (или `python -m app.seed`): «Пикник на обочине» / 1972 / жанр 1, «Убийство в „Восточном экспрессе“» / 1934, «Реквием» / 1963.

```bash
source .venv/bin/activate
python -m app.main
```

```bash
curl -s 'http://127.0.0.1:8080/books' | python -m json.tool
curl -s 'http://127.0.0.1:8080/books?year=1972' | python -m json.tool
curl -s 'http://127.0.0.1:8080/books?title=пикник' | python -m json.tool
curl -s 'http://127.0.0.1:8080/books?genre_id=1'
curl -s 'http://127.0.0.1:8080/books?author_id=2&year=1934' | python -m json.tool
curl -s 'http://127.0.0.1:8080/books?year=1999'
curl -s -o /dev/null -w "%{http_code}\n" 'http://127.0.0.1:8080/books?year=0'
curl -s -o /dev/null -w "%{http_code}\n" 'http://127.0.0.1:8080/books?year=abc'
curl -s -o /dev/null -w "%{http_code}\n" 'http://127.0.0.1:8080/books?title='
```

Откройте [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs) → `GET /books` → параметры `title`, `year`, `author_id`, `genre_id`.

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | `GET /books` без query | все книги, как раньше |
| ☐ | `?year=1972` | одна книга (Пикник), если год в БД ещё 1972 |
| ☐ | `?title=пикник` | та же книга, регистр не важен |
| ☐ | `?author_id=2&year=1934` | «Восточный экспресс» (оба условия) |
| ☐ | `?year=1999` | `[]` и **200**, не 404 |
| ☐ | `?year=0` / `?year=abc` / `?title=` | **422**, ключ `detail` |
| ☐ | `/docs` | четыре optional query у `GET /books` |
| ☐ | `BaseRepository.get_all` | без `title` / `ilike` |
| ☐ | `BookRepository` | принимает `BookFilters`, не импортирует FastAPI |

**Все пункты отмечены?** → [step-07-final.md](step-07-final.md)
