# Production Hardening Review

This review covers scalability, security, performance, maintainability, and
observability for the Customer 360 platform.

## Executive Summary

The platform has the core production building blocks in place: layered Snowflake
schemas, validated configuration, Airflow orchestration, audit tables, Great
Expectations, Domo publishing, Docker Compose infrastructure, CI/CD, and a broad
pytest suite. This hardening phase adds a deployment-ready readiness gate so
misconfiguration can be detected before production DAGs run.

Implemented in this phase:

- `customer360 readiness` CLI for production readiness validation.
- Config-driven checks for security, scale, performance, maintainability, and
  observability.
- CI readiness execution in the integration job.
- Final architecture documentation.

## Scalability

Current strengths:

- Snowflake workloads are separated by warehouse purpose: ingestion, transform,
  matching, and reporting.
- Airflow DAGs are split by pipeline phase and use cross-DAG dependencies.
- Dashboard datasets are pre-aggregated to reduce Domo query pressure.
- Splink matching threshold, blocking rules, and batch sizes are configuration-driven.

Implemented controls:

- Readiness checks verify production batch size, retry attempts, bounded Airflow
  `max_active_runs`, and matching threshold.

Recommendations:

- Add warehouse auto-scaling policies by environment after production query history
  is available.
- Introduce dynamic tables or materialized views only for repeated high-cost Domo
  cards.
- Partition heavy matching jobs by blocking key when source volume grows beyond a
  single matching warehouse SLA.

## Security

Current strengths:

- Secrets are externalized through environment variables and `.env` is ignored.
- Snowflake security roles and masking policies are defined in SQL.
- Domo publishing requires dataset IDs and supports dry-run operation.
- Docker runtime uses a non-root Airflow user.

Implemented controls:

- Readiness checks fail production when Snowflake authentication is missing.
- Production readiness rejects known development placeholder credentials.
- Production API sources must use HTTPS and authentication tokens.
- Production Domo dry-run mode is treated as a deployment blocker.

Recommendations:

- Use key-pair or external browser/service principal authentication for Snowflake
  production service users instead of passwords when the enterprise identity model
  is ready.
- Move Airflow admin credentials, Fernet key, Snowflake credentials, source tokens,
  and Domo secrets to a managed secret store.
- Require GitHub environment approvals for production deployment.

## Performance

Current strengths:

- Snowflake DDL uses clustering on high-value dashboard, matching, and metric keys.
- Analytics tables are daily snapshots and drill datasets instead of runtime joins.
- API ingestion uses configurable batch sizes and retry policy.
- Docker and CI builds use a single package install path.

Implemented controls:

- Readiness checks validate Snowflake query timeout, login timeout, and Splink
  iteration budget.

Recommendations:

- Review Snowflake query history after the first two production runs and tune
  clustering keys with measured scan patterns.
- Add performance budgets to CI for pure-Python matching and enrichment fixtures.
- Track Airflow task duration percentiles by DAG and task.

## Maintainability

Current strengths:

- Python modules follow clean architecture boundaries.
- SQL is organized by warehouse layer and execution phase.
- dbt models encode lineage for bronze, silver, gold, analytics, and exposures.
- Tests cover unit and integration behavior without live external credentials.

Implemented controls:

- Readiness checks ensure all required source systems and DAGs are configured and
  enabled.
- Final architecture documentation now centralizes the deployment view.

Recommendations:

- Add pull request templates that require migration, data-quality, and rollback notes.
- Add ownership metadata for each DAG, dataset, and dashboard contract.
- Version public Analytics dataset contracts once Domo cards are connected.

## Observability

Current strengths:

- Pipeline execution and ETL audit tables track runs, status, row counts, and errors.
- Great Expectations emits metrics, validation runs, alerts, and dashboard tables.
- Airflow callbacks emit failure, retry, and SLA miss notifications.
- Domo dataset refreshes are audited.

Implemented controls:

- Readiness checks validate structured logging, JSON rendering, audit history, Analytics
  audit-table placement, and production failure alert configuration.

Recommendations:

- Publish audit and data-quality metrics to a central observability platform.
- Add Domo cards for pipeline freshness, failed DAG runs, and Domo refresh latency.
- Configure alert routing for data-quality critical failures and SLA misses.

## Required Pre-Production Gates

Run these before enabling production DAGs:

```bash
customer360 healthcheck
customer360 readiness --environment prod --strict
python -m pytest
dbt parse --project-dir dbt/customer360 --profiles-dir dbt/customer360 --target prod
docker compose config
```

The readiness command is intentionally config-driven and safe to run without connecting
to Snowflake, Domo, or source APIs.
