# bronze

Snowflake DDL for raw ingested bronze tables.

Bronze tables stay source-shaped and retain raw payloads plus audit metadata. Downstream jobs
should use `load_batch_id`, `load_timestamp`, `record_hash`, and `last_modified_timestamp` for
incremental merges and reconciliation.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
