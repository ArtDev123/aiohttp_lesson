# Шаг 3 — Запросы в тех же пакетах

**Предыдущий:** [step-02-types.md](step-02-types.md) · **Следующий:** [step-04-route.md](step-04-route.md)

## Задача

Положить резолверы рядом с типами: `genres/queries.py`, `authors/queries.py`, `books/queries.py`. Корень схемы — отдельный тонкий файл, он только склеивает три класса. HTTP-роута ещё нет: схему можно исполнить из Python.

Поля книг не пишите в общий `Query` на сотню методов. Иначе автор и жанр, которые нужны уже сейчас, и любой следующий ресурс окажутся в одном классе.

---

## Теория: корень собирается наследованием

Клиент начинает с корня:

```graphql
{
  books {
    title
    author { name bio }
    genre { name }
  }
}
```

`books` — поле типа `Query`. Функция под ним — **резолвер**. Вложенные `title`, `author`, `genre` отдельно не резолвим: они уже лежат в `BookType`.

В Python корень не содержит этих методов. Он наследует готовые классы:

```python
@strawberry.type
class Query(GenreQuery, AuthorQuery, BookQuery):
    pass
```

Strawberry складывает поля всех баз в один `type Query`. Добавить полки — завести `shelves/queries.py` с `ShelfQuery` и дописать его в скобки. Файлы книг, авторов и жанров при этом не меняются.

Одинаковых имён полей в базах быть не должно: два `books` вольются в один слот и схема не соберётся.

---

## Теория: сессия одна на все пакеты

Резолвер — не эндпоинт, `Depends` в сигнатуру сам не встанет. Сессию читают из контекста. Доставалка одна, в `context.py`, чтобы каждый пакет не копировал `info.context["session"]`.

На этом шаге контекст передаём руками в `schema.execute`. На шаге 4 его заполнит FastAPI.

Резолвер книги:

```text
get_session(info)
    → BookRepository(session)
    → get_all / get          # selectinload автора и жанра
    → BookType.from_model
```

Жанр и автор ходят в свои репозитории и в SQL связей не нуждаются: у них нет вложенных объектов.

Если записи нет, `get` бросает `NotFoundError`. В `execute` это попадёт в `result.errors`. По HTTP на шаге 4 статус останется 200.

Возврат одиночных полей — `BookType | None` (так же автор и жанр). Аннотация без `| None` делает поле схемы `Book!`. Ошибка в не-nullable поле по правилам GraphQL обнуляет весь `data`, а не только `book`. С `| None` ответ такой: `{"data": {"book": null}, "errors": [...]}`. Списки (`books`, `authors`, `genres`) остаются без `None`: пустой каталог — это `[]`, не ошибка.

---

## 1. `app/graphql/context.py`

```python
import strawberry
from sqlalchemy.ext.asyncio import AsyncSession


def get_session(info: strawberry.Info) -> AsyncSession:
    return info.context["session"]
```

### Разбор

`info: strawberry.Info` — служебный аргумент резолвера. В схему он не попадает, клиент его не передаёт.

Функция ничего не открывает и не закрывает. Сессию создаёт тот, кто вызвал `execute` (сейчас скрипт, на шаге 4 — `SessionDep`).

---

## 2. `app/graphql/genres/queries.py`

```python
import strawberry

from app.graphql.context import get_session
from app.graphql.genres.types import GenreType
from app.repositories import GenreRepository


@strawberry.type
class GenreQuery:
    @strawberry.field
    async def genres(self, info: strawberry.Info) -> list[GenreType]:
        repo = GenreRepository(get_session(info))
        rows = await repo.get_all()
        return [GenreType.from_model(row) for row in rows]

    @strawberry.field
    async def genre(self, info: strawberry.Info, id: int) -> GenreType | None:
        repo = GenreRepository(get_session(info))
        row = await repo.get(id)
        return GenreType.from_model(row)
```

---

## 3. `app/graphql/authors/queries.py`

```python
import strawberry

from app.graphql.authors.types import AuthorType
from app.graphql.context import get_session
from app.repositories import AuthorRepository


@strawberry.type
class AuthorQuery:
    @strawberry.field
    async def authors(self, info: strawberry.Info) -> list[AuthorType]:
        repo = AuthorRepository(get_session(info))
        rows = await repo.get_all()
        return [AuthorType.from_model(row) for row in rows]

    @strawberry.field
    async def author(self, info: strawberry.Info, id: int) -> AuthorType | None:
        repo = AuthorRepository(get_session(info))
        row = await repo.get(id)
        return AuthorType.from_model(row)
```

Поле `author` здесь — запись автора целиком (`bio` тоже). Это не то же самое, что вложенный `author { … }` внутри книги: тот собирается в `BookType.from_model` без отдельного резолвера.

---

## 4. `app/graphql/books/queries.py`

Фильтры те же, что у `GET /books`. Имена аргументов в Python — `author_id`. В схеме Strawberry сделает `authorId`.

```python
import strawberry

from app.graphql.books.types import BookType
from app.graphql.context import get_session
from app.repositories import BookRepository
from app.schemas import BookFilters


@strawberry.type
class BookQuery:
    @strawberry.field
    async def books(
        self,
        info: strawberry.Info,
        title: str | None = None,
        year: int | None = None,
        author_id: int | None = None,
        genre_id: int | None = None,
    ) -> list[BookType]:
        repo = BookRepository(get_session(info))
        rows = await repo.get_all(
            BookFilters(
                title=title,
                year=year,
                author_id=author_id,
                genre_id=genre_id,
            )
        )
        return [BookType.from_model(book) for book in rows]

    @strawberry.field
    async def book(self, info: strawberry.Info, id: int) -> BookType | None:
        repo = BookRepository(get_session(info))
        book = await repo.get(id)
        return BookType.from_model(book)
```

### Разбор

`BookFilters(...)` переиспользуем, второй `WHERE` не пишем. `None` значит «фильтра нет». Пустую строку `title=""` сюда не кладите: у поля в Pydantic `min_length=1`.

`@strawberry.field` на методе — резолвер. `self` у корня пустой, данные в `info`.

Одна книга в запросе клиента:

```graphql
{
  book(id: 1) {
    title
    year
    author { id name bio }
    genre { id name }
  }
}
```

`id` не превращается в `Id`: это одно слово.

---

## 5. `app/graphql/schema.py`

Только склейка. Полей здесь нет.

```python
import strawberry

from app.graphql.authors.queries import AuthorQuery
from app.graphql.books.queries import BookQuery
from app.graphql.genres.queries import GenreQuery


@strawberry.type
class Query(GenreQuery, AuthorQuery, BookQuery):
    pass


schema = strawberry.Schema(query=Query)
```

Мутацию не передаём — в схеме не будет `type Mutation`.

Порядок баз в скобках задаёт порядок полей в SDL. На выполнение запроса он не влияет.

SDL без базы:

```bash
python -c "from app.graphql.schema import schema; print(schema.as_str())"
```

В тексте: `type Book` с `author: Author!` и `genre: Genre!`. У `Query` — `genres`, `genre`, `authors`, `author`, `books`, `book`. Методов внутри `class Query` по-прежнему ноль.

---

## 6. Прогон без HTTP

Нужны живая Postgres и сиды (`python -m app.seed`, если каталог пустой). Сервер можно не запускать.

`scripts/check_graphql.py` — временный файл, в git не кладите. После проверки удалите.

```python
import asyncio

from app.db import make_engine, make_session_factory
from app.graphql.schema import schema

QUERY = """
{
  books {
    title
    year
    author { name bio }
    genre { name }
  }
}
"""


async def main() -> None:
    engine = make_engine()
    factory = make_session_factory(engine)
    async with factory() as session:
        result = await schema.execute(QUERY, context_value={"session": session})
    await engine.dispose()
    if result.errors:
        raise SystemExit(result.errors)
    for book in result.data["books"]:
        print(
            book["title"],
            "—",
            book["author"]["name"],
            "/",
            book["genre"]["name"],
        )


if __name__ == "__main__":
    asyncio.run(main())
```

```bash
python scripts/check_graphql.py
```

Ожидание (среди строк сида, их может быть много):

```text
Пикник на обочине — Аркадий Стругацкий / фантастика
Убийство в «Восточном экспрессе» — Агата Кристи / детектив
Реквием — Анна Ахматова / поэзия
```

У «Пикника» в `author.bio` — «Советский писатель-фантаст». В REST-списке книг этого поля нет.

Тот же скрипт с другим текстом проверяет, что автор читается и своим полем, не только из книги. Замените `QUERY`:

```graphql
{
  authors {
    name
    bio
  }
}
```

Фильтр книг:

```graphql
{
  books(title: "Реквием") {
    title
    author { name }
    genre { name }
  }
}
```

В `data.books` одна книга, жанр — поэзия.

---

## ✅ Проверка

| ☐ | Проверка |
|---|----------|
| ☐ | у каждого ресурса свой `queries.py`, рядом с `types.py` |
| ☐ | в `schema.py` нет полей, только `class Query(GenreQuery, AuthorQuery, BookQuery)` |
| ☐ | `schema.as_str()` показывает `author: Author!`, `genre: Genre!` и поля всех трёх ресурсов |
| ☐ | `check_graphql.py` печатает три сидовые книги с автором и жанром |
| ☐ | у автора «Пикника» в результате есть `bio` |
| ☐ | `authors { name bio }` возвращает трёх авторов сида |
| ☐ | `books(title: "Реквием")` возвращает одну книгу |
| ☐ | `GET /books` не изменился |
| ☐ | временный скрипт удалён, роута `/graphql` ещё нет |
