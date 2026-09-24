# Шаг 4 — Сокет прогресса

**Предыдущий:** [step-03-snapshot.md](step-03-snapshot.md) · **Следующий:** [step-05-final.md](step-05-final.md)

## Задача

Открыть `WS /exports/{task_id}/ws`. Сервер шлёт тот же снимок, что `GET`, пока статус не станет `SUCCESS` или `FAILURE`, и закрывает соединение. Файл по сокету не передаётся.

---

## Теория: цикл в процессе API

Воркер в этот сокет писать не может. Цикл живёт в Uvicorn:

```text
accept
  → снимок из Redis (в потоке, не в event loop)
  → если снимок новый — кадр клиенту
  → SUCCESS или FAILURE — close
  → иначе sleep и снова
```

`export_snapshot` синхронный и ходит в Redis. Прямой вызов внутри `async def` блокирует цикл: пока ждём Redis, этот воркер Uvicorn не отдаёт другие запросы и не пишет в сокет. `asyncio.to_thread` уносит вызов в поток и на время ожидания отпускает цикл.

Пауза `0.5` секунды — чтобы не долбить Redis вхолостую. Кадры из-за этого реже, чем пачки. `book_count` может перепрыгнуть с 8 000 на 15 000. Пропущенные тысячи в файле есть, просто снимок сняли не на каждой пачке.

Одинаковый снимок второй раз не шлём. Иначе клиент на длинном `PENDING` получает один и тот же JSON два раза в секунду.

Обрыв клиента — `WebSocketDisconnect`. Задачу Celery при этом **не** отменяем: файл дописывается, его заберёт другой `GET`. Сокет был только окошком.

---

## Теория: путь рядом с файлом

Префикс роутера уже `/exports`. Метод:

```text
WS /exports/{task_id}/ws
```

Это не `GET`. Браузерный адрес `http://.../ws` соединение не откроет. Схема URL — `ws://` (в Compose с TLS было бы `wss://`). Порт тот же, `8080`. Новый контейнер не нужен.

Порядок объявления относительно `GET /{task_id}/file` не важен: у сокета другой суффикс и другой протокол.

---

## 1. Хендлер в `app/routes/exports.py`

Импорты:

```python
import asyncio

from fastapi import APIRouter, WebSocket, status
from starlette.websockets import WebSocketDisconnect
```

`status` у вас уже импортирован для `202`. Добавьте остальное, не дублируйте строки.

Хендлер ниже `export_snapshot`:

```python
@router.websocket("/{task_id}/ws")
async def export_progress(task_id: str, websocket: WebSocket) -> None:
    await websocket.accept()
    previous: str | None = None
    try:
        while True:
            snapshot = await asyncio.to_thread(export_snapshot, task_id)
            text = snapshot.model_dump_json()
            if text != previous:
                await websocket.send_text(text)
                previous = text
            if snapshot.status in {"SUCCESS", "FAILURE"}:
                await websocket.close()
                return
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return
```

### Разбор

`accept()` обязателен до `send_text`. Без него клиент висит на рукопожатии.

`model_dump_json()` — тот же набор полей, что у `ExportStatus` в `GET`: `task_id`, `status`, `book_count`, `filename`, `error`.

`close()` после терминального статуса. Клиентская библиотека тогда заканчивает цикл чтения. Если закрыть сокет со стороны клиента раньше, `send_text` или `close` бросит `WebSocketDisconnect` — выходим тихо.

Не вызывайте `export_catalog` и `delay()` из сокета. Задачу создаёт только `POST`. Сокет, открытый до `POST`, сидит в `PENDING`, пока вы не поставите задачу с **этим** id. Удобный порядок: сначала `POST`, из ответа взять id, потом открыть сокет. К этому моменту статус уже может быть `STARTED` или первый `PROGRESS` — снимок это покажет первым кадром, история «с нуля» не досылается. Redis хранит последний meta, не ленту.

Перезапустите `python -m app.main`. Воркер трогать не нужно, если шаг 2 уже задеплоен. В Compose перезапустите сервис `app`.

---

## 2. Клиент

`scripts/watch_export.py` можно держать локально и не коммитить. Подставьте свой `task_id` после `POST` или передайте его аргументом.

```python
import asyncio
import sys

import websockets

task_id = sys.argv[1]
url = f"ws://127.0.0.1:8080/exports/{task_id}/ws"


async def main() -> None:
    async with websockets.connect(url) as ws:
        async for raw in ws:
            print(raw)


if __name__ == "__main__":
    asyncio.run(main())
```

Два терминала:

```bash
curl -s -X POST http://127.0.0.1:8080/exports
```

```bash
python scripts/watch_export.py ВСТАВЬТЕ_TASK_ID
```

Ожидание, числа другие, порядок такой:

```text
{"task_id": "...", "status": "STARTED", "book_count": null, "filename": null, "error": null}
{"task_id": "...", "status": "PROGRESS", "book_count": 3000, "filename": null, "error": null}
{"task_id": "...", "status": "PROGRESS", "book_count": 42000, "filename": null, "error": null}
{"task_id": "...", "status": "SUCCESS", "book_count": 150000, "filename": "....json", "error": null}
```

Скрипт сам заканчивается: сервер закрыл сокет. Дальше файл:

```bash
curl -s -o /tmp/catalog.json -w "%{http_code}\n" \
  http://127.0.0.1:8080/exports/ВСТАВЬТЕ_TASK_ID/file
```

`200`. Размер файла — мегабайты, не килобайты.

Повторный запуск скрипта с тем же id, когда задача уже `SUCCESS`, печатает один кадр и выходит. Так и должно быть: ленту прошлых `PROGRESS` Redis не помнит.

---

## ✅ Проверка

| ☐ | Проверка |
|---|----------|
| ☐ | скрипт печатает несколько `PROGRESS` с растущим `book_count` |
| ☐ | последний кадр — `SUCCESS`, в нём `filename` |
| ☐ | процесс скрипта завершился сам |
| ☐ | `GET .../file` после этого — `200` |
| ☐ | `GET /exports/{task_id}` совпадает с последним кадром |
| ☐ | оборванный клиент (Ctrl+C) не отменяет задачу: файл всё равно появляется |
| ☐ | в кадре нет массива книг |
