# Containerized Deployment

The Customer 360 platform runs from one application image and a Docker Compose
stack for local, development, and small production-style deployments.

## Services

| Service | Purpose |
| --- | --- |
| `customer360-cli` | One-shot platform CLI and healthcheck container. |
| `airflow-postgres` | Airflow metadata database. |
| `airflow-redis` | Celery broker for distributed Airflow task execution. |
| `airflow-init` | Runs Airflow database migrations and creates the admin user. |
| `airflow-webserver` | Airflow UI on `AIRFLOW_WEBSERVER_PORT`, default `8080`. |
| `airflow-scheduler` | Parses DAGs and schedules Customer 360 workflows. |
| `airflow-worker` | Executes Airflow tasks with `CeleryExecutor`. |
| `airflow-triggerer` | Runs deferrable Airflow triggers and async sensors. |

## First Run

```bash
cp .env.example .env
docker compose build
docker compose up airflow-init
docker compose up -d airflow-webserver airflow-scheduler airflow-worker airflow-triggerer
```

Open Airflow at `http://localhost:8080` and sign in with the admin credentials
from `.env`.

For a quick image-level validation:

```bash
docker compose --profile tools run --rm customer360-cli customer360 healthcheck
docker compose --profile tools run --rm customer360-cli customer360 readiness --environment dev
```

## Snowflake Connectivity

The containers read Snowflake settings from `.env`, and the validated YAML config
uses those variables at runtime.

Required Snowflake variables:

```text
SNOWFLAKE_ACCOUNT
SNOWFLAKE_USER
SNOWFLAKE_PASSWORD
SNOWFLAKE_ROLE
SNOWFLAKE_WAREHOUSE
```

Use a least-privilege Snowflake service user. For production, set `CUSTOMER360_ENV=prod`
and provide all source-system API and Domo secrets in the deployment environment or
secret manager.

## Environment Management

- `.env.example` is committed as a template.
- `.env` and `.env.*` are ignored and must not be committed.
- `CUSTOMER360_ENV` selects `configs/<env>.yaml` inside the container.
- `CUSTOMER360_DOMO_DRY_RUN=true` prevents Domo writes until dataset IDs are configured.
- Raw and processed local data are mounted from `data/raw` and `data/processed`.
- Airflow logs and metadata are stored in Docker named volumes.

## Operations

Useful commands:

```bash
docker compose ps
docker compose logs -f airflow-scheduler
docker compose logs -f airflow-worker
docker compose exec airflow-webserver airflow dags list
docker compose down
docker compose down -v
```

Use `docker compose down -v` only when you intentionally want to remove the Airflow
metadata database and logs.

## Production Notes

- Override the development Fernet key, Airflow admin password, Postgres password,
  Snowflake password, source API tokens, and Domo credentials with secrets.
- Keep `AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true`; unpause DAGs deliberately
  after Snowflake schemas and Domo datasets are ready.
- Scale workers with `docker compose up -d --scale airflow-worker=3 airflow-worker`
  when ingestion, matching, or scoring workloads need more execution capacity.
- Run `customer360 readiness --environment prod --strict` in the container before
  enabling production DAG schedules.
- For larger deployments, use the same image in Kubernetes, ECS, or managed Airflow
  and map the environment variables documented above through the platform secret store.
