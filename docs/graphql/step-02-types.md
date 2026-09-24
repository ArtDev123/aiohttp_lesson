# Шаг 2 — Типы по пакетам

**Предыдущий:** [step-01-setup.md](step-01-setup.md) · **Следующий:** [step-03-query.md](step-03-query.md)

## Задача

Описать форму ответа так, чтобы жанр, автор и книга жили в **своих** пакетах. Книга ссылается на типы автора и жанра, не на строки с именами. Запросов (`books`, `authors`, …) ещё нет — их подключит шаг 3 в тех же папках.

Один файл `types.py` на все три сущности не создавайте. Следующий ресурс (полка, читатель) тогда придётся в него вклинивать.

---

## Теория: пакет на ресурс

REST уже разложен так:

```text
app/routes/genres.py
app/routes/authors.py
app/routes/books.py

app/repositories/genres.py
app/repositories/authors.py
app/repositories/books.py
```

GraphQL повторяет этот разрез. Тип и запрос ресурса лежат рядом:

```text
app/graphql/genres/types.py      # шаг 2
app/graphql/genres/queries.py    # шаг 3
app/graphql/authors/types.py
app/graphql/authors/queries.py
app/graphql/books/types.py
app/graphql/books/queries.py
app/graphql/schema.py            # шаг 3: только склейка
app/graphql/context.py           # шаг 3: сессия для всех резолверов
```

Общего «типы всех таблиц» нет. `schema.py` не знает про поля книги — он только перечисляет классы запросов.

Зависимость типов односторонняя:

```text
genres/types.py     никого не импортирует
authors/types.py    никого не импортирует
books/types.py      импортирует AuthorType и GenreType
```

Книга содержит автора и жанр, поэтому она зависит от их типов. Обратной связи нет: у автора в этом уроке нет поля `books`. Иначе `authors` и `books` начнут импортировать друг друга. Когда такое поле понадобится, его вешают отдельно через `strawberry.lazy("app.graphql.books.types")`, не сливая пакеты обратно в один файл.

---

## Теория: тип схемы и модель таблицы

`class Book` в `app/models.py` — строка Postgres. `class BookRead` — JSON для REST, автор там `str`.

Тип GraphQL — третья вещь. Клиент видит только его:

```graphql
type Book {
  id: Int!
  title: String!
  year: Int
  author: Author!
  genre: Genre!
}

type Author {
  id: Int!
  name: String!
  bio: String
}

type Genre {
  id: Int!
  name: String!
}
```

`String!` — поле обязано быть в ответе. `String` без `!` — можно `null` (у нас так у `bio` и `year`).

Восклицательный знак ставит Strawberry сам: `str` → `String!`, `str | None` → `String`.

Вложенный `author: Author!` — цель гайда. В REST то же место занято именем. Здесь клиент заходит внутрь: `author { name bio }` или только `author { id }`.

Поля `author_id` и `genre_id` в тип книги не кладём. Идентификатор есть у вложенного объекта (`author { id }`).

---

## Теория: поле, которое не ходит в SQL

Резолвер «когда спросили автора — сделай `SELECT`» на списке из 20 книг даёт 1 запрос книг + 20 авторов + 20 жанров. Это **N+1**.

`BookRepository` уже делает `selectinload`: после `get` / `get_all` заполнены `book.author` и `book.genre`. Тип GraphQL только копирует уже загруженное. Отдельного SQL на поле `author` нет.

Если клиент не попросил `author`, этого ключа не будет в JSON. `selectinload` в репозитории всё равно отработает — он не смотрит в текст GraphQL. Резать SQL по набору полей — не этот шаг.

---

## 1. Каркас пакетов

Пустые `__init__.py` в каждой папке:

```text
app/graphql/__init__.py
app/graphql/genres/__init__.py
app/graphql/authors/__init__.py
app/graphql/books/__init__.py
```

Файлов `queries.py`, `schema.py`, `context.py` на этом шаге нет.

---

## 2. `app/graphql/genres/types.py`

Жанр ни от кого не зависит — его пишем первым.

```python
import strawberry

from app.models import Genre


@strawberry.type(name="Genre")
class GenreType:
    id: int
    name: str

    @classmethod
    def from_model(cls, genre: Genre) -> "GenreType":
        return cls(id=genre.id, name=genre.name)
```

---

## 3. `app/graphql/authors/types.py`

```python
import strawberry

from app.models import Author


@strawberry.type(name="Author")
class AuthorType:
    id: int
    name: str
    bio: str | None

    @classmethod
    def from_model(cls, author: Author) -> "AuthorType":
        return cls(id=author.id, name=author.name, bio=author.bio)
```

`bio: str | None` повторяет колонку: текст может отсутствовать.

---

## 4. `app/graphql/books/types.py`

Книга собирает уже описанные типы. Свой `Author` здесь не объявляйте.

```python
import strawberry

from app.graphql.authors.types import AuthorType
from app.graphql.genres.types import GenreType
from app.models import Book


@strawberry.type(name="Book")
class BookType:
    id: int
    title: str
    year: int | None
    author: AuthorType
    genre: GenreType

    @classmethod
    def from_model(cls, book: Book) -> "BookType":
        return cls(
            id=book.id,
            title=book.title,
            year=book.year,
            author=AuthorType.from_model(book.author),
            genre=GenreType.from_model(book.genre),
        )
```

### Разбор

`@strawberry.type` помечает класс как тип схемы. Имя в SDL по умолчанию совпадает с классом (`BookType`). Параметр `name="Book"` публикует короткие имена — их пишет клиент.

`from_model` — тот же приём, что `BookRead.from_book`, только автор и жанр остаются объектами. Метод читает `book.author` и `book.genre`. На книге без `selectinload` в async-сессии SQLAlchemy запретит ленивый `SELECT`. На шаге 3 книгу берём только из `BookRepository`.

Пока нет `strawberry.Schema(...)`, импорт этих модулей ничего не слушает на порту 8080.

---

## ✅ Проверка

```bash
source .venv/bin/activate
python -c "
from app.graphql.authors.types import AuthorType
from app.graphql.books.types import BookType
from app.graphql.genres.types import GenreType
g = GenreType(id=1, name='фантастика')
a = AuthorType(id=1, name='Аркадий Стругацкий', bio='Советский писатель-фантаст')
b = BookType(id=1, title='Пикник на обочине', year=1972, author=a, genre=g)
assert b.author.bio.startswith('Советский')
assert b.genre.name == 'фантастика'
print(b.title, b.author.name, b.genre.name)
"
```

| ☐ | Проверка |
|---|----------|
| ☐ | скрипт печатает название, имя автора и жанр |
| ☐ | три пакета: `genres`, `authors`, `books`, в каждом свой `types.py` |
| ☐ | `books/types.py` импортирует автора и жанр, не объявляет их заново |
| ☐ | общего `app/graphql/types.py` нет |
| ☐ | `GET /books` по-прежнему отдаёт автора и жанр строками |
| ☐ | `queries.py` и `schema.py` ещё нет |
