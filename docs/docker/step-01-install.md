# Шаг 1 — Что такое Docker, установка, первые команды

**Предыдущий:** [README](README.md) · **Следующий:** [step-02-app.md](step-02-app.md)

## Задача

Понять, чем образ отличается от контейнера, поставить **Docker Desktop** (Windows / macOS) и проверить, что движок отвечает на команды. Приложение библиотеки на этом шаге **не трогаем**.

Без этого шага Dockerfile со следующего шага не к чему применять.

---

## Теория: зачем Docker

До сих пор у каждого свой зоопарк:

| На машине | Что может поехать |
|-----------|-------------------|
| Python 3.11 vs 3.13 | пакет не ставится / другой синтаксис |
| Postgres 14 vs 16 | другая аутентификация, нет нужного типа |
| «Я поставил пакет глобально» | у соседа его нет |
| `.env` забыли скопировать | `ValidationError` на старте |

Фраза «у меня работает» как раз про это: код один, окружение разное.

**Контейнер** — процесс с собственным файлами, сетью и переменными окружения. Внутри — Linux, фиксированные версии Python и пакетов. На ноутбуке Windows, macOS или Ubuntu снаружи это выглядит одинаково: `docker compose up`.

```text
без Docker                         с Docker
──────────                         ────────
ты: Python, venv, brew/apt Postgres    ты: Docker Desktop
сосед: другой Python, другой Postgres  сосед: Docker Desktop
CI: третья комбинация                  CI: тот же Dockerfile
```

Рецепт окружения лежит в репозитории (`Dockerfile`), а не в голове.

---

## Теория: образ, контейнер, Dockerfile

Три слова, которые путают чаще всего:

| Термин | Аналогия | Что это |
|--------|----------|---------|
| **Dockerfile** | рецепт | текстовый файл: «возьми Python, поставь пакеты, скопируй код» |
| **образ (image)** | класс / ISO | неподвижный снимок файловой системы; его **собирают** (`build`) или **скачивают** (`pull`) |
| **контейнер** | объект / запущенная ВМ | живой процесс из образа; их можно запустить несколько из одного образа |

```text
Dockerfile  ──build──►  образ  ──run──►  контейнер
   рецепт              «класс»          «экземпляр»
```

Образ **не меняется**, пока вы его не пересоберёте. Контейнер можно остановить, удалить, создать заново — данные внутри него по умолчанию пропадут (для Postgres поэтому нужен **том**, это на шаге 2).

**Реестр** (Docker Hub) — полка с готовыми образами. Строка `postgres:16` значит: скачай образ PostgreSQL 16. Тег после двоеточия — версия, не «имя контейнера».

---

## Теория: контейнер ≠ виртуальная машина

| | Виртуальная машина | Контейнер |
|---|--------------------|-----------|
| Что внутри | гостевая ОС целиком | процесс + изолированные файлы/сеть |
| Тяжесть | гигабайты, минуты на старт | десятки–сотни МБ, секунды |
| Ядро | своё | **ядро хоста** (на Win/Mac — ядро Linux-ВМ Desktop) |

Для нашего API ВМ избыточна: нужен Python-процесс и Postgres-процесс, не две полноценные ОС.

---

## Теория: зачем Docker Desktop на Windows и macOS

Контейнеры Docker — это **Linux-процессы**. На Linux движок может крутиться прямо на ядре. На Windows и macOS Linux-ядра нет, поэтому Desktop поднимает маленькую Linux-ВМ и прячет её за иконкой кита.

```text
Windows / macOS
    └── Docker Desktop
            └── Linux-ВМ (на Windows это WSL 2)
                    └── контейнеры
```

Поэтому на Win/Mac ставим не «голый» `docker` из случайного туториала, а **Docker Desktop**: движок, `docker compose` и GUI в одном установщике. Пока кит не «зелёный / Engine running», команды из терминала не заработают.

Linux: Desktop не обязателен, достаточно Docker Engine. Кратко — в конце раздела установки.

---

## 1. Установка

### Windows

Нужны Windows 10 (22H2+) или Windows 11, виртуализация в BIOS включена.

1. В PowerShell **от администратора**:

```powershell
wsl --install
```

Перезагрузка, если попросит. Проверка: `wsl --status` — должен быть WSL 2.

2. Скачайте [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/). Прямая ссылка с сайта: [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/).

3. Установщик: галка **Use WSL 2 instead of Hyper-V** (так и должно быть по умолчанию).

4. Перезагрузка, запустите **Docker Desktop**, дождитесь «Engine running».

5. В обычном PowerShell (не обязательно админ):

```powershell
docker version
docker compose version
```

Если `docker` «не является командой» — Desktop не доустановился в PATH, перелогиньтесь или перезапустите терминал.

### macOS

1. Скачайте [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/):
   - **Apple Silicon** (M1/M2/M3/M4) — ARM;
   - **Intel** — x86_64.
   
   «About This Mac» → чип. Не перепутайте: Intel-образ на M-чипе будет тормозить через эмуляцию.

2. Перетащите Docker в `Applications`, запустите, подтвердите права.

Через Homebrew, если так привычнее:

```bash
brew install --cask docker
```

3. Дождитесь, пока кит в строке меню перестанет анимироваться.

```bash
docker version
docker compose version
```

### Linux (кратко)

Desktop можно поставить и сюда, но для урока достаточно движка. Ubuntu / Debian — [официальная инструкция Engine](https://docs.docker.com/engine/install/ubuntu/). Минимально на Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker "$USER"
```

После `usermod` **выйдите из сессии и зайдите снова**, иначе `permission denied` на `/var/run/docker.sock`.

```bash
docker version
docker compose version
```

Пишем `docker compose` (плагин, пробел), не старый бинарь `docker-compose`.

---

## 2. Как пользоваться: модель команд

Клиент `docker` говорит **демону** (Engine). Демон качает образы, создаёт контейнеры, пробрасывает порты.

```text
терминал  →  docker / docker compose  →  Engine  →  контейнеры
```

| Команда | Зачем |
|---------|--------|
| `docker version` | клиент и сервер живы |
| `docker pull ИМЯ:ТЕГ` | скачать образ, не запуская |
| `docker images` | какие образы уже на диске |
| `docker run ...` | создать контейнер из образа и запустить |
| `docker ps` | **запущенные** контейнеры |
| `docker ps -a` | все, включая остановленные |
| `docker logs ИМЯ` | stdout/stderr процесса внутри |
| `docker exec -it ИМЯ КОМАНДА` | выполнить команду *внутри* уже бегущего контейнера |
| `docker stop ИМЯ` | корректно остановить |
| `docker rm ИМЯ` | удалить контейнер (образ останется) |
| `docker rmi ИМЯ` | удалить образ |
| `docker compose up` | поднять всё из `docker-compose.yml` (шаг 2) |
| `docker compose down` | остановить и убрать контейнеры этого проекта |

`run` без `--name` сам придумает имя вроде `funny_einstein`. С `--rm` контейнер удалится после остановки — удобно для разовых проверок.

Проброс порта: `-p 8080:8080` значит «порт **хоста** : порт **внутри контейнера**». Браузер всегда бьёт в левую часть.

---

## 3. Практика: `hello-world`

Демон должен быть запущен (кит зелёный).

```bash
docker run --rm hello-world
```

Первый раз скачается крошечный образ. В выводе должно быть «Hello from Docker!» — клиент достучался до Engine, Engine скачал образ, контейнер отработал и (из-за `--rm`) исчез.

Список образов:

```bash
docker images
```

Должна быть строка `hello-world`.

---

## 4. Практика (по желанию): контейнер Postgres

Так выглядит «чужой» образ, который мы на шаге 2 подключим через Compose. Если на машине **уже** слушает локальный PostgreSQL на 5432 — этот запуск упадёт с `port is already allocated`. Тогда либо остановите локальный Postgres, либо пропустите блок: на шаге 2 разберём конфликт портов.

```bash
docker run --name lesson-pg --rm -d \
  -e POSTGRES_DB=library_db \
  -e POSTGRES_USER=library_user \
  -e POSTGRES_PASSWORD=library_pass \
  -p 5432:5432 \
  postgres:16
```

Windows PowerShell — та же команда в одну строку, без `\`.

```bash
docker ps
docker logs lesson-pg
```

В логах: `database system is ready to accept connections`.

Зайти *внутрь* контейнера в `psql`:

```bash
docker exec -it lesson-pg psql -U library_user -d library_db -c "SELECT 1;"
```

Остановить (из-за `--rm` контейнер удалится сам):

```bash
docker stop lesson-pg
```

Образ `postgres:16` останется на диске — следующий `compose up` не будет качать его заново.

---

## Разбор: что только что произошло

`docker run postgres:16`:

1. Нет образа локально → Engine качает слои с Docker Hub.
2. Создаётся контейнер: своя файловая система, своя сеть, переменные `POSTGRES_*`.
3. Официальный образ **сам** создаёт роль и БД из этих переменных. Скрипты `scripts/init_postgres*.sh` здесь не нужны.
4. `-p 5432:5432` — с хоста `localhost:5432` попадает в Postgres внутри контейнера.
5. `docker exec` — не новый контейнер, а команда в уже запущенном.

На шаге 2 те же идеи, только два контейнера и YAML вместо длинного `docker run`.

---

## ✅ Проверка

```bash
docker version
docker compose version
docker run --rm hello-world
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | Docker Desktop / Engine запущен | без `Cannot connect to the Docker daemon` |
| ☐ | `docker version` | есть блок `Server`, не только `Client` |
| ☐ | `docker compose version` | версия плагина, команда с **пробелом** |
| ☐ | `docker run --rm hello-world` | текст «Hello from Docker!» |

**Все пункты отмечены?** → [step-02-app.md](step-02-app.md)
