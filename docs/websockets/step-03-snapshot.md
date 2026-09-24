# Шаг 3 — Один снимок статуса

**Предыдущий:** [step-02-progress.md](step-02-progress.md) · **Следующий:** [step-04-socket.md](step-04-socket.md)

## Задача

Собрать чтение Redis в одну функцию и отдать её из `GET /exports/{task_id}`. Пока экспорт идёт, в ответе уже есть растущий `book_count`. Сокет на следующем шаге вызовет ту же функцию, а не второй кусок работы с `AsyncResult`.

---

## Теория: что лежит в `result.info`

`AsyncResult` ходит в Redis по `task_id`.

| `status` | Что в `info` |
|----------|----------------|
| `PENDING` | пусто: ключа нет или задача ещё в очереди |
| `STARTED` | словарь Celery про процесс воркера, без наших книг |
| `PROGRESS` | meta из `update_state`: `{"book_count": ...}` |
| `SUCCESS` | то, что вернул `return`: `book_count` и `filename` |
| `FAILURE` | объект исключения, не словарь |

Старый `GET` смотрел `result.result` только если `successful()`. Поэтому `PROGRESS` для него был статусом без числа.

Общее правило: если `info` — словарь, забираем из него `book_count` и, когда ключ есть, `filename`. Если задача упала — в `error` кладём текст исключения. Чужой id остаётся `PENDING` без числа. Это не 404.

---

## 1. Функция в `app/routes/exports.py`

Рядом с роутером, выше хендлеров:

```python
def export_snapshot(task_id: str) -> ExportStatus:
    result = AsyncResult(task_id, app=celery_app)
    payload = ExportStatus(task_id=task_id, status=result.status)
    info = result.info

    if isinstance(info, dict):
        payload.book_count = info.get("book_count")
        payload.filename = info.get("filename")
    elif result.failed():
        payload.error = str(info)

    return payload
```

`get_export` становится тонким:

```python
@router.get(
    "/{task_id}",
    response_model=ExportStatus,
)
def get_export(task_id: str) -> ExportStatus:
    return export_snapshot(task_id)
```

`download_export` и `create_export` не меняйте.

### Разбор

`isinstance(info, dict)` отсекает и `None`, и исключение при `FAILURE`. У `STARTED` словарь есть, но ключа `book_count` в нём нет — `get` вернёт `None`, в JSON будет `"book_count": null`. Так и задумано: воркер ещё не закончил первую пачку.

`filename` в `PROGRESS` тоже `null`. Клиент качает файл только при `SUCCESS`, когда `return` уже записал имя.

Функция синхронная: клиент Redis в Celery синхронный. Из обычного `def get_export` это нормально. Из сокета на шаге 4 её нельзя звать прямо в event loop — там будет `asyncio.to_thread`.

---

## 2. Поймать середину

Воркер и `python -m app.main` запущены. Воркер перезапущен после шага 2.

```bash
curl -s -X POST http://127.0.0.1:8080/exports
```

Сразу и несколько раз, не дожидаясь конца:

```bash
curl -s http://127.0.0.1:8080/exports/ВСТАВЬТЕ_TASK_ID
```

Пока идёт выгрузка, ответ похож на:

```json
{"task_id": "...", "status": "PROGRESS", "book_count": 20000, "filename": null, "error": null}
```

Число от запроса к запросу растёт и не обязано совпасть с ровной тысячей в каждом `curl`: вы попадаете в момент между пачками. В конце:

```json
{"task_id": "...", "status": "SUCCESS", "book_count": 150000, "filename": "....json", "error": null}
```

`book_count` может быть на единицу больше 150 000, если в базе уже лежала лишняя тестовая книга до сида. Важен порядок: число растёт, затем статус становится `SUCCESS`, и только тогда есть `filename`.

---

## ✅ Проверка

| ☐ | Проверка |
|---|----------|
| ☐ | во время экспорта `GET` показывает `PROGRESS` и ненулевой `book_count` |
| ☐ | `filename` появляется вместе с `SUCCESS` |
| ☐ | после `SUCCESS` файл по-прежнему скачивается |
| ☐ | `POST /exports` по-прежнему `202` |
| ☐ | логика чтения Redis в одном `export_snapshot`, не скопирована во второй хендлер |
| ☐ | сокета ещё нет |
