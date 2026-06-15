# dags

Production Airflow DAG definitions. DAGs should orchestrate work and call package/dbt commands rather than contain business logic.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
