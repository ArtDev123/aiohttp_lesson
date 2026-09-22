# Шаг 5 — Экспорт по тестовой базе

**Предыдущий:** [step-04-api.md](step-04-api.md) · **Следующий:** [step-06-final.md](step-06-final.md)

## Задача

Проверить `POST /exports` и скачивание файла так, чтобы задача **правда** прочитала книги из `library_test`. Redis и контейнер `worker` не поднимаем: Celery выполняет задачу в процессе pytest.

Если гайд Celery ещё не закрыт — этот шаг можно отложить. Шаги 1–4 от него не зависят.

---

## Теория: eager — очередь без брокера

`export_catalog.delay()` в обычной жизни кладёт сообщение в Redis. В тесте нам нужен SQL и файл, не сеть до брокера.

```python
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True
```

`delay()` тогда вызывает `export_catalog()` **здесь и сейчас**. Это тот же `def`, тот же `make_sync_engine()`, тот же `database_url_sync` — уже `library_test`.

```text
POST /exports
  → delay()  (eager)
  → sync SELECT books из library_test
  → JSON-файл
  → 202 + task_id
GET .../file
  → тот же файл
```

| | Прод / Compose | pytest |
|---|----------------|--------|
| Кто выполняет задачу | процесс `worker` | процесс `pytest` |
| Брокер | Redis | не используется |
| Откуда книги | `library_db` | `library_test` |
| Куда файл | `exports/` | временная папка теста |

`task_eager_propagates=True` — исключение из задачи всплывёт в хендлере (тест увидит 500), а не спрячется в `FAILURE` в Redis. Для урока так честнее: сломанный SELECT сразу красный.

`GET /exports/{id}` статуса через `AsyncResult` ходит в **backend** (Redis). В eager-режиме без Redis этот GET ненадёжен: нового сообщения в брокере нет. Поэтому в тесте проверяем то, что не зависит от Redis: код `202`, файл на диске, JSON совпадает с каталогом. Статус `PENDING`/`SUCCESS` оставляем ручному чеклисту Celery.

---

## Теория: файл не в `exports/` репозитория

Задача пишет `EXPORT_DIR / f"{task_id}.json"`. Роут читает тот же `EXPORT_DIR`. Если оставить папку проекта, pytest замусорит git и тесты начнут находить чужие файлы.

`tmp_path` — фикстура pytest, пустая директория на один тест. Патчим константу **в двух модулях**:

```python
# app/tasks.py              EXPORT_DIR = Path("exports")
# app/routes/exports.py     from app.tasks import EXPORT_DIR
```

Роут уже держит своё имя. Подмена только `app.tasks.EXPORT_DIR` его не перебьёт.

`monkeypatch` вернёт значения после теста сам.

---

## 1. Фикстуры в `tests/conftest.py`

Импорты добавьте к остальным.

```python
from pathlib import Path

from pytest import MonkeyPatch

from app.celery_app import celery_app


@pytest.fixture(scope="session", autouse=True)
def celery_eager() -> Generator[None, None, None]:
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


@pytest.fixture
def export_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    monkeypatch.setattr("app.tasks.EXPORT_DIR", tmp_path)
    monkeypatch.setattr("app.routes.exports.EXPORT_DIR", tmp_path)
    return tmp_path
```

`celery_eager` на всю сессию: все тесты экспорта (и случайный `POST /exports` из другого файла) идут в процессе. Выключать на один кейс не нужно.

Не ставьте `broker_url` в Redis обратно в конце — объект живёт в том же интерпретаторе, что и следующие команды. После `pytest` процесс умирает, `make worker` стартует заново и читает `.env`.

---

## 2. `tests/test_exports.py`

```python
from pathlib import Path

from fastapi.testclient import TestClient


def test_create_export_writes_catalog(
    client: TestClient,
    catalog: dict,
    export_dir: Path,
) -> None:
    response = client.post("/exports")
    assert response.status_code == 202
    task_id = response.json()["task_id"]
    assert task_id

    saved = export_dir / f"{task_id}.json"
    assert saved.is_file()

    books = saved.read_text(encoding="utf-8")
    assert "Пикник на обочине" in books
    assert "Стругацкие" in books


def test_download_export_file(
    client: TestClient,
    catalog: dict,
    export_dir: Path,
) -> None:
    task_id = client.post("/exports").json()["task_id"]
    response = client.get(f"/exports/{task_id}/file")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["title"] == "Пикник на обочине"


def test_download_export_missing_file(
    client: TestClient,
    export_dir: Path,
) -> None:
    response = client.get("/exports/no-such-task/file")
    assert response.status_code == 404
    assert "error" in response.json()


def test_export_empty_catalog(
    client: TestClient,
    export_dir: Path,
) -> None:
    task_id = client.post("/exports").json()["task_id"]
    payload = (export_dir / f"{task_id}.json").read_text(encoding="utf-8")
    assert payload.strip() == "[]"
```

`test_export_empty_catalog` **без** `catalog`: пустая база, файл `[]`. Ловит «задача всегда подмешивает сиды».

`test_download_export_file` бьёт в роут, не в диск напрямую: и запись, и `FileResponse`.

Кириллица в файле — тот же `ensure_ascii=False`, что на шаге 3 Celery. Если его снимете, `in books` по `\u041f...` может ещё пройти; надёжнее смотреть `response.json()["title"]`.

---

## Разбор: что доказали

```text
зелёный test_create_export_writes_catalog
    = SELECT в library_test вернул книгу из POST /books
    = JSON записался
    ≠ Redis принял сообщение
    ≠ контейнер worker жив
    ≠ compose-сеть сходится
```

Очередь как транспорт по-прежнему проверяйте `curl` + `docker compose logs worker`. Тест закрывает **полезную работу** задачи: чтение каталога и формат файла.

---

## ✅ Проверка

Redis и `celery worker` выключены.

```bash
source .venv/bin/activate
pytest tests/test_exports.py -vv
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | четыре теста экспорта | passed |
| ☐ | Redis не запущен | всё равно зелёные |
| ☐ | папка `exports/` в репозитории | новых uuid-файлов нет (писали в tmp) |
| ☐ | без `catalog` пустой экспорт | файл `[]` |
| ☐ | `library_db` | сиды на месте |

**Все пункты отмечены?** → [step-06-final.md](step-06-final.md)
