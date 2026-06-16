# great_expectations

Data quality expectation suites, checkpoints, and validation plugins.

## Production Suites

- `customer_silver_suite`: Silver customer completeness, uniqueness, validity,
  consistency, and freshness.
- `gold_customer_master_suite`: golden-record identity, survivorship, and recency checks.
- `customer_enrichment_metrics_suite`: CLV, adoption, engagement, support health,
  renewal, and freshness checks.
- `customer_health_scores_suite`: health-score classes, model metadata, score ranges,
  uniqueness, and freshness checks.

The checkpoint `checkpoints/customer360_data_quality_checkpoint.yml` runs all four
suite contracts against Snowflake runtime queries. Python orchestration lives in
`src/customer360/infrastructure/great_expectations.py`.

Dashboard outputs are stored in `ANALYTICS.data_quality_metrics`,
`ANALYTICS.data_quality_validation_runs`, `ANALYTICS.data_quality_alerts`, and
`ANALYTICS.data_quality_dashboard_daily`.

## Why This Folder Exists

- Makes ownership clear as the Customer 360 platform grows.
- Keeps orchestration, transformation, domain logic, infrastructure adapters, documentation, and tests separated.
- Helps engineers find the right place for new production assets without guessing.

## Operating Rules

- Keep files cohesive with this folder's responsibility.
- Do not commit secrets or production customer data.
- Prefer small, reviewed changes with tests, validation, or clear run notes.
