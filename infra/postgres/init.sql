-- Seed a larger deterministic catalog so full-lab runs exercise real JSON payloads
-- and JDBC scans without relying on tiny toy datasets.
CREATE TABLE IF NOT EXISTS benchmark_products (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    brand TEXT NOT NULL,
    region TEXT NOT NULL,
    segment TEXT NOT NULL,
    primary_tag TEXT NOT NULL,
    secondary_tag TEXT NOT NULL,
    tertiary_tag TEXT NOT NULL
);

INSERT INTO benchmark_products (
    id,
    name,
    category,
    price,
    brand,
    region,
    segment,
    primary_tag,
    secondary_tag,
    tertiary_tag
)
SELECT
    series_id,
    'Product-' || series_id,
    'Category-' || (series_id % 20),
    ROUND((10 + (series_id % 100) + ((series_id % 9) * 0.17))::numeric, 2),
    'Brand-' || (series_id % 10),
    'Region-' || (series_id % 5),
    'Segment-' || (series_id % 3),
    'tag-' || (series_id % 4),
    'tag-' || (series_id % 6),
    'tag-' || (series_id % 8)
FROM generate_series(1, 50000) AS series_id
ON CONFLICT (id) DO NOTHING;
