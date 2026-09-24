# GraphQL для книг — обзор и архитектура

Пошаговая реализация — в [README.md](README.md). Этот файл — **карта**: зачем второй способ читать каталог, какое дерево отдаём, чего не меняем в таблицах.

> **Правило:** не пишите код «вперёд гайда». Сначала пакет и типы по папкам. Потом запросы в тех же папках и тонкий корень `Query`. Потом роут. Мутаций в уроке нет.

---

## 1. Зачем этот гайд

`GET /books` уже возвращает автора и жанр — но **строками**, именами:

```json
{
  "id": 1,
  "title": "Пикник на обочине",
  "year": 1972,
  "author_id": 1,
  "genre_id": 1,
  "author": "Аркадий Стругацкий",
  "genre": "фантастика"
}
```

Этого мало, если клиенту нужна биография, или наоборот — только название и жанр. Контракт REST фиксирован: сервер решает набор полей. Чтобы получить `bio`, нужен второй запрос `GET /authors/1`. Чтобы не тащить лишнее, нужен новый эндпоинт или query-флаг.

GraphQL переворачивает договор. Клиент присылает **форму ответа**:

```graphql
{
  books {
    title
    year
    author {
      name
      bio
    }
    genre {
      name
    }
  }
}
```

Сервер обходит это дерево и кладёт в `data` только запрошенное. Другой клиент может попросить `{ books { title } }` — SQL тот же, JSON короче.

Один URL на все такие чтения: `POST /graphql`. Отдельных `/graphql/books` нет.

---

## 2. Цепочка запроса

REST, как после FastAPI:

```text
GET /books  →  BookRepository.get_all  →  BookRead.from_book
                      selectinload(author, genre)
                      author и genre — строки (имена)
```

GraphQL:

```text
POST /graphql
  тело: { "query": "{ books { title author { bio } genre { name } } }" }
        │
        ▼
  Strawberry разбирает запрос по схеме
        │
        ▼
  Query (склейка GenreQuery, AuthorQuery, BookQuery)
        │
        ▼
  books/queries.py  →  BookRepository.get_all
        │                    selectinload(author, genre) уже есть
        ▼
  books/types.py  BookType.from_model
        author ← authors/types.py
        genre  ← genres/types.py
        │
        ▼
  { "data": { "books": [ ... ] } }
```

Репозиторий не переписываем. Он уже не даёт «голую» книгу без связей: `_with_relations()` грузит автора и жанр одним дополнительным SELECT на коллекцию (`selectinload`), не отдельным запросом на каждую книгу.

---

## 3. Что не трогаем

| Файл | Почему |
|------|--------|
| `app/models.py` | таблицы те же, миграции нет |
| `alembic/` | схема не меняется |
| `app/schemas.py` | `BookRead` остаётся контрактом REST |
| `app/routes/books.py` | `GET /books` не ломаем |
| `app/repositories/` | GraphQL вызывает `BookRepository` как есть |
| `task_1_client/` | отдельная задача |

Авторизации нет, как в остальном уроке.

---

## 4. Карта API (добавка)

Сервер: `http://127.0.0.1:8080`. Старые эндпоинты не меняются.

| Метод | URL | Назначение |
|-------|-----|------------|
| POST | `/graphql` | выполнить запрос, тело `{"query": "..."}` |
| GET | `/graphql` | GraphiQL в браузере |

Поля, которые появляются в схеме:

| Поле | Откуда в коде | Аргументы | Что внутри |
|------|--------------|-----------|------------|
| `genres` / `genre` | `genres/queries.py` | `id` у одной записи | жанр |
| `authors` / `author` | `authors/queries.py` | `id` у одной записи | автор, включая `bio` |
| `books` / `book` | `books/queries.py` | фильтры списка; `id` у одной книги | книга, внутри объекты автора и жанра |

У книги в схеме не строки, а объекты:

| Тип | Поля |
|-----|------|
| `Book` | `id`, `title`, `year`, `author`, `genre` |
| `Author` | `id`, `name`, `bio` |
| `Genre` | `id`, `name` |

Имена аргументов в схеме — **camelCase** (`authorId`), в Python — `author_id`. Strawberry переименовывает сам. REST по-прежнему на snake_case.

Книги, которой нет, REST отвечает **404**. GraphQL отвечает **HTTP 200**: в `data.book` будет `null`, текст ошибки — в массиве `errors`. Это норма протокола, не забытый статус.

---

## 5. Структура репозитория после гайда

```text
aiohttp_lesson/
├── requirements.txt              # + strawberry-graphql[fastapi]
├── app/
│   ├── graphql/
│   │   ├── __init__.py
│   │   ├── context.py            # сессия из info.context
│   │   ├── schema.py             # class Query(GenreQuery, AuthorQuery, BookQuery)
│   │   ├── genres/
│   │   │   ├── types.py
│   │   │   └── queries.py
│   │   ├── authors/
│   │   │   ├── types.py
│   │   │   └── queries.py
│   │   └── books/
│   │       ├── types.py          # вложенные author и genre
│   │       └── queries.py
│   └── routes/
│       └── __init__.py           # + GraphQLRouter
└── docs/
    └── graphql/
```

Пакеты `genres/`, `authors/`, `books/` повторяют `app/routes/` и `app/repositories/`: один ресурс — одна папка. `schema.py` только наследует три класса запросов. Четвёртый ресурс — новая папка и одна база в `class Query(...)`, файлы книг не открывают.

Типы — шаг 2. Запросы и склейка — шаг 3. Роут — шаг 4.

---

## 6. Этапы

| Этап | Файл | Что реализуете |
|------|------|----------------|
| 1 | [step-01-setup.md](step-01-setup.md) | пакет |
| 2 | [step-02-types.md](step-02-types.md) | типы в трёх пакетах |
| 3 | [step-03-query.md](step-03-query.md) | запросы в тех же пакетах, склейка корня |
| 4 | [step-04-route.md](step-04-route.md) | URL и сессия |
| 5 | [step-05-final.md](step-05-final.md) | чеклист |

**Начните здесь:** [README.md](README.md)
