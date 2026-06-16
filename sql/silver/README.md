# silver

Snowflake DDL for standardized silver-layer objects.

Silver tables contain standardized customer identities, daily conformed metrics, partner profiles,
and CDC history. Entity-resolution jobs should read from `SILVER.silver_customer`.

## Merge Scripts

- `001_silver_tables.sql`: Silver table definitions.
- `002_merge_silver_customer.sql`: Standardizes and merges customer identity records.
- `003_merge_silver_customer_metric_daily.sql`: Merges daily behavioral and operational metrics.
- `004_merge_silver_partner_profile.sql`: Standardizes and merges partner records.
- `005_insert_silver_data_quality_metrics.sql`: Publishes Silver quality metrics.

The merge scripts use `since_watermark` as the incremental boundary. Override it before execution
when running backfills or Airflow task windows.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
