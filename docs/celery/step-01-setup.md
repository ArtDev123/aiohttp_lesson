# Шаг 1 — Пакеты, Redis и `REDIS_URL`

**Предыдущий:** [README.md](README.md) · **Следующий:** [step-02-app.md](step-02-app.md)

## Задача

Поставить Celery и клиент Redis, запустить брокер, добавить `REDIS_URL` в настройки. Задач и роутов ещё нет — на этом шаге только инфраструктура, без которой `delay()` на шаге 2 некуда отправить.

---

## Теория: почему не в запросе

Хендлер FastAPI живёт, пока не вернул ответ. Всё, что вы пишете в `async def create_export`, занимает воркер Uvicorn.

```text
один воркер Uvicorn

запрос A: GET /health      — 1 мс
запрос B: POST /exports    — 5 секунд SELECT + файл
запрос C: GET /books       — ждёт, пока B закончит
```

Uvicorn умеет крутить много корутин на одном потоке. Но **синхронная** запись большого файла или долгий CPU всё равно стопорит цикл. Даже честный `async` SELECT всех книг держит соединение и память, а клиент смотрит на крутилку.

Очередь меняет контракт:

| | В запросе | Через очередь |
|---|-----------|----------------|
| Ответ клиенту | «вот файл» | «вот номер заказа» |
| Кто пишет файл | процесс API | отдельный воркер |
| Если воркер упал | запрос 500 | задачу можно повторить |
| Масштаб | больше Uvicorn | больше воркеров Celery |

Для трёх сидовых книг разницы не видно. Паттерн нужен, когда работа *может* стать тяжёлой: выгрузка, письмо, импорт, картинки. В уроке работа маленькая — зато цепочка настоящая.

---

## Теория: брокер

**Брокер** — место, куда кладут сообщения «выполни вот эту функцию с вот такими аргументами».

```text
app.delay()  →  [сообщение]  →  Redis list / stream
                                      │
                                      ▼
                               worker забирает
```

Без брокера API и воркер не знают друг о друге: это разные процессы, у них разная память. Нельзя «вызвать функцию в другом процессе» просто импортом — нужен канал.

Почему Redis, а не Postgres:

| | Redis | Postgres как брокер |
|---|---------|---------------------|
| Для чего создан | очереди, ключ-значение, TTL | таблицы |
| Задержка | миллисекунды | выше |
| В уроке | один контейнер `redis:7` | уже занят данными библиотеки |

Celery умеет и RabbitMQ. Redis проще: один образ, один URL, его же используем как **result backend** — сюда воркер кладёт статус и маленький JSON результата (`book_count`, имя файла). Сам каталог кладём **в файл**, не в Redis: брокер не файловое хранилище.

`REDIS_URL` выглядит как Postgres URL, только протокол другой:

```text
redis://localhost:6379/0
        │         │    └── номер логической БД Redis (0…15)
        │         └── порт
        └── хост (в Docker будет имя сервиса redis)
```

Пароля в учебном Redis нет. Если появится: `redis://:пароль@host:6379/0`.

Та же ловушка, что с Postgres в Docker: внутри контейнера `localhost` — сам контейнер. На шаге 5 переопределим на `redis://redis:6379/0`. Сейчас — локальный запуск, `localhost`.

---

## 1. Redis на машине

Docker у вас уже есть. Отдельный `apt install redis` не нужен:

```bash
docker run --rm -p 6379:6379 --name library-redis redis:7-alpine
```

Оставьте терминал открытым. `--rm` удалит контейнер после Ctrl+C. Порт `6379` — дефолт Redis, с хоста `localhost:6379`.

Проверка в другом терминале:

```bash
docker exec library-redis redis-cli ping
```

Должно напечатать `PONG`.

Если `6379` занят — либо у вас уже крутится Redis (тогда новый контейнер не нужен), либо смените левую часть: `-p 6380:6379` и в `.env` будет `redis://localhost:6380/0`.

---

## 2. Дописать `requirements.txt`

В конец файла:

```text
celery[redis]>=5.4
redis>=5.0
```

`celery[redis]` ставит сам Celery и зависимость, чтобы говорить с Redis. Пакет `redis` — официальный клиент; его явно фиксируем, чтобы импорт `redis` не сюрпризил.

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Windows: `.\.venv\Scripts\Activate.ps1`, затем та же команда `pip`.

`psycopg2-binary` уже стоит — его не добавляем. Им пользуется Alembic и на шаге 3 — задача экспорта.

---

## 3. `.env` и `.env.example`

В оба файла добавьте строку:

```text
REDIS_URL=redis://localhost:6379/0
```

Локальный `make run` и воркер на хосте читают этот URL. Compose на шаге 5 перебьёт его через `environment`, как `POSTGRES_HOST`.

---

## 4. `app/config.py`

В класс `Settings` добавьте поле. Остальные ключи не трогайте.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_db: str = "library_db"
    postgres_user: str = "library_user"
    postgres_password: str = "library_pass"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    app_host: str = "127.0.0.1"
    app_port: int = 8080
    redis_url: str = "redis://localhost:6379/0"

    @property
    def database_url(self) -> str:
        ...

    @property
    def database_url_sync(self) -> str:
        ...
```

`pydantic-settings` сам сопоставит `REDIS_URL` → `redis_url`. Дефолт в коде совпадает с `.env.example`: если файла нет, `ping` всё равно целится в локальный Redis.

---

## Разбор пакетов

| Пакет | Зачем |
|-------|--------|
| `celery` | приложение, декоратор `@task`, команда `celery worker` |
| extra `[redis]` | транспорт брокера и backend результата |
| `redis` | клиент; Celery ходит через него |
| `psycopg2-binary` | уже был; sync-доступ из воркера |
| `asyncpg` | только FastAPI, как раньше |

Celery **не** ASGI и не замена Uvicorn. Это отдельная программа. FastAPI его не «включает» сам — воркер запускаете вы.

---

## ✅ Проверка

```bash
source .venv/bin/activate
python -c "import celery, redis; print(celery.__version__, redis.__version__)"
python -c "from app.config import settings; print(settings.redis_url)"
docker exec library-redis redis-cli ping
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | `pip install -r requirements.txt` | без ошибок, в выводе есть `celery` и `redis` |
| ☐ | импорт celery / redis | две версии, не `ModuleNotFoundError` |
| ☐ | `settings.redis_url` | `redis://localhost:6379/0` |
| ☐ | `redis-cli ping` | `PONG` |
| ☐ | `python -m app.main` | API как раньше, экспортных роутов **ещё нет** |

Контейнер Redis не останавливайте — он нужен на шаге 2.

**Все пункты отмечены?** → [step-02-app.md](step-02-app.md)
