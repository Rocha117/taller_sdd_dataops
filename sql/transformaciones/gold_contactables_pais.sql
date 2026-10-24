-- Stage 5 · Gold: indicador de clientes contactables por país. Sin datos personales.
-- Parámetro: :run_id (la ejecución que cargó Bronze y Silver).
--   clientes_unicos       = clientes únicos del archivo (Bronze), manda la fila con menor _row_number
--   clientes_contactables = filas de Silver con es_contactable = true
-- Los clientes sin país o con país desconocido van a ZZ · "Sin país" · "Sin región";
-- esa fila solo aparece si hay alguno.
INSERT OVERWRITE {{catalog}}.{{schema}}.gold_contactables_pais
SELECT
  u.country_code,
  COALESCE(p.country_name, 'Sin país')                                AS country_name,
  COALESCE(p.region, 'Sin región')                                    AS region,
  u.clientes_unicos,
  COALESCE(c.clientes_contactables, 0)                                AS clientes_contactables,
  CAST(ROUND(100.0 * COALESCE(c.clientes_contactables, 0) / u.clientes_unicos, 2) AS DECIMAL(5,2))
                                                                      AS pct_contactables,
  :run_id                                                             AS _run_id,
  current_timestamp()                                                 AS _updated_at
FROM (
  SELECT
    CASE WHEN rp.country_code IS NULL THEN 'ZZ' ELSE b.country_code END AS country_code,
    COUNT(*)                                                            AS clientes_unicos
  FROM (
    SELECT
      upper(trim(coalesce(country, '')))                                           AS country_code,
      ROW_NUMBER() OVER (PARTITION BY trim(customer_id) ORDER BY _row_number)      AS orden
    FROM {{catalog}}.{{schema}}.bronze_customers
    WHERE _run_id = :run_id AND trim(coalesce(customer_id, '')) <> ''
  ) b
  LEFT JOIN {{catalog}}.{{schema}}.ref_paises rp ON b.country_code = rp.country_code
  WHERE b.orden = 1
  GROUP BY CASE WHEN rp.country_code IS NULL THEN 'ZZ' ELSE b.country_code END
) u
LEFT JOIN {{catalog}}.{{schema}}.ref_paises p ON u.country_code = p.country_code
LEFT JOIN (
  SELECT country_code, COUNT(*) AS clientes_contactables
  FROM {{catalog}}.{{schema}}.silver_customers
  WHERE _run_id = :run_id AND es_contactable
  GROUP BY country_code
) c ON u.country_code = c.country_code
