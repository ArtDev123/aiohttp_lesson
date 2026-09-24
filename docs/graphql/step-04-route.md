# Шаг 4 — Роут `/graphql`

**Предыдущий:** [step-03-query.md](step-03-query.md) · **Следующий:** [step-05-final.md](step-05-final.md)

## Задача

Открыть схему по HTTP и прокинуть туда ту же async-сессию, что у REST. После шага книгу с автором и жанром можно спросить из браузера (GraphiQL) и через `curl`. Отдельный порт не нужен.

---

## Теория: контекст на запрос

`schema.execute(..., context_value=...)` на шаге 3 подсовывал сессию вручную. Из сети это должен сделать FastAPI: один запрос — одна сессия — один контекст.

```text
POST /graphql
  → Depends(get_session)     # уже есть, SessionDep
  → context_getter кладёт её в dict
  → резолвер читает get_session(info)  # app/graphql/context.py
  → сессия закрывается в конце запроса, как у GET /books
```

`GraphQLRouter` — это `APIRouter`. Его подключают через `include_router`, не через отдельный сервер.

По умолчанию IDE на том же пути: браузерный `GET /graphql` открывает GraphiQL, `POST` выполняет запрос. REST-документация остаётся на `/docs`.

---

## Теория: HTTP 200 и массив `errors`

Успешный ответ:

```json
{
  "data": {
    "book": {
      "title": "Пикник на обочине",
      "author": {"name": "Аркадий Стругацкий", "bio": "Советский писатель-фантаст"},
      "genre": {"name": "фантастика"}
    }
  }
}
```

Книги с `id`, которого нет:

```json
{
  "data": { "book": null },
  "errors": [{ "message": "Book not found", "path": ["book"] }]
}
```

Статус при этом **200**. Клиент GraphQL смотрит на `errors`, а не на код HTTP. `NotFoundError` из репозитория Strawberry превращает в этот массив: сообщение исключения становится `message`. Обработчик 404 в `main.py` на `/graphql` не срабатывает — исключение ловит слой GraphQL, до вашего `exception_handler` оно не доходит.

Ошибка в тексте запроса (поле, которого нет в схеме) тоже 200 и `errors`, `data` будет `null`. Это не 422 в стиле FastAPI.

---

## Теория: camelCase в схеме

Аргумент Python `author_id` клиент пишет как `authorId`:

```graphql
{
  books(authorId: 1) {
    title
    genre { name }
  }
}
```

Поля ответа тоже в camelCase, если в типе несколько слов. У нас `id`, `title`, `year`, `name`, `bio` — одно слово, писать их иначе не нужно.

---

## 1. Подключить роут

В `app/routes/__init__.py` добавьте импорты и регистрацию. Остальные `include_router` не удаляйте.

```python
from strawberry.fastapi import GraphQLRouter

from app.db import SessionDep
from app.graphql.schema import schema
```

Функция контекста — рядом с `health_router` (или сразу над `register_routes`):

```python
async def graphql_context(session: SessionDep) -> dict:
    return {"session": session}
```

Внутри `register_routes`, после REST-роутов:

```python
    app.include_router(
        GraphQLRouter(schema, context_getter=graphql_context),
        prefix="/graphql",
    )
```

### Разбор

`context_getter` — зависимость FastAPI. `SessionDep` внутри него открывает сессию так же, как в `list_books`. Strawberry сольёт ваш dict со служебными ключами (`request`, `response`). Ключ `"session"` уже ждёт `get_session` с шага 3. Пакеты жанров, авторов и книг этот dict не собирают — им всё равно, кто положил сессию.

`prefix="/graphql"` вешает и POST, и GET (GraphiQL) на этот путь.

Порядок роутов важен только относительно `/{параметр}`. Отдельный префикс `/graphql` с `/books` не конфликтует.

---

## 2. Если API в Docker

Пакет ставится в образ на сборке. После правки `requirements.txt`:

```bash
docker compose build app
docker compose up -d app
```

Код `app/` у вас, скорее всего, скопирован в образ, а не примонтирован томом (том есть только у `exports/`). Тогда пересоберите образ и после изменений в `app/graphql/`. Локальный `python -m app.main` с `--reload` подхватывает файлы сам. Воркер Celery этот роут не обслуживает — перезапускать его незачем.

---

## 3. Запросы

Сервер:

```bash
python -m app.main
```

Браузер: [http://127.0.0.1:8080/graphql](http://127.0.0.1:8080/graphql) — слева текст, справа JSON.

Список с автором и жанром:

```graphql
{
  books {
    id
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

Только название и жанр — автор в ответ не входит, хотя в базе связь есть:

```graphql
{
  books {
    title
    genre { name }
  }
}
```

Одна книга (подставьте id из списка):

```graphql
{
  book(id: 1) {
    title
    author { id name bio }
    genre { id name }
  }
}
```

Тот же список через `curl`:

```bash
curl -s http://127.0.0.1:8080/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ books { title author { name bio } genre { name } } }"}'
```

Фильтр:

```bash
curl -s http://127.0.0.1:8080/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ books(title: \"Реквием\") { title author { name } genre { name } } }"}'
```

Чужая книга:

```bash
curl -s http://127.0.0.1:8080/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ book(id: 999999) { title author { name } } }"}'
```

В ответе `"book": null` и `errors`. Код HTTP — 200:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ book(id: 999999) { title } }"}'
```

REST на месте:

```bash
curl -s http://127.0.0.1:8080/books/1
```

Там `author` и `genre` снова строки.

---

## ✅ Проверка

| ☐ | Проверка |
|---|----------|
| ☐ | GraphiQL открывается на `GET /graphql` |
| ☐ | `books` отдаёт `author.bio` и `genre.name` |
| ☐ | запрос без `author` не содержит ключ `author` в JSON |
| ☐ | `books(title: "Реквием")` — одна книга, жанр «поэзия» |
| ☐ | `book(id: 999999)` — HTTP 200, `data.book` = `null`, есть `errors` |
| ☐ | `GET /books/1` по-прежнему REST: автор и жанр строками |
| ☐ | `GET /health` → `{"status":"ok"}` |
