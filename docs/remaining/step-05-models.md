# Шаг 5 — Модели: Genre, Author, Book

**Предыдущий:** [step-04-app.md](step-04-app.md) · **Следующий:** [step-06-alembic.md](step-06-alembic.md)

## Задача

Описать три таблицы библиотеки в SQLAlchemy 2. Без моделей Alembic и CRUD не к чему привязывать.

```text
Genre
  └── Book (FK genre_id)
Author
  └── Book (FK author_id)
```

---

## Теория: SQLAlchemy 2.0 mapped style

Классический Django: `models.CharField(...)`. Здесь:

```python
class Base(DeclarativeBase):
    pass

class Genre(Base):
    __tablename__ = "genres"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
```

| Конструкция | Зачем |
|-------------|--------|
| `DeclarativeBase` | общий metadata для Alembic (`Base.metadata`) |
| `Mapped[str]` | тип для type-checker и для ORM |
| `mapped_column` | колонка в таблице |
| `relationship` + `back_populates` | `book.author`, `author.books` без ручного JOIN в каждом запросе |
| `ForeignKey("authors.id")` | ограничение в БД |

SQLAlchemy — таблицы. JSON входа/выхода — Pydantic на шаге 7 (`GenreCreate` / `GenreRead`). В ORM-класс `to_dict()` не кладём: иначе контракт API размажется по моделям БД.

Таблицы **не** создаём через `Base.metadata.create_all` — это работа Alembic на следующем шаге.

---

## Код — `app/models.py`

```python
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    books: Mapped[list["Book"]] = relationship(back_populates="genre")


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    books: Mapped[list["Book"]] = relationship(back_populates="author")


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"))
    genre_id: Mapped[int] = mapped_column(ForeignKey("genres.id"))

    author: Mapped[Author] = relationship(back_populates="books")
    genre: Mapped[Genre] = relationship(back_populates="books")
```

**Разбор полей:**

| Поле | Зачем |
|------|--------|
| `Genre.name` unique | не плодим «фантастика» дважды |
| `Author.bio` nullable | краткая справка, можно пусто |
| `Book.year` nullable | год издания не всегда известен |
| `author_id` / `genre_id` | книга обязана ссылаться на существующие строки |

`Book.author.name` понадобится в `BookRead.from_book` на шаге 7. В списке книг обязателен `selectinload`, иначе N+1 или ошибка ленивой загрузки вне сессии.

---

## ✅ Проверка

```bash
source .venv/bin/activate
python -c "from app.models import Genre, Author, Book, Base; print(list(Base.metadata.tables))"
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | Импорт моделей | `['genres', 'authors', 'books']` (порядок может отличаться) |
| ☐ | Сервер с шага 4 всё ещё стартует | `/health` отвечает `ok` |

Таблиц в Postgres ещё нет — это нормально до шага 6.

**Все пункты отмечены?** → [step-06-alembic.md](step-06-alembic.md)
