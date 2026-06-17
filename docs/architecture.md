# Architecture

The platform uses layered data engineering architecture:

1. Source systems publish customer data.
2. Landing receives raw extracts.
3. Bronze stores source data exactly as received plus audit metadata.
4. Silver standardizes names, emails, phones, addresses, and source-specific fields.
5. Splink creates match probabilities, cluster IDs, and confidence scores.
6. Gold stores golden customer master records.
7. Enrichment computes CLV, engagement, adoption, and renewal metrics.
8. Analytics exposes curated reporting tables for Domo.

Python code follows clean architecture. Domain rules do not import Snowflake, Airflow, Domo, Splink, or Great Expectations directly.

For the complete production deployment view, see `final_architecture.md`.

Production deployments must pass:

```bash
customer360 readiness --environment prod --strict
```

The readiness gate validates scalability, security, performance, maintainability,
and observability controls before production DAGs are enabled.
