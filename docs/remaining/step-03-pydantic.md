# Шаг 3 — Мини-гайд по Pydantic и настройки приложения

**Предыдущий:** [step-02-client.md](step-02-client.md) · **Следующий:** [step-04-app.md](step-04-app.md)

## Задача

Понять, зачем Pydantic, и перевести конфиг с `os.getenv` на `BaseSettings`. На шаге 7 те же модели будут валидировать JSON API.

Без этого шага `.env` с `APP_PORT=abc` упадёт уже на старте — а не где-то в глубине handler.

---

## Теория: зачем не `dict`

В Python данные снаружи (`.env`, JSON, query) — это строки и словари. В коде вам нужны `int`, `str | None`, «имя не пустое».

| Подход | Что будет на `year: "много"` |
|--------|------------------------------|
| `body["year"]` | тихая порча или `TypeError` позже |
| **Pydantic `BaseModel`** | сразу `ValidationError` с понятным списком ошибок |

В DRF эту роль играет Serializer. Здесь — Pydantic: меньше магии, те же идеи (вход → проверка → объект с типами).

Два слоя в этом проекте:

```text
Settings(BaseSettings)     ← .env / переменные окружения
GenreCreate(BaseModel)     ← JSON тела запроса  (шаг 7)
GenreRead(BaseModel)       ← JSON ответа
```

SQLAlchemy-модели — это таблицы. Pydantic-модели — контракт API и конфиг. Их не смешивают в один класс.

---

## Теория: `BaseModel`, `Field`, ошибки

```python
from pydantic import BaseModel, Field, ValidationError


class GenreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


GenreCreate.model_validate({"name": "фантастика"})  # ок
GenreCreate.model_validate({"name": ""})            # ValidationError
```

| Метод | Направление |
|-------|-------------|
| `model_validate(data)` | dict / объект → модель (кидает `ValidationError`) |
| `model_dump()` | модель → обычный `dict` (для `json_response`) |
| `model_validate_json(raw)` | строка JSON → модель |

`Field(...)` — ограничения, которых нет в одном только `str`: длина, `ge`/`le`, описание.

`from_attributes=True` — читать поля с ORM-объекта (`genre.name`), не только из dict. Понадобится в `GenreRead` на шаге 7.

```python
class GenreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
```

`ValidationError.errors()` — список `{loc, msg, type}`. В API его отдают как `422`, не как 500.

---

## Теория: настройки — `BaseSettings`

`os.getenv("APP_PORT", "8080")` всегда строка: `int()` вы пишете руками, про опечатку `POSGRES_DB` узнаёте из странной ошибки Postgres.

`pydantic-settings.BaseSettings`:

1. читает `.env` сам (python-dotenv не нужен);
2. мапит `POSTGRES_DB` → поле `postgres_db`;
3. приводит типы (`postgres_port: int`);
4. падает при старте, если порт — не число.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_port: int = 5432
```

`extra="ignore"` — лишние ключи в `.env` не ломают запуск.

Один экземпляр на процесс:

```python
settings = Settings()
```

Дальше везде `settings.app_port`, не россыпь констант.

---

## Код — `app/config.py`

```python
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @property
    def database_url(self) -> str:
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
```

**Разбор:**

| Кусок | Зачем |
|-------|--------|
| `env_file=".env"` | секреты не в git, как в магазине |
| имена полей `postgres_*` | совпадают с ключами `.env` без ручного `os.getenv` |
| `database_url` / `database_url_sync` | async-приложение vs sync-Alembic |
| `quote_plus` | пароль со спецсимволами не сломает URL |
| `settings = Settings()` | один объект на импорт |

---

## ✅ Проверка

```bash
source .venv/bin/activate
python -c "from app.config import settings; print(settings.postgres_db, settings.app_port, type(settings.app_port))"
```

Должно напечатать `library_db 8080 <class 'int'>` — порт уже `int`, не строка.

Сломайте на секунду `.env`: `APP_PORT=abc`, снова импортируйте — должен быть `ValidationError`. Верните `8080`.

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | Импорт `settings` | `library_db` и порт как `int` |
| ☐ | `APP_PORT=abc` | процесс не стартует, ошибка валидации |
| ☐ | `.env` снова валидный | импорт проходит |

**Все пункты отмечены?** → [step-04-app.md](step-04-app.md)
