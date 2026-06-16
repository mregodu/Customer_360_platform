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

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
