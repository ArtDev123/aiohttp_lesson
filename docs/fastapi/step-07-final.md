# Шаг 7 — Финальный прогон и сравнение

**Предыдущий:** [step-06-filters.md](step-06-filters.md) · **К карте:** [guide.md](guide.md)

## Задача

Прогнать API на FastAPI целиком: сиды, CRUD + PATCH, query-фильтры книг, Swagger, клиент задачи 1 без изменений.

---

## 1. Сиды и запуск

Схема БД не менялась — новые миграции не нужны. `app/seed.py` работает через `make_engine` / `make_session_factory`, FastAPI ему не нужен.

```bash
source .venv/bin/activate
make migrate
python -m app.seed
python -m app.main
```

Если сиды уже залиты в первом гайде, скрипт напишет «Сиды уже есть, пропускаем.» Это ожидаемо.

Клиент (jsonplaceholder, aiohttp):

```bash
python -m task_1_client.main
```

---

## 2. Чеклист API

```bash
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/books | python -m json.tool
curl -s 'http://127.0.0.1:8080/books?year=1972' | python -m json.tool
curl -s 'http://127.0.0.1:8080/books?title=пикник'
curl -s -X PATCH http://127.0.0.1:8080/books/1 \
  -H 'Content-Type: application/json' \
  -d '{"year":1973}'
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/books/999
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8080/genres \
  -H 'Content-Type: application/json' \
  -d '{"name":""}'
curl -s -o /dev/null -w "%{http_code}\n" 'http://127.0.0.1:8080/books?year=0'
```

Swagger UI: [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs)  
Альтернатива ReDoc: [http://127.0.0.1:8080/redoc](http://127.0.0.1:8080/redoc)

| ☐ | Проверка |
|---|----------|
| ☐ | Uvicorn слушает `127.0.0.1:8080` (не 8000) |
| ☐ | `GET /health` → `{"status":"ok"}` |
| ☐ | `GET /genres`, `/authors`, `/books` |
| ☐ | `GET /books?year=1972` / `?title=пикник` — сужают список |
| ☐ | `GET /books?year=1999` → `[]` и 200 |
| ☐ | `GET /books?year=0` → 422 |
| ☐ | `GET` по id, `POST` создания, `PATCH` частичного обновления |
| ☐ | Пустой `name` на POST → `422` с `detail` |
| ☐ | Нет строки → `404` с `{"error":"..."}` |
| ☐ | У книги в JSON `author` и `genre` — строки-имена |
| ☐ | `/docs` строится из типов, без YAML; у `GET /books` видны query |
| ☐ | `task_1_client` по-прежнему на aiohttp |
| ☐ | Роуты не импортируют `sqlalchemy.select` |
| ☐ | Общий SQL — в `BaseRepository`, фильтры — только в `BookRepository` |
| ☐ | Список в репозитории — `get_all`, не `list` |

---

## 3. Было / стало

| Тема | aiohttp | FastAPI |
|------|---------|---------|
| Старт процесса | `web.run_app` | Uvicorn + `lifespan` |
| Достать сессию | `request.app["session_factory"]` | `Depends(get_session)` |
| Достать SQL | прямо в handler | `Depends(get_*_repository)` → `BaseRepository` |
| Body | `body: dict` + `parse_body` | `payload: GenreCreate` / `GenreUpdate` |
| Query | `request.query.get` + ручной `int()` | `BookFilters` + `Depends()` |
| 404 | `web.json_response(..., status=404)` | `raise NotFoundError` + handler |
| Path-параметр | swagger3 инжектит `book_id` | `{book_id}` → аргумент функции |
| OpenAPI | docstring YAML + `aiohttp-swagger3` | типы и `response_model` |
| Обновление | не было | `PATCH` + `exclude_unset` |
| Тесты (идея) | подложить ключ в `app` | `app.dependency_overrides` |

Цепочка после шага 6:

```text
GET /books?title=пикник
  → BookFilters (query, не body)
  → get_session  (один раз на запрос)
  → BookRepository.get_all(filters)
        └── WHERE только для не-None
  → list[BookRead]  (пустой список — 200)
  → сессия закрывается
```

```text
PATCH /books/{id}
  → BookUpdate (только присланные поля)
  → get_session  (один раз на запрос)
  → AuthorRepository / GenreRepository / BookRepository
        └── BaseRepository.get / update
  → роут: 404 или BookRead
  → сессия закрывается
```

---

## 4. Типичные ошибки

| Симптом | Что проверить |
|---------|----------------|
| Uvicorn на порту 8000 | в `.env` `APP_PORT=8080`; запускайте `python -m app.main`, не голый `uvicorn app.main:app` без `--port` |
| `AttributeError: session_factory` | забыли `lifespan=` у `FastAPI(...)` или смотрите не тот экземпляр `app` |
| `/health` есть, `/genres` 404 | не вызвали `register_routes(app)` |
| 404 приходит как `{"detail":"..."}` | кидаете `HTTPException`, а не `NotFoundError` |
| Книга без имени автора | `selectinload` должен быть в `BookRepository.get` / `get_all` |
| `MissingGreenlet` / lazy load | читаете `book.author` без `selectinload` |
| PATCH затёр поля в `None` | нет `exclude_unset=True` |
| `TypeError: model is not a mapped class` | у потомка нет `model = Genre` |
| Три сессии на один POST книги | репозиторий создаёте вручную, минуя `Depends` |
| `GET /books?year=1972` отдаёт все книги | не добавили `WHERE` или передали фильтры в базу, а не в `BookRepository` |
| `BookFilters` без `?` даёт 422 | у полей нет `default=None` — FastAPI считает их обязательными |
| фильтры ждут JSON в body | забыли `Depends()` у `BookFilters`, FastAPI принял модель за тело |
| `ValidationError` на старте | `.env`: `APP_PORT` должен быть числом (это ещё `Settings`) |
| `alembic: No module named app` | команда не из корня репозитория |

---

## 5. Куда расти (не в этом уроке)

- `commit` после `yield` в `get_session` — одна транзакция на запрос.
- Пагинация (`limit` / `offset`) — тоже метод потомка, не универсальный движок в `BaseRepository`.
- Экранирование `%` / `_` в `ilike`, диапазон `year_from` / `year_to`.
- Сервисный слой, если правила сложнее, чем «404 если FK нет».
- `dependency_overrides[get_book_repository] = lambda: FakeBookRepo()` в pytest.

Карта проекта: [guide.md](guide.md) · первый гайд: [../guide.md](../guide.md)

**Дальше:** упаковать API и PostgreSQL в Docker — [../docker/README.md](../docker/README.md).
