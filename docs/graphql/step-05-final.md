# Шаг 5 — Финальный прогон

**Предыдущий:** [step-04-route.md](step-04-route.md) · **К карте:** [guide.md](guide.md)

## Задача

Одним проходом проверить, что клиент забирает книгу вместе с автором и жанром, REST не сломан, чужой id не превращается в HTTP 404.

Сервер запущен (`python -m app.main` или контейнер `app`). Сиды на месте.

---

## 1. Чеклист

| ☐ | Проверка |
|---|----------|
| ☐ | `GET /graphql` открывает GraphiQL |
| ☐ | `books { title author { name bio } genre { name } }` — у «Пикника» автор Стругацкий и жанр фантастика, в `bio` не пусто |
| ☐ | `books { title genre { name } }` — в элементах нет ключа `author` |
| ☐ | `book(id: …) { author { id name bio } genre { id name } }` — оба объекта, не строки |
| ☐ | `books(title: "Реквием")` — одна книга |
| ☐ | `books(genreId: <id поэзии>)` — в списке «Реквием» (id жанра возьмите из `genre { id }` любого запроса) |
| ☐ | `book(id: 999999)` — HTTP 200, `book: null`, `errors[0].message` про книгу |
| ☐ | запрос поля `isbn` — `errors`, в схеме такого поля нет |
| ☐ | `GET /books` — автор и жанр по-прежнему строки |
| ☐ | `GET /docs` — REST на месте, `/graphql` в Swagger может быть без полей схемы (её смотрят в GraphiQL) |
| ☐ | миграций новых нет: `alembic current` тот же revision, что до гайда |

Команда для списка:

```bash
curl -s http://127.0.0.1:8080/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ books { title author { name bio } genre { name } } }"}'
```

---

## 2. Что покрыли

```text
POST /graphql   books        список + author + genre
POST /graphql   books(...)   те же фильтры, что GET /books
POST /graphql   book(id)     одна книга, вложенные объекты
GET  /graphql   GraphiQL
GET  /books     REST не менялся
```

Цепочка:

```text
GraphQLRouter
  → SessionDep → context["session"]
  → Query(GenreQuery, AuthorQuery, BookQuery)
  → books/queries.py → BookRepository
  → selectinload(author), selectinload(genre)
  → books/types.py собирает AuthorType и GenreType
  → JSON только с запрошенными полями
```

---

## 3. Было / стало

| Тема | REST `GET /books` | GraphQL `books` |
|------|-------------------|-----------------|
| Адрес | свой URL на ресурс | один `POST /graphql` |
| Автор | строка, имя | объект `id`, `name`, `bio` — что попросили |
| Жанр | строка, имя | объект `id`, `name` |
| Лишние поля | всегда в ответе | клиент их не пишет — их нет в JSON |
| Нет книги | HTTP 404 | HTTP 200 и `errors` |
| Имена полей | `author_id` | аргумент `authorId` |

Оба канала читают один репозиторий. Создавать книгу по-прежнему через `POST /books`.

---

## 4. Типичные ошибки

| Симптом | Что проверить |
|---------|----------------|
| `ImportError: strawberry` | не тот venv или образ Docker без пересборки |
| GraphiQL 404 | `include_router` забыли или префикс не `/graphql` |
| `MissingGreenlet` / lazy load | в резолвер попала книга не из `BookRepository` (нет `selectinload`) |
| в ответе автор строкой | смотрите `GET /books`, а не `/graphql` |
| `authorId` «неизвестное поле» | в запросе написали `author_id` — в схеме camelCase |
| пустой `bio` | сиды не залиты или это не именованная книга из `NAMED_BOOKS` |
| HTTP 500 на чужой id | `NotFoundError` не долетает до Strawberry (её перехватили раньше и не пробросили) |
| `context` не dict / нет `session` | `graphql_context` возвращает не `{"session": session}` |

---

## 5. Новый ресурс без переделки книг

Полка, читатель, что угодно ещё — та же тройка файлов, что у жанра:

```text
app/graphql/shelves/types.py      ShelfType
app/graphql/shelves/queries.py    class ShelfQuery
```

И одна правка склейки:

```python
class Query(GenreQuery, AuthorQuery, BookQuery, ShelfQuery):
    pass
```

`books/types.py` и `books/queries.py` не открывают. Поле «книги автора» вешают на `AuthorType` через `strawberry.lazy("app.graphql.books.types")`, а не переносом типов в общий файл.

Дальше по желанию, не в этом уроке:

- `mutations.py` в том же пакете и вторая склейка `class Mutation(...)`.
- DataLoader, если вложенное поле начнёт само ходить в SQL.
- Не грузить `author`/`genre`, если клиент их не запросил: смотреть `info.selected_fields` и выбирать `selectinload` точечно.
- Тест в `tests/`: `TestClient.post("/graphql", json={"query": "..."})` и `assert` на `data["books"][0]["author"]["bio"]`.

Карта раздела: [guide.md](guide.md) · FastAPI: [../fastapi/README.md](../fastapi/README.md) · pytest: [../pytest/README.md](../pytest/README.md)
