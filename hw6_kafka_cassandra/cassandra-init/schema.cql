CREATE KEYSPACE IF NOT EXISTS warehouse
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'datacenter1': 3
};

USE warehouse;

-- (1) Остатки товаров по зонам.
-- partition key = product_id: чтобы все строки для одного товара лежали на одной партиции
--   (запросы "все зоны для товара" - одна партиция).
-- clustering key = zone_id: уникальность строки и сортировка по зонам.
CREATE TABLE IF NOT EXISTS inventory_by_product_zone (
  product_id TEXT,
  zone_id TEXT,
  available_quantity BIGINT,
  reserved_quantity BIGINT,
  last_event_timestamp TIMESTAMP,
  last_event_id TEXT,
  supplier_id TEXT,
  PRIMARY KEY ((product_id), zone_id)
);

-- (2) Остатки товара агрегированно (по всем зонам).
-- partition key = product_id, одна строка на товар.
CREATE TABLE IF NOT EXISTS inventory_by_product (
  product_id TEXT PRIMARY KEY,
  total_available_quantity BIGINT,
  total_reserved_quantity BIGINT,
  last_event_timestamp TIMESTAMP
);

-- (3) Все товары в зоне.
-- partition key = zone_id: запросы "все, что лежит в зоне" - одна партиция.
-- clustering key = product_id: уникальность.
CREATE TABLE IF NOT EXISTS inventory_by_zone (
  zone_id TEXT,
  product_id TEXT,
  available_quantity BIGINT,
  reserved_quantity BIGINT,
  last_event_timestamp TIMESTAMP,
  PRIMARY KEY ((zone_id), product_id)
);

-- (4) Заказы. partition key = order_id.
CREATE TABLE IF NOT EXISTS orders (
  order_id TEXT PRIMARY KEY,
  status TEXT,
  items TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- (5) Идемпотентность - журнал обработанных событий.
-- TTL 7 дней, чтобы таблица не разрасталась бесконечно.
CREATE TABLE IF NOT EXISTS processed_events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT,
  processed_at TIMESTAMP
) WITH default_time_to_live = 604800;

-- (6) История событий (аудит, опциональная таблица).
-- partition key = product_id, clustering = (event_timestamp, event_id) DESC
-- - выдает последние события по товару одной партицией.
CREATE TABLE IF NOT EXISTS event_history (
  product_id TEXT,
  event_timestamp TIMESTAMP,
  event_id TEXT,
  event_type TEXT,
  payload TEXT,
  PRIMARY KEY ((product_id), event_timestamp, event_id)
) WITH CLUSTERING ORDER BY (event_timestamp DESC, event_id DESC);
