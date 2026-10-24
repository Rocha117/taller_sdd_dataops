-- Permisos por grupo: matriz "Quién puede ver qué" de constitucion/stack-tecnologico.md.
--
-- NO lo ejecuta el pipeline: en Databricks Free Edition no existen estos grupos y
-- los GRANT fallarían. Queda versionado para un workspace real.
--
-- Para usarlo en un workspace real:
--   1. Crear los grupos marketing, bi, gobierno e ingenieria (Settings → Identity and access).
--   2. Reemplazar {{catalog}} y {{schema}} (por defecto: workspace y demo).
--   3. Ejecutarlo en el SQL Editor con un usuario administrador del catálogo.
--
-- | Tabla                  | marketing | bi | gobierno | ingenieria |
-- |------------------------|-----------|----|----------|------------|
-- | bronze_customers       |           |    |    ✔     |     ✔      |
-- | silver_customers (PII) |    ✔      |    |    ✔     |     ✔      |
-- | gold_contactables_pais |    ✔      | ✔  |    ✔     |     ✔      |
-- | rechazados_customers   |           |    |    ✔     |     ✔      |
-- | monitoreo_ejecuciones  |           | ✔  |    ✔     |     ✔      |
-- | ref_paises             |    ✔      | ✔  |    ✔     |     ✔      |
--
-- ref_paises no tiene datos personales; se abre a todos para que puedan leer Gold con contexto.

-- Acceso al catálogo y al schema (necesario para cualquier SELECT)
GRANT USE CATALOG ON CATALOG {{catalog}} TO `marketing`;
GRANT USE CATALOG ON CATALOG {{catalog}} TO `bi`;
GRANT USE CATALOG ON CATALOG {{catalog}} TO `gobierno`;
GRANT USE CATALOG ON CATALOG {{catalog}} TO `ingenieria`;

GRANT USE SCHEMA ON SCHEMA {{catalog}}.{{schema}} TO `marketing`;
GRANT USE SCHEMA ON SCHEMA {{catalog}}.{{schema}} TO `bi`;
GRANT USE SCHEMA ON SCHEMA {{catalog}}.{{schema}} TO `gobierno`;
GRANT USE SCHEMA ON SCHEMA {{catalog}}.{{schema}} TO `ingenieria`;

-- Bronze: solo gobierno e ingeniería
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.bronze_customers TO `gobierno`;
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.bronze_customers TO `ingenieria`;

-- Silver (con email): marketing, gobierno e ingeniería. BI no ve emails.
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.silver_customers TO `marketing`;
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.silver_customers TO `gobierno`;
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.silver_customers TO `ingenieria`;

-- Gold (sin datos personales): todos
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.gold_contactables_pais TO `marketing`;
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.gold_contactables_pais TO `bi`;
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.gold_contactables_pais TO `gobierno`;
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.gold_contactables_pais TO `ingenieria`;

-- Rechazados (registro original con PII): gobierno e ingeniería
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.rechazados_customers TO `gobierno`;
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.rechazados_customers TO `ingenieria`;

-- Monitoreo: bi, gobierno e ingeniería
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.monitoreo_ejecuciones TO `bi`;
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.monitoreo_ejecuciones TO `gobierno`;
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.monitoreo_ejecuciones TO `ingenieria`;

-- Referencia de países: todos
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.ref_paises TO `marketing`;
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.ref_paises TO `bi`;
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.ref_paises TO `gobierno`;
GRANT SELECT ON TABLE {{catalog}}.{{schema}}.ref_paises TO `ingenieria`;
