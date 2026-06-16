# analytics

Snowflake DDL for reporting-ready tables consumed by Domo.

Analytics tables are dashboard-ready daily snapshots, customer health scores, partner performance,
data-quality metrics, pipeline execution logs, ETL lineage, and Domo refresh logs.

## Customer Health Scoring

- `001_customer_health_scores.sql`: creates reporting tables, model feature storage,
  and model evaluation storage.
- `002_build_customer_health_features.sql`: builds model-ready features from Gold
  enrichment metrics.
- `003_merge_customer_health_scores.sql`: merges Python/ML prediction rows into
  `customer_health_scores`.
- `004_merge_customer_health_model_evaluations.sql`: merges training evaluation
  metrics for Logistic Regression, Random Forest, and XGBoost.

## Data Quality Dashboard

- `005_merge_data_quality_results.sql`: merges Great Expectations metrics,
  validation run summaries, and alert events.
- `006_build_data_quality_dashboard_daily.sql`: builds the daily quality dashboard
  aggregate for Domo and operations monitoring.

## Enterprise Audit Logs

- `pipeline_execution_log`: run-level pipeline audit table with start/end time,
  status, error details, and row counters.
- `etl_audit_log`: step-level ETL audit table with source, destination, row counts,
  checksum, status, and structured details.
- `007_merge_enterprise_audit_logs.sql`: merges staged audit records into both
  enterprise audit tables.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
