# matching

Matching module for Splink orchestration and customer cluster generation.

## Components

- `settings.py`: builds production Splink settings for company name, email, phone,
  website domain, and address matching.
- `scoring.py`: calculates pairwise match probability, comparison vectors, and confidence scores.
- `clustering.py`: turns pairwise predictions into deterministic `gold_customer_clusters` rows.
- `service.py`: application-level matching orchestration.

The checked-in Splink configuration lives at `configs/splink_customer_matching.yaml`.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
