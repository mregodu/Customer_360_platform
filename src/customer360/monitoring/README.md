# monitoring

Monitoring module for lineage, freshness, data quality, audit, and operational metrics.

- `audit.py`: reusable enterprise audit framework for pipeline execution and ETL
  step logs.
- `lineage.py`: lightweight source-to-target lineage event model.

`AuditLogger.start_pipeline(...)` can be used as a context manager to capture
pipeline name, run ID, start/end time, status, error details, and row counts.
Step-level ETL events are written with `record_step(...)`.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
