# docker

Container runtime helper scripts for the Customer 360 platform.

## Assets

- `airflow-init.sh`: runs Airflow metadata migrations, creates the admin user
  idempotently, and validates the metadata database.

## Engineering Notes

- Keep scripts idempotent so containers can restart safely.
- Avoid secrets and production customer data.
- Prefer environment variables over hardcoded deployment values.
