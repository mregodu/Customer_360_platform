# ingestion

Ingestion module for source extraction, CDC, and bronze loading.

## Framework Components

- `sources.py`: CSV and API extractors with incremental filtering and pagination support.
- `service.py`: batch orchestration, retry handling, logging, audit-field enrichment, bronze loads,
  and watermark updates.
- `watermarks.py`: watermark store protocol plus an in-memory implementation for tests/local use.
- `factory.py`: builds the production service from validated YAML configuration.

Configured source systems:

- Salesforce
- Marketo
- Zendesk
- Product Usage Data
- Licensing System
- Impartner

Production runs should use `build_ingestion_service(settings)` and call
`ingest_source("<source_name>")` or `ingest_all()`. Source definitions, target bronze tables,
batch sizes, retry policy, CSV paths, API endpoints, and API credentials are controlled in
`configs/*.yaml`.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
