-- Скрипт инициализации базы данных PostgreSQL для крипто-бота
-- Этот файл выполняется автоматически при первом запуске контейнера PostgreSQL

-- Создаем базу данных если она не существует
SELECT 'CREATE DATABASE crypto_bot'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'crypto_bot')\gexec

-- Подключаемся к базе данных
\c crypto_bot;

-- Создаем расширения если нужны
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Даем права пользователю
GRANT ALL PRIVILEGES ON DATABASE crypto_bot TO crypto_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO crypto_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO crypto_user;

-- Устанавливаем права по умолчанию для будущих таблиц
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO crypto_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO crypto_user;