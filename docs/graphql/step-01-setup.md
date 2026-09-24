# Шаг 1 — Пакет Strawberry

**Предыдущий:** [README.md](README.md) · **Следующий:** [step-02-types.md](step-02-types.md)

## Задача

Поставить библиотеку, которая из Python-типов собирает схему GraphQL и умеет сесть роутом на FastAPI. Типов и URL ещё нет — без пакета на шаге 2 нечего импортировать.

---

## Теория: один URL и текст запроса

У REST много адресов: `/books`, `/books/1`, `/authors/1`. У GraphQL адрес один. Что читать, написано в теле:

```json
{
  "query": "{ books { title author { name } genre { name } } }"
}
```

Слово `query` здесь — имя операции «прочитать». Есть ещё `mutation` (изменить) и `subscription` (поток). В этом гайде только чтение.

Текст внутри — не JSON и не SQL. Это язык GraphQL:

```graphql
{
  books {
    title
    author { name }
    genre { name }
  }
}
```

Фигурные скобки — дерево полей. Сервер имеет право отдать только то, что есть в **схеме**. Поле `books.isbn`, которого мы не объявили, — ошибка запроса, даже если в Postgres такая колонка есть.

Схему можно писать отдельным файлом `.graphql` (SDL). Strawberry делает иначе, ближе к FastAPI: вы описываете типы в Python, библиотека сама публикует SDL. Как Pydantic-модель становится куском OpenAPI, так `@strawberry.type` становится куском схемы.

---

## Теория: почему не «ещё один GET»

Вложить автора объектом можно и в REST: поменять `BookRead.author` со `str` на вложенную модель. Тогда **каждый** клиент `GET /books` получит `bio`, даже главная страница, которой нужно одно название.

GraphQL режет ответ по запросу клиента. Поле `bio` считается, только если оно есть в тексте. Для каталога из трёх сидов разницы в миллисекундах нет. Разница в контракте: форма ответа — часть запроса, а не навсегда зашитый `response_model`.

---

## 1. Дописать `requirements.txt`

В конец файла:

```text
strawberry-graphql[fastapi]>=0.270
```

Скобки `[fastapi]` ставят интеграцию с FastAPI (`GraphQLRouter`). Без них есть ядро GraphQL, но нет роута.

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Windows: `.\.venv\Scripts\Activate.ps1`, затем та же команда `pip`.

Проверка импорта:

```bash
python -c "import strawberry; from strawberry.fastapi import GraphQLRouter; print(strawberry.__version__)"
```

Печатается версия, без `ImportError`.

---

## 2. Что не трогаем на этом шаге

| Оставить | Не создавать заранее |
|----------|----------------------|
| `app/models.py`, `alembic/` | `app/graphql/` (шаг 2: папка на ресурс, не один `types.py`) |
| `app/schemas.py`, `app/routes/books.py` | роут в `register_routes` (шаг 4) |
| `app/repositories/books.py` | мутации, логин, DataLoader |

`selectinload` в репозитории книг уже есть. Его хватит, чтобы на шаге 3 отдать автора и жанр без запроса «на каждую книгу».

---

## Разбор пакета

| Пакет | Зачем |
|-------|--------|
| `strawberry-graphql` | типы, схема, разбор текста запроса |
| extra `fastapi` | `GraphQLRouter` — тот же `APIRouter`, плюс GraphiQL |
| `graphql-core` | ставится зависимостью, руками не пишем |

Pydantic и SQLAlchemy остаются для REST и таблиц. Strawberry их не заменяет: это третий слой, только для `/graphql`.

---

## ✅ Проверка

| ☐ | Проверка |
|---|----------|
| ☐ | `pip install -r requirements.txt` без ошибки |
| ☐ | `import strawberry` и `GraphQLRouter` импортируются |
| ☐ | `python -m app.main` по-прежнему поднимает REST (`GET /health` → `{"status":"ok"}`) |
| ☐ | папки `app/graphql/` ещё нет |

REST не должен измениться: пакет сам по себе ни одного URL не добавляет.
