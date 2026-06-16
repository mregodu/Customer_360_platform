# cleansing

Cleansing module for standardization and silver-layer normalization rules.

## Silver Transformation Components

- `standardizers.py`: deterministic formatting for names, company names, emails, phones,
  addresses, states, countries, and website domains.
- `validation.py`: Silver validation rules and aggregate data-quality metrics.
- `transformations.py`: source-aware bronze-to-silver transformation functions.
- `pipeline.py`: reusable orchestration for bronze reads, transformation, Silver merges, and
  quality metric publishing.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
