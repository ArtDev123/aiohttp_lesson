# Шаг 2 — Приложение и Postgres в Compose

**Предыдущий:** [step-01-install.md](step-01-install.md) · **К карте:** [README.md](README.md)

## Задача

Собрать образ нашего API и поднять **два контейнера**: PostgreSQL и приложение. С хоста по-прежнему `http://127.0.0.1:8080`, но Python и Postgres живут внутри Docker.

Локальный `.venv` для этого шага не нужен. Файл `.env` нужен — Compose читает его с хоста.

---

## Теория: два контейнера и сеть

Один контейнер — один процесс (лучше так и держать). API и Postgres — **два** контейнера. Compose поднимает их вместе и вешает на одну виртуальную сеть: контейнеры видят друг друга **по имени сервиса**.

```text
хост (браузер, curl, DBeaver)
        │
        │  localhost:8080          localhost:5433
        ▼                          ▼
   ┌─────────┐                 ┌─────────┐
   │   app   │  db:5432        │   db    │
   │ FastAPI │ ───────────────►│ Postgres│
   └─────────┘   сеть compose  └─────────┘
```

С хоста Docker-Postgres смотрим на **5433**, чтобы не задеть локальный Postgres с [шага 1](../remaining/step-01-env.md) (там 5432). Внутри сети Compose Postgres по-прежнему слушает 5432 — контейнер `app` ходит на `db:5432`.

Имя хоста `db` — не магия DNS интернета, а имя сервиса в YAML. Его же пишем в `POSTGRES_HOST`.

---

## Теория: `localhost` и `0.0.0.0`

Это две самые частые ошибки при переносе в Docker.

**1. Куда смотрит приложение за Postgres**

В `.env` у нас `POSTGRES_HOST=localhost`. С вашей машины это правильно: Postgres на этом же ноутбуке.

Внутри контейнера `localhost` — **сам контейнер**, не ноутбук и не соседний `db`.

```text
python -m app.main на хосте     →  localhost:5432  = Postgres на ноутбуке
тот же код в контейнере app     →  localhost:5432  = пусто (Postgres в другом контейнере)
код в контейнере app            →  db:5432         = сервис db
```

Поэтому в Compose **переопределяем** `POSTGRES_HOST=db`. `pydantic-settings` читает переменные окружения **позже**, чем `.env` — значение из Compose победит файл.

**2. На каком адресе слушает Uvicorn**

`APP_HOST=127.0.0.1` — процесс принимает соединения только с loopback. Внутри контейнера loopback не тот, куда Docker пробрасывает `-p 8080:8080`. С хоста получите «connection refused».

Нужно `APP_HOST=0.0.0.0`: слушать все интерфейсы контейнера. Проброс порта тогда доходит до Uvicorn.

`.env` для локального `make run` можно не трогать: переопределение только в Compose.

---

## Теория: слои образа

Каждая инструкция Dockerfile — слой. Слои кэшируются сверху вниз. Меняете `app/main.py` — пересобирается хвост, `pip install` **не** гоняется заново, если `requirements.txt` тот же.

Поэтому сначала копируем только зависимости, потом код:

```text
FROM python:3.12-slim     слой 1  (редко меняется)
COPY requirements.txt     слой 2
RUN pip install ...       слой 3  (тяжёлый)
COPY app ./app            слой 4  (часто)
```

`.dockerignore` выкидывает `.venv`, `docs`, `.git` из контекста сборки: иначе огромный venv уедет в образ или сломает кэш.

---

## Теория: инструкции Dockerfile

Dockerfile читается **сверху вниз**. Часть инструкций меняет файлы в образе (`COPY`, `RUN`), часть — только настройки процесса (`ENV`, `EXPOSE`, `ENTRYPOINT`).

| Инструкция | Когда | Что делает |
|------------|-------|------------|
| `FROM` | сборка | стартовый образ, с которого начинаем |
| `WORKDIR` | сборка | «текущая папка» внутри образа (`cd` + `mkdir`) |
| `ENV` | сборка и запуск | переменные окружения |
| `COPY` | сборка | файлы с вашей машины → в образ |
| `RUN` | сборка | команда в образе (`pip`, `chmod`) |
| `EXPOSE` | метаданные | пометка «процесс слушает этот порт» |
| `ENTRYPOINT` | **запуск** | что выполнить, когда контейнер стартует |
| `CMD` | **запуск** | аргументы к `ENTRYPOINT` или команда по умолчанию |

`FROM` обязан быть первым (кроме редкого `ARG` перед ним). Без базового образа не из чего собирать.

**`FROM python:3.12-slim`** — не «поставь Python на ноутбук», а «возьми готовый Linux-снимок, где уже есть интерпретатор 3.12». Имя до двоеточия — репозиторий на Docker Hub, после — тег. `slim` = Debian без компиляторов, man-страниц и лишних пакетов. Полный `python:3.12` тяжелее на сотни мегабайт; `gcc` нам не нужен: `asyncpg` и `psycopg2-binary` ставятся готовыми колёсами.

**`WORKDIR /app`** — все относительные пути дальше считаются от `/app`. Эквивалент `mkdir -p /app && cd /app`. Поэтому `COPY requirements.txt .` кладёт файл в `/app/requirements.txt`, а `python -m app.main` ищет пакет в `/app/app/`.

**`ENV KEY=value`** — переменная попадает и в `RUN` на сборке, и в процесс контейнера. Несколько значений в одном `ENV` (через `\`) — один слой, не пять.

**`COPY источник назначение`** — только файлы из **контекста сборки** (обычно папка, где лежит Dockerfile). Точка `.` справа = текущий `WORKDIR`. `COPY` не скачивает из интернета и не распаковывает архивы — для этого был бы `ADD`; в уроке везде `COPY`, он предсказуемее.

**`RUN команда`** — выполняется один раз при `docker build`, результат замораживается в слое. `RUN pip install` **не** повторяется на каждый `compose up`, пока слой в кэше.

**`EXPOSE 8080`** порт на хост **не** открывает. Это комментарий для человека и для `docker run -P`. Реальный проброс — поле `ports` в Compose.

**`ENTRYPOINT` vs `CMD`:**

```text
ENTRYPOINT = программа     (у нас скрипт)
CMD        = её аргументы  (мы не задаём)
```

Две записи одной инструкции:

| Форма | Пример | Кто PID 1 |
|-------|--------|-----------|
| exec (JSON-массив) | `ENTRYPOINT ["/docker-entrypoint.sh"]` | сам скрипт |
| shell | `ENTRYPOINT /docker-entrypoint.sh` | `/bin/sh -c "..."` |

Нужна exec-форма: `docker compose stop` шлёт SIGTERM процессу с PID 1. Если PID 1 — оболочка, сигнал может не дойти до Uvicorn. Внутри скрипта поэтому ещё и `exec python -m app.main` — shell заменяется сервером.

`CMD` мы не пишем: entrypoint сам вызывает Alembic, сиды и Uvicorn. Строка `command:` в Compose подменила бы `CMD`, не `ENTRYPOINT`.

---

## Теория: поля Compose

`docker-compose.yml` — не рецепт образа, а **описание нескольких контейнеров и связей**. Dockerfile отвечает на «как собрать app». Compose — на «что запустить вместе».

```text
docker-compose.yml
├── services          ← контейнеры проекта
│   ├── db            ← имя = DNS-имя в сети
│   └── app
└── volumes
    └── pgdata        ← именованный диск
```

Ключа `version: "3.9"` нет — это старый формат. Движок сам понимает схему.

### `services`

Словарь. Ключ (`db`, `app`) становится именем хоста: из контейнера `app` Postgres доступен как `db`, не как `localhost`.

Два способа получить образ:

| Поле | Смысл | Кто у нас |
|------|--------|-----------|
| `image: postgres:16` | скачать готовый с Docker Hub | `db` |
| `build: .` | собрать из Dockerfile | `app` |

Точка в `build: .` — **контекст**: какие файлы демон видит при `COPY`. Обрезает `.dockerignore`. Имя получившегося образа Compose берёт из папки проекта: `aiohttp_lesson-app`.

### `environment` и `env_file`

Оба кладут переменные **внутрь контейнера**. Не путать с подстановкой в самом YAML.

```yaml
POSTGRES_DB: ${POSTGRES_DB:-library_db}
```

`${ИМЯ:-дефолт}` считает Compose **на хосте**, когда читает файл: сначала оболочка / корневой `.env`, если пусто — `library_db`. В контейнер уже уходит готовая строка. Это не bash внутри Postgres.

Официальный образ Postgres при **первом** старте пустого тома читает `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` и сам создаёт роль и базу. Скрипты `scripts/init_postgres*` здесь не нужны.

`env_file: .env` — прочитать файл и сделать каждую строку переменной процесса. Файл в образ **не копируется**. Нужен `app`: `pydantic-settings` ждёт те же имена, что в локальном запуске.

Если ключ есть и в `env_file`, и в `environment`, побеждает **`environment`**. Поэтому `.env` с `POSTGRES_HOST=localhost` можно не трогать: Compose перебьёт на `db`.

### `ports`

Строка `ХОСТ:КОНТЕЙНЕР`. Слева слушает ваш ноутбук, справа — процесс в контейнере.

```text
"5433:5432"
   │     └── Postgres внутри db (всегда 5432)
   └── порт на Windows/Mac/Linux, чтобы DBeaver не задел локальный 5432
```

Без `ports` сервис всё равно виден **соседям по сети Compose**. `app` ходит на `db:5432` и без проброса. `ports` нужен, только чтобы достучаться **с хоста**.

### `volumes`

Данные в контейнере живут, пока жив контейнер. `docker compose down` контейнер удаляет — файлы Postgres пропали бы. Том — диск **рядом** с контейнером.

```yaml
volumes:
  - pgdata:/var/lib/postgresql/data
```

Слева — имя тома, справа — путь **внутри** контейнера (туда пишет PostgreSQL). Это **именованный** том, не папка проекта.

| Вид | Запись | Когда |
|-----|--------|--------|
| named volume | `pgdata:/var/lib/postgresql/data` | данные БД, не смешивать с git |
| bind mount | `.:/app` | подставить код с диска (hot-reload), в этом уроке нет |

В корне файла ещё раз `volumes: pgdata:` — объявить том. Без объявления Compose создаст его молча; явное имя проще искать в `docker volume ls`.

`down` том **не** трогает. Снести БД: `docker compose down -v`.

### `healthcheck`

Контейнер «запущен» ≠ процесс внутри готов принимать TCP. Healthcheck периодически гоняет команду; код 0 = healthy.

| Поле | Смысл |
|------|--------|
| `test` | что выполнить |
| `interval` | как часто |
| `timeout` | сколько ждать один прогон |
| `retries` | сколько неудач подряд → unhealthy |

`["CMD-SHELL", "pg_isready ..."]` — запуск через `sh -c` (удобно для одной строки). `["CMD", "pg_isready", ...]` — без оболочки, аргументы списком.

### `depends_on`

Контейнер Postgres **стартовал** ≠ демон внутри готов. Alembic в этот момент поймает `connection refused`.

```yaml
depends_on:
  db:
    condition: service_healthy
```

Compose ждёт healthcheck и только потом запускает `app`. Обычный `depends_on: [db]` этого не делает — только порядок `docker start`.

### Чего нет в нашем YAML — и это нормально

| Поле | Почему не пишем |
|------|-----------------|
| `network` | Compose сам создаёт `{проект}_default` и кладёт туда все сервисы |
| `container_name` | сам назовёт `aiohttp_lesson-app-1`; фиксированное имя мешает поднять два проекта сразу |
| `command` | возьмётся `ENTRYPOINT` из Dockerfile |
| `restart` | учебный запуск, не демон на сервере |

---

## 1. `.dockerignore`

В корне репозитория:

```text
.git
.gitignore
.venv
venv
env
__pycache__
*.py[cod]
.pytest_cache
.mypy_cache
.ruff_cache
.idea
.vscode
.DS_Store

.env
.env.*
!.env.example

docs
*.md
task_1_client
scripts
docker-compose.yml
```

`.env` в образ не копируем: секреты передаёт Compose. `task_1_client` и `docs` серверу в контейнере не нужны.

Контекст сборки — папка, которую демон видит при `COPY`. `.dockerignore` режет её **до** отправки. Без него в билд уедут `.venv` (сотни МБ) и `.git`. `!.env.example` — исключение из исключения: шаблон можно было бы копировать, мы его всё равно не копируем, строка на будущее.

---

## 2. `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8080

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/docker-entrypoint.sh"]
```

### Разбор строк

**`FROM python:3.12-slim`** — база. В образе уже Linux + Python 3.12. Тег `slim` отрезает лишнее; для `pip install` колёс этого хватает.

**`WORKDIR /app`** — дальше «текущая директория» = `/app`. `COPY app ./app` даст `/app/app/main.py`. `python -m app.main` и Alembic (`prepend_sys_path = .`) работают так же, как с хоста из корня репозитория.

**`ENV PYTHONDONTWRITEBYTECODE=1`** — не писать `.pyc`. В контейнере они только занимают слой.

**`ENV PYTHONUNBUFFERED=1`** — `print` и логи Uvicorn сразу в stdout. Иначе `docker compose logs` может молчать, пока не наберётся буфер.

**`ENV PIP_NO_CACHE_DIR=1`** — pip не складывает скачанные wheels в `/root/.cache`. Слой `RUN pip` меньше.

**`ENV APP_HOST=0.0.0.0` / `APP_PORT=8080`** — дефолты внутри образа. Compose всё равно переопределит тем же, но контейнер не окажется на `127.0.0.1`, если YAML забудут.

Обратный слэш в `ENV` — продолжение одной инструкции (один слой), не пять отдельных `ENV`.

**`COPY requirements.txt .`** — один файл, `/app/requirements.txt`. Не `COPY . .`: любое изменение `.py` сбросило бы кэш и заставило бы `pip install` гоняться заново.

**`RUN pip install -r requirements.txt`** — пакеты вшиваются в образ на **сборке**. Пока `requirements.txt` не менялся, Docker берёт этот слой из кэша.

**`COPY alembic.ini .`** — конфиг Alembic (`script_location`, `prepend_sys_path`). Без него `alembic upgrade` в entrypoint не стартует.

**`COPY alembic ./alembic`** — папка ревизий, в том числе `versions/0001_initial_tables.py`.

**`COPY app ./app`** — код API. `task_1_client` и `docs` специально не копируем (их отсёк `.dockerignore` и мы их не перечисляем).

**`COPY docker-entrypoint.sh /docker-entrypoint.sh`** — скрипт в корень файловой системы образа, абсолютный путь. Так его не спутаешь с пакетом `app`.

**`RUN chmod +x /docker-entrypoint.sh`** — бит исполнения. На Windows Git часто выкладывает файл без `+x`; в образе чиним сами.

**`EXPOSE 8080`** — пометка. Проброс на ноутбук делает Compose: `"8080:8080"`.

**`ENTRYPOINT ["/docker-entrypoint.sh"]`** — exec-форма (JSON-массив). При старте контейнера PID 1 = этот скрипт, не `sh -c`. `CMD` нет: скрипт сам вызывает миграции, сиды и Uvicorn.

---

## 3. `docker-entrypoint.sh`

Скрипт, который контейнер запускает **вместо** «голой» команды. Сначала схема БД и сиды, потом сервер.

```sh
#!/bin/sh
set -e

echo ">>> alembic upgrade head"
alembic upgrade head

echo ">>> python -m app.seed"
python -m app.seed

echo ">>> python -m app.main"
exec python -m app.main
```

### Разбор строк

`#!/bin/sh` — shebang: ядро запускает файл через `/bin/sh` образа (в `slim` это `dash` или `sh`, не bash). Пишем POSIX, без `[[` и массивов bash.

`set -e` — первая команда с ненулевым кодом завершает скрипт. Не поднимаем Uvicorn, если миграция упала.

`alembic upgrade head` — привести схему к последней ревизии. Ходит в Postgres по `database_url_sync` из `Settings` (уже с `POSTGRES_HOST=db`).

`python -m app.seed` — идемпотентно: если жанры есть, скрипт выходит. Повторный `compose up` не плодит строки.

`exec python -m app.main` — `exec` **заменяет** оболочку процессом Uvicorn. Без `exec` PID 1 остался бы `sh`, а сервер — потомком; `docker compose stop` послал бы SIGTERM шеллу.

Файл должен быть с переводами строк **LF**, не CRLF. Иначе Linux внутри образа скажет `exec user process caused: no such file or directory`. В корне репозитория есть `.gitattributes` (`docker-entrypoint.sh text eol=lf`). После создания:

```bash
chmod +x docker-entrypoint.sh
```

Windows: если Git всё же выдал CRLF — в редакторе переключите ending на LF.

---

## 4. `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-library_db}
      POSTGRES_USER: ${POSTGRES_USER:-library_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-library_pass}
    ports:
      - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-library_user} -d ${POSTGRES_DB:-library_db}"]
      interval: 3s
      timeout: 3s
      retries: 10

  app:
    build: .
    ports:
      - "8080:8080"
    env_file:
      - .env
    environment:
      POSTGRES_HOST: db
      POSTGRES_PORT: 5432
      APP_HOST: 0.0.0.0
      APP_PORT: 8080
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```

### Разбор полей

**`services:`** — список контейнеров. Имена `db` и `app` — не подписи для человека, а DNS: приложение подключается к хосту `db`.

**`db.image: postgres:16`** — готовый образ с Hub. `16` — мажор PostgreSQL, не имя контейнера. Dockerfile для БД не пишем.

**`db.environment`** — то, что официальный образ читает при первом запуске пустого тома и создаёт роль/БД.

`${POSTGRES_DB:-library_db}` подставляет Compose с хоста из корневого `.env`. Если файла нет — дефолт после `:-`. В контейнер уходит уже `library_db`, не сырой синтаксис.

**`db.ports: "5433:5432"`** — с ноутбука `127.0.0.1:5433` → порт 5432 внутри `db`. Для DBeaver. Контейнер `app` этот проброс не использует: он ходит на `db:5432` по внутренней сети.

**`db.volumes: pgdata:/var/lib/postgresql/data`** — именованный том на каталог данных Postgres. Пересоздали контейнер `db` — таблицы на месте. Путь справа — linux-путь внутри образа, его не меняют.

**`healthcheck.test`** — `pg_isready` возвращает 0, когда демон принимает соединения. `CMD-SHELL` нужен, чтобы строка выполнилась через `sh`. `interval` / `timeout` / `retries` — как часто проверять, сколько ждать, после скольких провалов считать сервис больным.

**`app.build: .`** — собрать образ из `Dockerfile` в текущей папке. Контекст = `.` (минус `.dockerignore`).

**`app.ports: "8080:8080"`** — браузер и `curl` с хоста бьют в левую восьмёрку. Правая должна совпадать с `APP_PORT` и `EXPOSE`: Uvicorn внутри слушает 8080.

**`app.env_file: .env`** — загрузить все ключи файла в процесс. Нужны `POSTGRES_*` для `Settings`. Файл должен лежать на хосте рядом с YAML (`cp .env.example .env`).

**`app.environment`** — точечные переопределения поверх `.env`:

| Ключ | Зачем именно такое значение |
|------|------------------------------|
| `POSTGRES_HOST: db` | не `localhost` — Postgres в другом контейнере |
| `POSTGRES_PORT: 5432` | внутренний порт образа, не 5433 с хоста |
| `APP_HOST: 0.0.0.0` | иначе проброс 8080 не дойдёт до Uvicorn |
| `APP_PORT: 8080` | совпадает с `EXPOSE` и правой частью `ports` |

**`depends_on.db.condition: service_healthy`** — не стартовать `app`, пока healthcheck `db` не станет зелёным. Без `condition` Compose ждал бы только `docker start`, и Alembic поймал бы `connection refused`.

**`volumes: pgdata:`** (корень файла) — объявить том, на который ссылается `db`. Имя любое, но одно и то же в двух местах.

---

## 5. Makefile (опционально)

В корень, к уже существующим целям:

```makefile
docker-up:
	docker compose up --build

docker-down:
	docker compose down
```

Windows без make — те же команды `docker compose` вручную.

---

## Разбор: зачем `environment` поверх `env_file`

Два разных механизма, оба про переменные:

| | Подстановка `${...}` в YAML | `env_file` | `environment` |
|---|-----------------------------|------------|----------------|
| Когда | Compose **парсит** файл | контейнер уже стартует | контейнер уже стартует |
| Где действует | текст YAML на хосте | процесс внутри | процесс внутри |
| Пример | `POSTGRES_DB: ${POSTGRES_DB:-library_db}` у сервиса `db` | все ключи из `.env` у `app` | `POSTGRES_HOST: db` у `app` |

```text
1. Compose читает docker-compose.yml
2. Подставляет ${POSTGRES_DB} из корневого .env  →  в YAML уже library_db
3. Поднимает db с environment POSTGRES_DB=library_db
4. Поднимает app: сначала ключи из env_file (.env), потом environment
5. Settings в Python: переменные окружения бьют значения из файла на диске
```

| Источник | `POSTGRES_HOST` | `POSTGRES_PORT` | `APP_HOST` |
|----------|-----------------|-----------------|------------|
| `.env` на диске | `localhost` | `5432` | `127.0.0.1` |
| Compose `environment` | `db` | `5432` | `0.0.0.0` |
| Что видит контейнер `app` | `db` | `5432` | `0.0.0.0` |

Локальный `make run` по-прежнему ходит в Postgres на ноутбуке. `docker compose up` — в контейнер `db`. Один `.env`, два режима.

Порты — это две разные пары «слева:справа»:

| Куда стучитесь | Адрес |
|----------------|--------|
| браузер / `curl` → API | `127.0.0.1:8080` |
| DBeaver → Postgres **в Docker** | `127.0.0.1:5433` |
| контейнер `app` → контейнер `db` | `db:5432` |
| `make run` на ноутбуке → локальный Postgres | `localhost:5432` |

`5433:5432` как раз затем, чтобы локальный Postgres с шага 1 можно было не останавливать. `POSTGRES_PORT: 5432` в `environment` нужен явно: если когда-нибудь в `.env` окажется `5433` «для DBeaver», приложение внутри Docker полезет на `db:5433`, которого нет — внутри контейнера Postgres всегда слушает 5432.

---

## Запуск

В корне репозитория, Docker Desktop/Engine запущен. `.env` должен существовать (`cp .env.example .env`, если ещё нет).

Локальный PostgreSQL можно не трогать. Свободен должен быть порт **8080** (не гоняйте параллельно `python -m app.main`) и **5433**.

```bash
docker compose up --build
```

Первый раз качаются `python:3.12-slim` и `postgres:16` — это несколько сотен мегабайт. В логах `app` сначала `alembic upgrade head`, потом сиды, потом Uvicorn на `0.0.0.0:8080`.

Остановка: Ctrl+C в этом терминале, затем (если контейнеры ещё висят):

```bash
docker compose down
```

В фоне:

```bash
docker compose up --build -d
docker compose logs -f app
docker compose down
```

---

## ✅ Проверка

```bash
docker compose ps
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/docs -o /dev/null -w "%{http_code}\n"
docker compose exec db psql -U library_user -d library_db -c "SELECT 1;"
```

Если CRUD уже собран (гайд FastAPI / aiohttp):

```bash
curl -s http://127.0.0.1:8080/books | python -m json.tool
```

Swagger: [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs)

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | `docker compose up --build` | оба сервиса `running` / `healthy` |
| ☐ | лог `app` | `alembic upgrade` без ошибки, Uvicorn `0.0.0.0:8080` |
| ☐ | `GET /health` | `{"status":"ok"}` |
| ☐ | `GET /docs` | `200` |
| ☐ | `docker compose exec db psql … SELECT 1` | `1` |
| ☐ | DBeaver (по желанию) на `localhost:5433` | те же `library_user` / `library_db` |
| ☐ | `docker compose down` и снова `up` | сиды не дублируются, данные на месте (том `pgdata`) |

---

## Типичные ошибки

| Симптом | Что проверить |
|---------|----------------|
| `Cannot connect to the Docker daemon` | Desktop/Engine не запущен, на Linux — нет группы `docker` |
| `Bind for 0.0.0.0:5433 failed` | занят 5433; смените левую часть `ports` у `db` |
| `Bind for 0.0.0.0:8080 failed` | уже запущен `python -m app.main` на хосте |
| `connection refused` / `could not translate host name` к БД | забыли `POSTGRES_HOST: db`, остался `localhost` |
| `curl` с хоста не коннектится, в логах Uvicorn есть | `APP_HOST` всё ещё `127.0.0.1` |
| `exec user process caused: no such file or directory` | CRLF в `docker-entrypoint.sh` |
| `alembic: No module named app` | в образ не попали `app/` или `WORKDIR` не `/app` |
| `app` рестартится, `db` ещё `health: starting` | слишком мало `retries` у healthcheck **или** неверный user в `pg_isready` |
| сиды есть, таблиц нет | entrypoint не вызвался, запустили контейнер с другой командой |
| изменения в Python не видны | нужен `docker compose up --build`, без `--build` живёт старый образ |

Полезные команды, когда уже поднято:

```bash
docker compose logs -f app
docker compose logs -f db
docker compose exec app alembic current
docker compose ps
```

Карта раздела: [README.md](README.md) · FastAPI: [../fastapi/README.md](../fastapi/README.md)

**Дальше:** фоновый экспорт каталога (Redis + Celery в том же Compose) — [../celery/README.md](../celery/README.md).
