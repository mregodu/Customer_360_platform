"""Apache Airflow DAGs for the Customer 360 platform.

The DAGs orchestrate package-level runtime jobs and keep transformations in
`src/customer360`, SQL, dbt, and Snowflake adapters. They are safe to parse
without source-system secrets; full platform configuration is loaded only when
tasks execute.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import pendulum
import yaml
from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.task_group import TaskGroup

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from customer360.interfaces.airflow.jobs import (  # noqa: E402
    DOMO_DATASET_TABLES,
    INGESTION_SOURCES,
    notify_airflow_event,
    publish_domo_dataset,
    run_customer_enrichment,
    run_customer_health_scoring,
    run_customer_matching,
    run_data_quality_validations,
    run_golden_customer_master,
    run_healthcheck,
    run_ingestion_source,
    run_silver_standardization_source,
    run_sql_script,
)

DAG_IDS = (
    "customer_ingestion_dag",
    "customer_standardization_dag",
    "customer_matching_dag",
    "customer_enrichment_dag",
    "customer_scoring_dag",
    "dashboard_refresh_dag",
)


def _airflow_config() -> dict[str, Any]:
    environment = os.getenv("CUSTOMER360_ENV", "dev")
    config_path = Path(os.getenv("CUSTOMER360_CONFIG_PATH", REPO_ROOT / "configs" / f"{environment}.yaml"))
    if not config_path.exists():
        return {}
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    airflow_config = payload.get("airflow")
    return dict(airflow_config) if isinstance(airflow_config, dict) else {}


AIRFLOW_CONFIG = _airflow_config()
AIRFLOW_DAGS = dict(AIRFLOW_CONFIG.get("dags") or {})
TIMEZONE = str(AIRFLOW_CONFIG.get("schedule_timezone") or "UTC")
START_DATE = pendulum.datetime(2026, 1, 1, tz=TIMEZONE)
OWNER = str(AIRFLOW_CONFIG.get("dag_owner") or "customer360-data-engineering")
RETRIES = int(AIRFLOW_CONFIG.get("retries", 1))
RETRY_DELAY = timedelta(minutes=int(AIRFLOW_CONFIG.get("retry_delay_minutes", 5)))
MAX_ACTIVE_RUNS = int(AIRFLOW_CONFIG.get("max_active_runs", 1))
CATCHUP = bool(AIRFLOW_CONFIG.get("catchup", False))
EMAIL_ON_FAILURE = bool(AIRFLOW_CONFIG.get("email_on_failure", False))
DEFAULT_POOL = str(AIRFLOW_CONFIG.get("default_pool") or "default_pool")
ALERT_EMAILS = [email.strip() for email in os.getenv("CUSTOMER360_ALERT_EMAILS", "").split(",") if email.strip()]

DEFAULT_ARGS = {
    "owner": OWNER,
    "depends_on_past": False,
    "email": ALERT_EMAILS,
    "email_on_failure": EMAIL_ON_FAILURE,
    "email_on_retry": False,
    "retries": RETRIES,
    "retry_delay": RETRY_DELAY,
    "sla": timedelta(hours=2),
    "on_failure_callback": lambda context: notify_airflow_event("failure", context),
    "on_retry_callback": lambda context: notify_airflow_event("retry", context),
}


def _dag_kwargs(dag_id: str, *, schedule_fallback: str) -> dict[str, Any]:
    dag_config = dict(AIRFLOW_DAGS.get(dag_id) or {})
    enabled = bool(dag_config.get("enabled", True))
    schedule = dag_config.get("schedule") or schedule_fallback
    return {
        "dag_id": dag_id,
        "default_args": DEFAULT_ARGS,
        "start_date": START_DATE,
        "schedule": schedule if enabled else None,
        "catchup": CATCHUP,
        "max_active_runs": MAX_ACTIVE_RUNS,
        "sla_miss_callback": _sla_miss_callback,
        "tags": ["customer360", _dag_tag(dag_id)],
    }


def _dag_tag(dag_id: str) -> str:
    return dag_id.replace("customer_", "").replace("_dag", "")


def _sla_miss_callback(
    dag: Any,
    task_list: str,
    blocking_task_list: str,
    slas: list[Any],
    blocking_tis: list[Any],
) -> None:
    notify_airflow_event(
        "sla_miss",
        {
            "dag": dag,
            "task_instance": blocking_tis[0] if blocking_tis else None,
            "task_list": task_list,
            "blocking_task_list": blocking_task_list,
            "slas": slas,
        },
    )


def _python_task(
    *,
    task_id: str,
    python_callable: Any,
    op_kwargs: dict[str, Any] | None = None,
    execution_timeout: timedelta | None = None,
    sla: timedelta | None = None,
) -> PythonOperator:
    return PythonOperator(
        task_id=task_id,
        python_callable=python_callable,
        op_kwargs=op_kwargs or {},
        pool=DEFAULT_POOL,
        execution_timeout=execution_timeout or timedelta(hours=1),
        sla=sla or timedelta(hours=2),
    )


def _wait_for_dag(external_dag_id: str, external_task_id: str) -> ExternalTaskSensor:
    return ExternalTaskSensor(
        task_id=f"wait_for_{external_dag_id}",
        external_dag_id=external_dag_id,
        external_task_id=external_task_id,
        allowed_states=["success"],
        failed_states=["failed", "skipped"],
        mode="reschedule",
        poke_interval=300,
        timeout=timedelta(hours=6).total_seconds(),
        pool=DEFAULT_POOL,
    )


with DAG(**_dag_kwargs("customer_ingestion_dag", schedule_fallback="@hourly")) as customer_ingestion_dag:
    validate_config = _python_task(task_id="validate_runtime_config", python_callable=run_healthcheck)

    with TaskGroup(group_id="ingest_sources") as ingest_sources:
        for source_name in INGESTION_SOURCES:
            _python_task(
                task_id=f"ingest_{source_name}",
                python_callable=run_ingestion_source,
                op_kwargs={"source_name": source_name},
                execution_timeout=timedelta(hours=2),
                sla=timedelta(hours=3),
            )

    ingestion_complete = EmptyOperator(task_id="ingestion_complete")

    validate_config >> ingest_sources >> ingestion_complete


with DAG(
    **_dag_kwargs("customer_standardization_dag", schedule_fallback="@hourly")
) as customer_standardization_dag:
    wait_for_ingestion = _wait_for_dag("customer_ingestion_dag", "ingestion_complete")

    with TaskGroup(group_id="standardize_sources") as standardize_sources:
        for source_name in INGESTION_SOURCES:
            _python_task(
                task_id=f"standardize_{source_name}",
                python_callable=run_silver_standardization_source,
                op_kwargs={"source_name": source_name},
                execution_timeout=timedelta(hours=2),
                sla=timedelta(hours=3),
            )

    validate_silver = _python_task(
        task_id="validate_silver_quality",
        python_callable=run_data_quality_validations,
        op_kwargs={"target_group": "silver"},
        execution_timeout=timedelta(hours=1),
    )
    standardization_complete = EmptyOperator(task_id="standardization_complete")

    wait_for_ingestion >> standardize_sources >> validate_silver >> standardization_complete


with DAG(**_dag_kwargs("customer_matching_dag", schedule_fallback="0 2 * * *")) as customer_matching_dag:
    wait_for_standardization = _wait_for_dag(
        "customer_standardization_dag",
        "standardization_complete",
    )
    generate_clusters = _python_task(
        task_id="generate_gold_customer_clusters",
        python_callable=run_customer_matching,
        execution_timeout=timedelta(hours=3),
        sla=timedelta(hours=4),
    )
    generate_master = _python_task(
        task_id="generate_gold_customer_master",
        python_callable=run_golden_customer_master,
        execution_timeout=timedelta(hours=2),
        sla=timedelta(hours=3),
    )
    validate_gold = _python_task(
        task_id="validate_gold_quality",
        python_callable=run_data_quality_validations,
        op_kwargs={"target_group": "gold"},
    )
    matching_complete = EmptyOperator(task_id="matching_complete")

    wait_for_standardization >> generate_clusters >> generate_master >> validate_gold >> matching_complete


with DAG(
    **_dag_kwargs("customer_enrichment_dag", schedule_fallback="0 3 * * *")
) as customer_enrichment_dag:
    wait_for_matching = _wait_for_dag("customer_matching_dag", "matching_complete")
    generate_enrichment = _python_task(
        task_id="generate_customer_enrichment_metrics",
        python_callable=run_customer_enrichment,
        execution_timeout=timedelta(hours=2),
        sla=timedelta(hours=3),
    )
    validate_enrichment = _python_task(
        task_id="validate_enrichment_quality",
        python_callable=run_data_quality_validations,
        op_kwargs={"target_group": "enrichment"},
    )
    enrichment_complete = EmptyOperator(task_id="enrichment_complete")

    wait_for_matching >> generate_enrichment >> validate_enrichment >> enrichment_complete


with DAG(**_dag_kwargs("customer_scoring_dag", schedule_fallback="30 3 * * *")) as customer_scoring_dag:
    wait_for_enrichment = _wait_for_dag("customer_enrichment_dag", "enrichment_complete")
    build_features = _python_task(
        task_id="build_customer_health_features",
        python_callable=run_sql_script,
        op_kwargs={
            "script_path": "sql/analytics/002_build_customer_health_features.sql",
            "pipeline_name": "customer_health_feature_build",
            "step_name": "merge_customer_health_features",
        },
        execution_timeout=timedelta(hours=1),
    )
    score_customers = _python_task(
        task_id="score_customer_health",
        python_callable=run_customer_health_scoring,
        execution_timeout=timedelta(hours=3),
        sla=timedelta(hours=4),
    )
    validate_scoring = _python_task(
        task_id="validate_customer_health_scores",
        python_callable=run_data_quality_validations,
        op_kwargs={"target_group": "scoring"},
    )
    scoring_complete = EmptyOperator(task_id="scoring_complete")

    wait_for_enrichment >> build_features >> score_customers >> validate_scoring >> scoring_complete


with DAG(**_dag_kwargs("dashboard_refresh_dag", schedule_fallback="0 4 * * *")) as dashboard_refresh_dag:
    wait_for_scoring = _wait_for_dag("customer_scoring_dag", "scoring_complete")
    build_quality_dashboard = _python_task(
        task_id="build_data_quality_dashboard_daily",
        python_callable=run_sql_script,
        op_kwargs={
            "script_path": "sql/analytics/006_build_data_quality_dashboard_daily.sql",
            "pipeline_name": "dashboard_refresh",
            "step_name": "merge_data_quality_dashboard_daily",
        },
        execution_timeout=timedelta(hours=1),
    )
    build_domo_reporting_layer = _python_task(
        task_id="build_domo_reporting_layer",
        python_callable=run_sql_script,
        op_kwargs={
            "script_path": "sql/analytics/008_build_domo_reporting_layer.sql",
            "pipeline_name": "dashboard_refresh",
            "step_name": "merge_domo_reporting_layer",
        },
        execution_timeout=timedelta(hours=1),
    )

    with TaskGroup(group_id="publish_domo_datasets") as publish_domo_datasets:
        for dataset_name, table_name in DOMO_DATASET_TABLES.items():
            _python_task(
                task_id=f"publish_{dataset_name}",
                python_callable=publish_domo_dataset,
                op_kwargs={"dataset_name": dataset_name, "table_name": table_name},
                execution_timeout=timedelta(hours=1),
                sla=timedelta(hours=2),
            )

    dashboard_refresh_complete = EmptyOperator(task_id="dashboard_refresh_complete")

    wait_for_scoring >> build_quality_dashboard >> build_domo_reporting_layer >> publish_domo_datasets >> dashboard_refresh_complete
