# Шаг 4 — CRUD книг через тестовую БД

**Предыдущий:** [step-03-fixtures.md](step-03-fixtures.md) · **Следующий:** [step-05-exports.md](step-05-exports.md)

## Задача

Прогнать список, чтение, создание, PATCH, 404 и 422 **настоящим SQL**. Данные тест создаёт сам через HTTP — отдельный `INSERT` в фикстуре не пишем.

---

## Теория: тест готовит мир через API

Можно в фикстуре открыть сессию и `session.add(Book(...))`. Тогда вы тестируете только `GET`, а `POST` остаётся без проверки.

Другой путь — тот же, что руками в Swagger:

```text
POST /genres  → id
POST /authors → id
POST /books   → книга с этими FK
GET  /books/1
```

Падает создание жанра — красный и список книг. Это плюс: один сломанный роут не маскируется «правильным» SQL в фикстуре.

Книга требует существующие `author_id` и `genre_id`. Репозиторий кинет `NotFoundError`, если FK нет. Фикстура `catalog` сначала создаёт жанр и автора, потом книгу — иначе каждый тест копирует три `POST`.

После теста `TRUNCATE` + `RESTART IDENTITY`: следующий `catalog` снова получит `id=1`. На номера из сидовой базы не ориентируйтесь.

---

## 1. Фикстура каталога в `tests/conftest.py`

В конец файла:

```python
from typing import Any


@pytest.fixture
def catalog(client: TestClient) -> dict[str, Any]:
    genre = client.post("/genres", json={"name": "фантастика"}).json()
    author = client.post(
        "/authors",
        json={"name": "Стругацкие", "bio": "Писатели"},
    ).json()
    book = client.post(
        "/books",
        json={
            "title": "Пикник на обочине",
            "year": 1972,
            "author_id": author["id"],
            "genre_id": genre["id"],
        },
    ).json()
    return {"genre": genre, "author": author, "book": book}
```

### Разбор

`catalog` просит `client` — pytest сначала даст клиент, потом каталог. `clean_tables` сработает после теста, не между `client` и `catalog`: оба живут внутри одного кейса.

Три `.json()` без проверки статуса. Если `POST /genres` вернул 500, упадёте на `POST /books` с кривым id — ищите в `-vv` какой вызов первый красный. Можно добавить `assert response.status_code == 201` в фикстуру, если хочется сразу явный fail.

Имена как в сидах, но это **не** вызов `app.seed`. Строки появятся только в `library_test`.

---

## 2. `tests/test_books.py`

```python
from fastapi.testclient import TestClient


def test_list_books_empty(client: TestClient) -> None:
    response = client.get("/books")
    assert response.status_code == 200
    assert response.json() == []


def test_list_books(client: TestClient, catalog: dict) -> None:
    response = client.get("/books")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["title"] == "Пикник на обочине"
    assert payload[0]["author"] == "Стругацкие"
    assert payload[0]["genre"] == "фантастика"


def test_get_book(client: TestClient, catalog: dict) -> None:
    book_id = catalog["book"]["id"]
    response = client.get(f"/books/{book_id}")
    assert response.status_code == 200
    assert response.json()["id"] == book_id


def test_get_book_missing(client: TestClient) -> None:
    response = client.get("/books/999")
    assert response.status_code == 404
    assert "error" in response.json()


def test_create_book_unknown_author(client: TestClient, catalog: dict) -> None:
    response = client.post(
        "/books",
        json={
            "title": "Нет такого автора",
            "year": 1970,
            "author_id": 999,
            "genre_id": catalog["genre"]["id"],
        },
    )
    assert response.status_code == 404


def test_patch_book_year(client: TestClient, catalog: dict) -> None:
    book_id = catalog["book"]["id"]
    response = client.patch(f"/books/{book_id}", json={"year": 1973})
    assert response.status_code == 200
    body = response.json()
    assert body["year"] == 1973
    assert body["title"] == "Пикник на обочине"


def test_create_genre_empty_name_is_422(client: TestClient) -> None:
    response = client.post("/genres", json={"name": ""})
    assert response.status_code == 422
    assert "detail" in response.json()
```

`test_list_books_empty` **не** просит `catalog`. База после TRUNCATE пустая — ловите регрессию «всегда отдаём сиды из памяти».

`test_create_book_unknown_author` бьёт в проверку FK внутри `BookRepository`. Фейк-репозиторий из черновика этого бы не поймал.

`422` — Pydantic, до SQL. База всё равно должна быть доступна: зависимость сессии откроется. Пустой `name` не оставит грязную строку.

Текст 404 (`"Book not found"` / `"Автор не найден"`) возьмите из своего репозитория, если хотите жёсткий `assert response.json() == ...`. В гайде проверяем код и ключ `error` — так меньше боли при другой формулировке.

---

## Разбор кейсов

| Тест | Что ловит в БД |
|------|----------------|
| пустой список | `get_all` без строк → `[]` и 200, не 404 |
| список с каталогом | `selectinload`: в JSON имена, не только id |
| get по id | path доходит до `WHERE id =` |
| 999 | нет строки → `NotFoundError` → `{"error":...}` |
| чужой author_id | FK-проверка репозитория, не Postgres `IntegrityError` |
| PATCH year | `exclude_unset`: title на месте, в таблице новое year |
| пустой name | 422, `TRUNCATE` не обязателен, но сработает |

Порядок тестов не гарантирован. Изоляция — только `TRUNCATE`, не надейтесь, что `empty` идёт первым.

---

## Разбор: заглянуть в базу

После красного теста таблицы уже пустые (чистка в `finally` фикстуры). Чтобы поймать момент:

```bash
pytest tests/test_books.py::test_list_books -vv --pdb
```

На `pdb` чистка ещё не выполнилась. Другой терминал:

```bash
docker exec library-test-db \
  psql -U library_user -d library_test \
  -c "SELECT id, title FROM books;"
```

Должны увидеть «Пикник». В `library_db` этой строки, созданной тестом, нет.

---

## ✅ Проверка

```bash
source .venv/bin/activate
pytest tests/test_books.py tests/test_health.py -vv
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | все тесты книг + health | passed |
| ☐ | сломать `selectinload` в репозитории | `list_books` красный (`author` / lazy load) |
| ☐ | дважды подряд `pytest tests/test_books.py` | оба раза зелёные, id снова с 1 |
| ☐ | `SELECT count(*) FROM books` в `library_db` | сиды, не ноль и не «накопились тесты» |
| ☐ | `SELECT count(*) FROM books` в `library_test` после прогона | `0` |

**Все пункты отмечены?** → [step-05-exports.md](step-05-exports.md)
