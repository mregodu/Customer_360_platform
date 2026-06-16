# dags

Production Airflow DAG definitions. DAGs orchestrate package services, Snowflake SQL, dbt, Great Expectations, and Domo publishing while keeping business logic in `src/customer360`.

## DAGs

- `customer_ingestion_dag`: source-to-Bronze ingestion for Salesforce, Marketo, Zendesk, Product Usage, Licensing, and Impartner.
- `customer_standardization_dag`: Bronze-to-Silver standardization plus Silver quality validation.
- `customer_matching_dag`: Splink matching, Gold clusters, golden customer master generation, and Gold validation.
- `customer_enrichment_dag`: enrichment metric generation and validation.
- `customer_scoring_dag`: Customer Health feature build, model training/scoring, and score validation.
- `dashboard_refresh_dag`: data-quality dashboard build, Domo reporting-layer build, and Domo dataset publishing.

## Operations

- Schedules, retries, catchup, owner, pools, and failure email behavior are read from `configs/<env>.yaml`.
- Runtime tasks load full Customer 360 configuration only when executed, so DAG parsing does not require source-system credentials.
- Failures, retries, and SLA misses emit Airflow notification callbacks; task bodies write enterprise audit records to Snowflake.
- Cross-DAG dependencies use `ExternalTaskSensor` completion markers.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
