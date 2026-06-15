"""Airflow DAG definitions for Customer 360.

These DAGs are intentionally thin: they orchestrate work but keep business logic
inside `src/customer360` so jobs remain testable outside Airflow.
"""

from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

DEFAULT_ARGS = {"owner": "customer360-data-engineering", "depends_on_past": False, "retries": 1}

with DAG(
    dag_id="customer_ingestion_dag",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 1, 1),
    schedule="@hourly",
    catchup=False,
    tags=["customer360", "bronze"],
) as customer_ingestion_dag:
    BashOperator(task_id="extract_and_load_bronze", bash_command="customer360 healthcheck")

with DAG(
    dag_id="customer_standardization_dag",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 1, 1),
    schedule="@hourly",
    catchup=False,
    tags=["customer360", "silver", "dbt"],
) as customer_standardization_dag:
    BashOperator(task_id="bronze_to_silver", bash_command="dbt run --project-dir dbt/customer360 --select silver")

with DAG(
    dag_id="customer_matching_dag",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["customer360", "matching", "gold"],
) as customer_matching_dag:
    BashOperator(task_id="run_splink_matching", bash_command="customer360 healthcheck")
    BashOperator(task_id="generate_golden_records", bash_command="dbt run --project-dir dbt/customer360 --select gold")

with DAG(
    dag_id="customer_enrichment_dag",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["customer360", "enrichment", "classification"],
) as customer_enrichment_dag:
    BashOperator(task_id="run_enrichment", bash_command="dbt run --project-dir dbt/customer360 --select analytics")
    BashOperator(task_id="run_classification", bash_command="customer360 healthcheck")

with DAG(
    dag_id="dashboard_refresh_dag",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["customer360", "domo"],
) as dashboard_refresh_dag:
    BashOperator(task_id="publish_domo_datasets", bash_command="customer360 healthcheck")
