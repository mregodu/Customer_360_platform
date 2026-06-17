# tests

Unit, integration, and fixture tests that protect platform behavior.

## Test Commands

Install development dependencies first:

```bash
python -m pip install -e .
```

Run the complete suite with the configured coverage gate:

```bash
python -m pytest
```

Run only fast unit tests:

```bash
python -m pytest -o addopts='' tests/unit
```

Run integration tests without external credentials:

```bash
python -m pytest -o addopts='' tests/integration
```

The project coverage target is 80% or higher for `src/customer360`. CI enforces this
with `pytest-cov`; local interpreters without `pytest-cov` can use `-o addopts=''`
for quick behavior checks.

## Coverage Scope

- Unit tests cover ingestion, cleansing, matching, enrichment, classification, config,
  audit logging, Great Expectations, Airflow task registry, and Domo publishing behavior.
- Integration tests validate Snowflake adapter SQL generation, commits, rollbacks,
  data fetching, watermarking, and script execution with fake Snowflake connections.
- Live Snowflake credentials are intentionally not required for default CI.

## Why This Folder Exists

- Makes ownership clear as the Customer 360 platform grows.
- Keeps orchestration, transformation, domain logic, infrastructure adapters, documentation, and tests separated.
- Helps engineers find the right place for new production assets without guessing.

## Operating Rules

- Keep files cohesive with this folder's responsibility.
- Do not commit secrets or production customer data.
- Prefer small, reviewed changes with tests, validation, or clear run notes.
