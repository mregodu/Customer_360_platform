# integration

Integration tests for external adapters, dbt, Airflow DAG imports, and warehouse contracts.

## Default Integration Strategy

Integration tests must run in CI without production credentials. Use in-memory fakes,
temporary files, and adapter contract tests by default. Live-system tests should be
opt-in through explicit markers and environment variables.

Current Snowflake integration tests verify:

- Bronze insert SQL and variant serialization.
- Merge SQL generation for Silver and Analytics writers.
- Query result mapping and limit handling.
- Watermark reads and merge parameters.
- Script execution order, commits, and rollback behavior.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
