-- Bancada da lição 06: um banco com volume.
-- ATENÇÃO: APAGA tudo o que houver em users, resources e bookings do banco de desenvolvimento.
--
-- docker compose exec -T postgres psql -U fairfare -d fairfare -v linhas=1000000 \
--   < chapters/04-o-banco-de-dados-de-verdade/bancada/seed.sql
\timing on

TRUNCATE users, resources, bookings RESTART IDENTITY CASCADE;

INSERT INTO users (nome, email) VALUES ('Semente', 'semente@example.com');
INSERT INTO resources (nome, tipo) SELECT 'Quadra ' || i, 'quadra' FROM generate_series(1, 50) i;

-- Cada quadra recebe reservas de uma hora, uma atrás da outra, sem sobreposição
-- (a lição 11 cria uma regra que recusaria sobreposições).
INSERT INTO bookings (user_id, resource_id, starts_at, ends_at)
SELECT 1,
       i % 50 + 1,
       timestamptz '2030-01-01 00:00+00' + (i / 50) * interval '1 hour',
       timestamptz '2030-01-01 00:00+00' + (i / 50 + 1) * interval '1 hour'
FROM generate_series(0, :linhas - 1) i;

-- Estatísticas frescas: sem elas, o planner decide no escuro.
ANALYZE bookings;
