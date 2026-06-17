#!/usr/bin/env bash
set -euo pipefail

required_vars=(
  AIRFLOW_ADMIN_USERNAME
  AIRFLOW_ADMIN_PASSWORD
  AIRFLOW_ADMIN_FIRSTNAME
  AIRFLOW_ADMIN_LASTNAME
  AIRFLOW_ADMIN_EMAIL
)

for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing required environment variable: ${var_name}" >&2
    exit 1
  fi
done

airflow db migrate

if airflow users list | awk 'NR > 2 {print $2}' | grep -qx "${AIRFLOW_ADMIN_USERNAME}"; then
  echo "Airflow admin user ${AIRFLOW_ADMIN_USERNAME} already exists."
else
  airflow users create \
    --username "${AIRFLOW_ADMIN_USERNAME}" \
    --password "${AIRFLOW_ADMIN_PASSWORD}" \
    --firstname "${AIRFLOW_ADMIN_FIRSTNAME}" \
    --lastname "${AIRFLOW_ADMIN_LASTNAME}" \
    --role Admin \
    --email "${AIRFLOW_ADMIN_EMAIL}"
fi

airflow db check
