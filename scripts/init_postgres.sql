-- Пользователь и БД для учебной библиотеки на aiohttp.
-- Пароль library_user должен совпадать с POSTGRES_PASSWORD в .env:
--   POSTGRES_PASSWORD=library_pass
--
-- Linux:  ./scripts/init_postgres.sh
-- macOS:  ./scripts/init_postgres_mac.sh
-- Windows: powershell -File scripts\init_postgres.ps1

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'library_user') THEN
        CREATE USER library_user WITH PASSWORD 'library_pass';
    ELSE
        ALTER USER library_user WITH PASSWORD 'library_pass';
    END IF;
END
$$;

SELECT 'CREATE DATABASE library_db OWNER library_user ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'library_db')\gexec

GRANT ALL PRIVILEGES ON DATABASE library_db TO library_user;
ALTER USER library_user CREATEDB;

\c library_db

GRANT ALL PRIVILEGES ON SCHEMA public TO library_user;
GRANT CREATE ON SCHEMA public TO library_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO library_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO library_user;
