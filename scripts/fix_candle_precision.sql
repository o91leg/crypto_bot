-- Изменить точность полей volume и quote_volume
BEGIN;

-- Изменяем тип данных для volume
ALTER TABLE candles ALTER COLUMN volume TYPE NUMERIC(24,8);

-- Изменяем тип данных для quote_volume
ALTER TABLE candles ALTER COLUMN quote_volume TYPE NUMERIC(24,8);

-- Добавляем индексы для оптимизации
CREATE INDEX IF NOT EXISTS idx_candles_volume ON candles(volume);
CREATE INDEX IF NOT EXISTS idx_candles_quote_volume ON candles(quote_volume);

COMMIT;
