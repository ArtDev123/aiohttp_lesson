# Шаг 5 — Базовый класс репозитория

**Предыдущий:** [step-04-repos.md](step-04-repos.md) · **Следующий:** [step-06-final.md](step-06-final.md)

## Задача

Три репозитория на шаге 4 отличаются в основном именем модели. Вынести общее в `BaseRepository`: `get_all`, `get`, `add`, `update`. Дочерние классы задают `model` и больше ничего — кроме книг, где остаётся `selectinload`.

Фильтры, пагинация, сервисный слой, загрузка связей в базе — **не нужны**. Это учебный generic CRUD, не «платформа».

---

## Теория: один класс, разный `model`

Сейчас копипаста:

```python
result = await self._session.execute(select(Genre).order_by(Genre.id))
# ...
result = await self._session.execute(select(Author).order_by(Author.id))
```

Меняется только модель. Базовый класс знает SQLAlchemy, не знает Genre/Author/Book:

```text
BaseRepository[ModelType]
    get_all / get / add / update     ← общий SQL
        │
        ├── GenreRepository.model = Genre
        ├── AuthorRepository.model = Author
        └── BookRepository.model = Book
                └── свои get / get_all  (selectinload)
```

`Generic[ModelType]` — подсказка для редактора: `GenreRepository().get(1)` имеет тип `Genre | None`, не `Any`. На рантайме это обычное наследование.

Классовая переменная `model` — какую таблицу трогать. Её задаёт потомок, базовый код пишет `select(self.model)` и `self.model(**fields)`.

Сессию по-прежнему кладём в конструктор (как на шаге 4). Методы базы **не** принимают `session` аргументом: её уже инжектит FastAPI через `Depends`.

Связи (`joinedload` / `selectinload` / «подгрузи relationship по имени») в базовый класс не тащим. Для жанра и автора `session.get` достаточно. Для книги — единственное переопределение `get` / `get_all`.

---

## 1. `app/repositories/base.py`

```python
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class BaseRepository(Generic[ModelType]):
    model: type[ModelType]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> Sequence[ModelType]:
        result = await self._session.execute(
            select(self.model).order_by(self.model.id)
        )
        return result.scalars().all()

    async def get(self, obj_id: int) -> ModelType | None:
        return await self._session.get(self.model, obj_id)

    async def add(self, **fields: Any) -> ModelType:
        obj = self.model(**fields)
        self._session.add(obj)
        await self._session.commit()
        loaded = await self.get(obj.id)
        return loaded

    async def update(self, obj_id: int, **fields: Any) -> ModelType | None:
        obj = await self.get(obj_id)
        if obj is None:
            return None
        for key, value in fields.items():
            setattr(obj, key, value)
        await self._session.commit()
        return await self.get(obj.id)
```

После `commit` снова зовём `self.get`, а не `refresh`: у `BookRepository` свой `get` с `selectinload`, и `add`/`update` из базы автоматически подхватят актуальные имена автора и жанра.

`order_by(self.model.id)` работает, потому что у всех трёх таблиц есть `id`. Другого PK в этом уроке нет.

---

## 2. Потомки

### `app/repositories/genres.py`

```python
from app.models import Genre
from app.repositories.base import BaseRepository


class GenreRepository(BaseRepository[Genre]):
    model = Genre
```

### `app/repositories/authors.py`

```python
from app.models import Author
from app.repositories.base import BaseRepository


class AuthorRepository(BaseRepository[Author]):
    model = Author
```

### `app/repositories/books.py`

```python
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Book
from app.repositories.base import BaseRepository


class BookRepository(BaseRepository[Book]):
    model = Book

    def _with_relations(self):
        return select(Book).options(
            selectinload(Book.author),
            selectinload(Book.genre),
        )

    async def get_all(self) -> Sequence[Book]:
        result = await self._session.execute(self._with_relations().order_by(Book.id))
        return result.scalars().all()

    async def get(self, obj_id: int) -> Book | None:
        result = await self._session.execute(
            self._with_relations().where(Book.id == obj_id)
        )
        return result.scalar_one_or_none()
```

`add` и `update` не переопределяем: они вызывают `self.get`, а `self` у книги — уже этот класс.

Роуты и `app/deps.py` **не меняются**: те же `GenreRepoDep`, те же `repo.get_all()` / `repo.update(...)`.

`app/repositories/__init__.py` можно не трогать, если экспортирует те же три класса.

---

## Разбор: чего нет в базе специально

| Не кладём в `BaseRepository` | Почему |
|------------------------------|--------|
| фильтры / `ilike` / `in` | один учебный список, без поиска |
| `limit` / `offset` | пагинация — отдельная тема |
| `relationships=["author"]` | магия, которую не видно в SQL |
| Pydantic `dto` / `model_dump` | роут уже отдал `**fields` |
| `session` в каждом методе | сессия в конструкторе с шага 4 |
| сервис над репозиторием | 404 и FK остаются в роуте |

Если понадобится `get_by_name` — метод пишут в потомке, базу не раздувают.

---

## ✅ Проверка

```bash
python -c "from app.repositories import GenreRepository, AuthorRepository, BookRepository; from app.repositories.base import BaseRepository; print(issubclass(GenreRepository, BaseRepository))"
```

Должно напечатать `True`. Перезапустите сервер и прогоните те же curl, что на шаге 4: список, деталь, POST, PATCH.

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | `GenreRepository` / `AuthorRepository` | только `model = ...`, без своего SQL |
| ☐ | `BookRepository` | свои `get` / `get_all`, без своих `add` / `update` |
| ☐ | GET `/books` | имена автора и жанра на месте |
| ☐ | PATCH жанра и книги | `200`, как на шаге 4 |
| ☐ | Роуты | не изменились |
| ☐ | В `base.py` нет FastAPI и нет `selectinload` | — |

**Все пункты отмечены?** → [step-06-final.md](step-06-final.md)
