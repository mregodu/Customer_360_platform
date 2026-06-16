# sql

Snowflake DDL, schema setup, and administrative SQL organized by warehouse layer.

## Recommended Execution Order

Run the scripts with the role noted in each file:

1. `security/001_create_roles.sql`
2. `admin/001_create_warehouses.sql`
3. `landing/001_create_database_and_schemas.sql`
4. `landing/002_file_formats_stages_and_control_tables.sql`
5. `bronze/001_bronze_tables.sql`
6. `silver/001_silver_tables.sql`
7. `gold/001_gold_customer_master.sql`
8. `analytics/001_customer_health_scores.sql`
9. `security/002_grant_privileges.sql`
10. `security/003_masking_policies.sql`

## Recurring Transformation Scripts

After bronze ingestion completes, run these Silver transformation scripts with
`WH_CUSTOMER360_TRANSFORM`:

1. `silver/002_merge_silver_customer.sql`
2. `silver/003_merge_silver_customer_metric_daily.sql`
3. `silver/004_merge_silver_partner_profile.sql`
4. `silver/005_insert_silver_data_quality_metrics.sql`

After the Splink matching job stages cluster rows, run:

1. `gold/002_merge_gold_customer_clusters.sql`

## Warehouse Design

- `WH_CUSTOMER360_INGEST`: source extraction and landing-to-bronze loads.
- `WH_CUSTOMER360_TRANSFORM`: cleansing, dbt, enrichment, and analytics transforms.
- `WH_CUSTOMER360_MATCHING`: Splink pairwise matching and clustering workloads.
- `WH_CUSTOMER360_REPORTING`: Domo refreshes and analyst reads.

This split keeps reporting responsive while matching and ingestion run independently.

## Security Model

- `CUSTOMER360_PLATFORM_ADMIN`: platform owner and break-glass administration.
- `CUSTOMER360_LOADER`: landing and bronze loading.
- `CUSTOMER360_TRANSFORMER`: silver, gold, and analytics transformations.
- `CUSTOMER360_ANALYST`: curated read access.
- `CUSTOMER360_DOMO_ROLE`: analytics read-only service access.
- `CUSTOMER360_SECURITY_ADMIN`: access review and masking policy maintenance.

Sensitive customer fields are protected by masking policies for email, phone, and address.

## Clustering and Performance

- High-volume append tables are clustered by source and load or event date.
- Matching lookup tables are clustered by source identifiers and golden customer IDs.
- Dashboard tables are clustered by reporting date plus common filters such as health class,
  partner region, and tier.
- Search Optimization Service is intentionally documented as optional in the table scripts.
  Enable it only after validating workload patterns and Snowflake edition/cost impact.
- Keep transformation warehouses separate from reporting warehouses to avoid dashboard refresh
  contention during daily matching and enrichment jobs.

## Why This Folder Exists

- Makes ownership clear as the Customer 360 platform grows.
- Keeps orchestration, transformation, domain logic, infrastructure adapters, documentation, and tests separated.
- Helps engineers find the right place for new production assets without guessing.

## Operating Rules

- Keep files cohesive with this folder's responsibility.
- Do not commit secrets or production customer data.
- Prefer small, reviewed changes with tests, validation, or clear run notes.
