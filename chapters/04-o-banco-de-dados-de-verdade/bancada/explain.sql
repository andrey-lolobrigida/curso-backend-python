-- Lição 06: a consulta do find_overlapping, como o SQLAlchemy a escreve.
-- docker compose exec -T postgres psql -U fairfare -d fairfare < chapters/04-o-banco-de-dados-de-verdade/bancada/explain.sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM bookings
WHERE resource_id = 7
  AND starts_at < timestamptz '2031-01-01 12:00+00'
  AND ends_at > timestamptz '2031-01-01 10:00+00';
