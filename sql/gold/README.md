# gold

Snowflake DDL for golden customer master and entity-resolution output tables.

Gold includes Splink match predictions, customer clusters, source-to-golden identity mapping,
golden customer master records, and enrichment metrics.

## Matching Outputs

- `customer_match_predictions`: pairwise Splink match probabilities and comparison vectors.
- `gold_customer_clusters`: final cluster output consumed by golden-record generation.
- `002_merge_gold_customer_clusters.sql`: merges staged cluster rows into the gold output table.
- `003_generate_gold_customer_master.sql`: applies survivorship rules and merges trusted
  records into `gold_customer_master`.
- `004_generate_customer_enrichment_metrics.sql`: rolls Silver activity metrics up to
  `customer_enrichment_metrics`.

## Enrichment Outputs

- `customer_enrichment_metrics`: daily CLV, product adoption, engagement, support
  health, renewal probability, and supporting metric components by golden customer.

## Survivorship Rules

Golden-record generation chooses field winners by valid value, source priority, data
quality score, completeness score, recency, and deterministic source ID tie-breakers.
Company name, email, phone, and address winners are recorded in the
`survivorship_rules` variant column for auditability.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
