-- Lição 11: as reservas que se sobrepõem a alguma anterior no mesmo recurso.
-- Rode antes da migração da constraint. Qual das duas vale é decisão sua, não do banco.
-- docker compose exec -T postgres psql -U fairfare -d fairfare < chapters/04-o-banco-de-dados-de-verdade/bancada/sobreposicoes.sql
SELECT id, resource_id, user_id, starts_at, ends_at
FROM (
    SELECT *,
           max(ends_at) OVER (
               PARTITION BY resource_id ORDER BY starts_at, id
               ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
           ) AS fim_das_anteriores
    FROM bookings
) b
WHERE fim_das_anteriores > starts_at
ORDER BY resource_id, starts_at;
