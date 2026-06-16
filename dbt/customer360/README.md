# Customer 360 dbt Project

This dbt project builds the warehouse-facing Customer 360 transformation layer in Snowflake.

## Layers

- `bronze`: source-specific raw models with ingestion metadata and record hashes.
- `silver`: standardized customer identity, customer metrics, partner profiles, and change history.
- `gold`: Splink cluster publication, identity map, golden customer master, and enrichment metrics.
- `analytics`: Domo-ready health scores, executive KPIs, Customer Success snapshots, partner performance, and data-quality dashboards.

## Run Order

1. `dbt seed --project-dir dbt/customer360`
2. `dbt run --project-dir dbt/customer360 --select tag:bronze`
3. `dbt run --project-dir dbt/customer360 --select tag:silver`
4. Run Splink/Python matching to populate `GOLD.stage_gold_customer_clusters` and optional pairwise prediction staging.
5. `dbt run --project-dir dbt/customer360 --select tag:gold`
6. Run Great Expectations pipelines to populate runtime quality tables.
7. `dbt run --project-dir dbt/customer360 --select tag:analytics`
8. `dbt snapshot --project-dir dbt/customer360`
9. `dbt test --project-dir dbt/customer360`

## Lineage

Lineage is encoded with dbt `source`, `ref`, snapshot, and exposure dependencies. The Domo dashboard exposures in `models/exposures.yml` connect Analytics outputs to downstream consumers.

## Notes

- `generate_schema_name` is overridden so dbt writes to exact Snowflake schemas: `BRONZE`, `SILVER`, `GOLD`, `ANALYTICS`, `REFERENCE`, and `SNAPSHOTS`.
- Runtime Python jobs still own API extraction, Splink execution, ML model training, Great Expectations execution, and Domo publication.
- Secrets must stay in environment variables or a secret manager.
