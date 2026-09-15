from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "library.db"

DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
DATABASE_URL_SYNC = f"sqlite:///{DB_PATH}"

HOST = "127.0.0.1"
PORT = 8080
