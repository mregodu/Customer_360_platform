# gold

Snowflake DDL for golden customer master and entity-resolution output tables.

Gold includes Splink match predictions, customer clusters, source-to-golden identity mapping,
golden customer master records, and enrichment metrics.

## Matching Outputs

- `customer_match_predictions`: pairwise Splink match probabilities and comparison vectors.
- `gold_customer_clusters`: final cluster output consumed by golden-record generation.
- `002_merge_gold_customer_clusters.sql`: merges staged cluster rows into the gold output table.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
