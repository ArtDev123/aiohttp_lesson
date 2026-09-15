# aiohttp: клиент и мини-библиотека

Две задачи урока:

1. **Клиент** — `ClientSession`, параллельные запросы, таймауты.
2. **Сервер** — маленькое API библиотеки на aiohttp + SQLAlchemy + Alembic + Swagger.

## Запуск

```bash
make setup    # venv, зависимости, миграции, сиды
make run      # сервер на http://127.0.0.1:8080
```

Swagger UI: [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs)

Клиент (jsonplaceholder, сервер не нужен):

```bash
make client
```

## Модели

- `Genre` — жанр книги
- `Author` — автор
- `Book` — книга, ссылается на автора и жанр

SQLite-файл: `library.db` (в git не попадает).
