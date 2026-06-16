"""Reusable Airflow task callables for Customer 360 DAGs.

The functions in this module are intentionally Airflow-light. They accept the
standard Airflow context as keyword arguments, but keep business logic in the
Customer 360 services and infrastructure adapters.
"""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from customer360.classification.models import HealthModelAlgorithm
from customer360.classification.prediction import CustomerHealthPredictionPipeline
from customer360.classification.training import CustomerHealthTrainingPipeline, HealthTrainingResult
from customer360.cleansing.pipeline import (
    SilverPipelineResult,
    SilverTransformationPipeline,
    default_silver_source_mappings,
)
from customer360.config import Customer360Config, load_settings
from customer360.domain.customer import SourceCustomerRecord
from customer360.enrichment.pipeline import CustomerEnrichmentPipeline
from customer360.golden.service import GoldenRecordService
from customer360.infrastructure.domo import DomoPublisher
from customer360.infrastructure.great_expectations import (
    GreatExpectationsRunner,
    GreatExpectationsValidationPipeline,
    TableValidationConfig,
)
from customer360.infrastructure.snowflake import (
    SnowflakeAuditLogWriter,
    SnowflakeBronzeReader,
    SnowflakeCustomerEnrichmentWriter,
    SnowflakeCustomerHealthScoringWriter,
    SnowflakeDataQualityWriter,
    SnowflakeGoldenRecordWriter,
    SnowflakeGoldMatchingWriter,
    SnowflakeSilverWriter,
    SnowflakeSqlScriptRunner,
    SnowflakeTableDataProvider,
)
from customer360.infrastructure.splink_engine import SplinkEntityResolutionEngine
from customer360.ingestion.factory import build_ingestion_service
from customer360.logging import configure_logging
from customer360.monitoring.audit import AuditLogger

LOGGER = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[4]

INGESTION_SOURCES = (
    "salesforce",
    "marketo",
    "zendesk",
    "product_usage",
    "licensing",
    "impartner",
)

DOMO_DATASET_TABLES = {
    "customer_health_scores": "ANALYTICS.customer_health_scores",
    "executive_customer_kpis_daily": "ANALYTICS.executive_customer_kpis_daily",
    "customer_success_account_daily": "ANALYTICS.customer_success_account_daily",
    "partner_performance_daily": "ANALYTICS.partner_performance_daily",
    "data_quality_dashboard_daily": "ANALYTICS.data_quality_dashboard_daily",
}


def run_healthcheck(**context: object) -> dict[str, object]:
    """Validate package import and configuration loading from an Airflow task."""
    settings = _load_runtime_settings()
    return {
        "run_id": _airflow_run_id(context),
        "environment": settings.environment,
        "database": settings.snowflake.database,
    }


def run_ingestion_source(source_name: str, **context: object) -> dict[str, object]:
    """Run incremental extraction and Bronze loading for one configured source."""
    settings = _load_runtime_settings()
    audit = _audit_logger(settings)
    service = build_ingestion_service(settings)
    run_id = _airflow_run_id(context)

    source_config = settings.ingestion.sources[source_name]
    with audit.start_pipeline(
        "customer_ingestion",
        run_id=run_id,
        source_system=source_config.source_system,
        target_table=source_config.target_table,
        metadata={"source_name": source_name, "source_object": source_config.source_object},
    ) as pipeline_audit:
        result = service.ingest_source(source_name)
        pipeline_audit.add_rows(
            rows_read=result.rows_extracted,
            rows_inserted=result.rows_loaded,
        )
        pipeline_audit.record_step(
            f"extract_load_{source_name}",
            source_table=f"{source_config.source_system}.{source_config.source_object}",
            destination_table=source_config.target_table,
            row_count=result.rows_loaded,
            details=_json_mapping(asdict(result)),
        )
    return _json_mapping(asdict(result))


def run_silver_standardization_source(
    source_name: str,
    since_watermark: str | None = None,
    **context: object,
) -> dict[str, object]:
    """Run Bronze-to-Silver transformation for one source."""
    settings = _load_runtime_settings()
    database_name = settings.snowflake.database
    audit = _audit_logger(settings)
    reader = SnowflakeBronzeReader(settings.snowflake.connection_parameters())
    writer = SnowflakeSilverWriter(
        settings.snowflake.connection_parameters(),
        database_name=database_name,
    )
    pipeline = SilverTransformationPipeline(
        mappings=default_silver_source_mappings(database_name),
        reader=reader,
        writer=writer,
    )
    mapping = default_silver_source_mappings(database_name)[source_name]
    run_id = _airflow_run_id(context)

    with audit.start_pipeline(
        "customer_standardization",
        run_id=run_id,
        source_system=mapping.source_system,
        target_table=f"{database_name}.SILVER.silver_customer",
        metadata={"source_name": source_name, "since_watermark": since_watermark},
    ) as pipeline_audit:
        result = pipeline.run_source(source_name, since_watermark=since_watermark)
        rows_written = result.customers_merged + result.metrics_merged + result.partners_merged
        pipeline_audit.add_rows(
            rows_read=result.bronze_rows_read,
            rows_inserted=rows_written,
        )
        pipeline_audit.record_step(
            f"standardize_{source_name}",
            source_table=mapping.bronze_table,
            destination_table=f"{database_name}.SILVER",
            row_count=rows_written,
            details=_json_mapping(asdict(result)),
        )
    return _silver_result_to_row(result)


def run_customer_matching(**context: object) -> dict[str, object]:
    """Run Splink-style matching and write Gold customer clusters."""
    settings = _load_runtime_settings()
    database_name = settings.snowflake.database
    run_id = _airflow_run_id(context)
    audit = _audit_logger(settings)
    reader = _table_reader(settings)
    writer = SnowflakeGoldMatchingWriter(
        settings.snowflake.connection_parameters(),
        database_name=database_name,
    )

    with audit.start_pipeline(
        "customer_matching",
        run_id=run_id,
        source_system="SILVER",
        target_table=f"{database_name}.GOLD.gold_customer_clusters",
    ) as pipeline_audit:
        rows = reader.fetch_table(f"{database_name}.SILVER.silver_customer")
        records = tuple(_source_customer_record(row) for row in rows)
        engine = SplinkEntityResolutionEngine(
            splink_config=settings.splink,
            match_threshold=settings.pipeline.matching_threshold,
        )
        predictions = engine.predict_matches(records)
        prediction_rows = [prediction.to_row(load_batch_id=run_id) for prediction in predictions]
        clusters = engine.generate_clusters(records, predictions, load_batch_id=run_id)
        predictions_written = writer.write_predictions(prediction_rows)
        clusters_written = writer.write_clusters(clusters)

        pipeline_audit.add_rows(
            rows_read=len(rows),
            rows_inserted=predictions_written + clusters_written,
        )
        pipeline_audit.record_step(
            "generate_match_predictions",
            source_table=f"{database_name}.SILVER.silver_customer",
            destination_table=f"{database_name}.GOLD.customer_match_predictions",
            row_count=predictions_written,
            details={"records_read": len(records)},
        )
        pipeline_audit.record_step(
            "generate_gold_customer_clusters",
            source_table=f"{database_name}.GOLD.customer_match_predictions",
            destination_table=f"{database_name}.GOLD.gold_customer_clusters",
            row_count=clusters_written,
            details={"clusters_generated": len(clusters)},
        )

    return {
        "run_id": run_id,
        "silver_rows_read": len(rows),
        "match_predictions_written": predictions_written,
        "clusters_written": clusters_written,
    }


def run_golden_customer_master(**context: object) -> dict[str, object]:
    """Generate trusted Golden Customer records with survivorship rules."""
    settings = _load_runtime_settings()
    database_name = settings.snowflake.database
    run_id = _airflow_run_id(context)
    audit = _audit_logger(settings)
    reader = _table_reader(settings)
    writer = SnowflakeGoldenRecordWriter(
        settings.snowflake.connection_parameters(),
        database_name=database_name,
    )
    service = GoldenRecordService(writer=writer)

    with audit.start_pipeline(
        "golden_customer_master",
        run_id=run_id,
        source_system="GOLD",
        target_table=f"{database_name}.GOLD.gold_customer_master",
    ) as pipeline_audit:
        clusters = reader.fetch_table(f"{database_name}.GOLD.gold_customer_clusters")
        silver_records = reader.fetch_table(f"{database_name}.SILVER.silver_customer")
        written = service.generate_and_write(
            clusters,
            silver_records,
            load_batch_id=run_id,
        )
        pipeline_audit.add_rows(
            rows_read=len(clusters) + len(silver_records),
            rows_inserted=written,
        )
        pipeline_audit.record_step(
            "apply_survivorship_rules",
            source_table=f"{database_name}.GOLD.gold_customer_clusters",
            destination_table=f"{database_name}.GOLD.gold_customer_master",
            row_count=written,
            details={
                "clusters_read": len(clusters),
                "silver_records_read": len(silver_records),
            },
        )

    return {
        "run_id": run_id,
        "clusters_read": len(clusters),
        "silver_records_read": len(silver_records),
        "golden_records_written": written,
    }


def run_customer_enrichment(**context: object) -> dict[str, object]:
    """Generate customer enrichment metrics from Gold clusters and Silver metrics."""
    settings = _load_runtime_settings()
    database_name = settings.snowflake.database
    run_id = _airflow_run_id(context)
    audit = _audit_logger(settings)
    reader = _table_reader(settings)
    writer = SnowflakeCustomerEnrichmentWriter(
        settings.snowflake.connection_parameters(),
        database_name=database_name,
    )
    pipeline = CustomerEnrichmentPipeline(writer=writer)

    with audit.start_pipeline(
        "customer_enrichment",
        run_id=run_id,
        source_system="GOLD",
        target_table=f"{database_name}.GOLD.customer_enrichment_metrics",
    ) as pipeline_audit:
        clusters = reader.fetch_table(f"{database_name}.GOLD.gold_customer_clusters")
        metric_records = reader.fetch_table(f"{database_name}.SILVER.silver_customer_metric_daily")
        result = pipeline.generate_and_write(
            clusters,
            metric_records,
            load_batch_id=run_id,
        )
        pipeline_audit.add_rows(
            rows_read=result.clusters_read + result.metric_rows_read,
            rows_inserted=result.enrichment_rows_written,
        )
        pipeline_audit.record_step(
            "calculate_customer_enrichment_metrics",
            source_table=f"{database_name}.SILVER.silver_customer_metric_daily",
            destination_table=f"{database_name}.GOLD.customer_enrichment_metrics",
            row_count=result.enrichment_rows_written,
            details=_json_mapping(asdict(result)),
        )

    return _json_mapping(asdict(result))


def run_customer_health_scoring(**context: object) -> dict[str, object]:
    """Train health scoring candidates, choose the best model, and persist predictions."""
    settings = _load_runtime_settings()
    database_name = settings.snowflake.database
    run_id = _airflow_run_id(context)
    audit = _audit_logger(settings)
    reader = _table_reader(settings)
    writer = SnowflakeCustomerHealthScoringWriter(
        settings.snowflake.connection_parameters(),
        database_name=database_name,
    )
    trainer = CustomerHealthTrainingPipeline()
    predictor = CustomerHealthPredictionPipeline(writer=writer)

    with audit.start_pipeline(
        "customer_health_scoring",
        run_id=run_id,
        source_system="ANALYTICS",
        target_table=f"{database_name}.ANALYTICS.customer_health_scores",
    ) as pipeline_audit:
        feature_rows = reader.fetch_table(f"{database_name}.ANALYTICS.customer_health_features")
        training_results = trainer.train_candidate_models(
            feature_rows,
            algorithms=(
                HealthModelAlgorithm.LOGISTIC_REGRESSION,
                HealthModelAlgorithm.RANDOM_FOREST,
                HealthModelAlgorithm.XGBOOST,
            ),
            skip_unavailable=True,
        )
        if not training_results:
            raise RuntimeError("No customer health models were trained successfully.")

        best_result = _best_health_model(training_results)
        evaluations_written = writer.write_model_evaluations(
            result.evaluation.to_row(load_batch_id=run_id) for result in training_results
        )
        prediction_result = predictor.predict_and_write(
            feature_rows,
            trained_model=best_result.trained_model,
            load_batch_id=run_id,
        )

        pipeline_audit.add_rows(
            rows_read=len(feature_rows),
            rows_inserted=prediction_result.rows_written + evaluations_written,
        )
        pipeline_audit.record_step(
            "train_customer_health_models",
            source_table=f"{database_name}.ANALYTICS.customer_health_features",
            destination_table=f"{database_name}.ANALYTICS.customer_health_model_evaluations",
            row_count=evaluations_written,
            details={
                "candidate_models": [result.trained_model.algorithm for result in training_results],
                "selected_model": best_result.trained_model.algorithm,
                "selected_macro_f1": best_result.evaluation.macro_f1,
            },
        )
        pipeline_audit.record_step(
            "predict_customer_health_scores",
            source_table=f"{database_name}.ANALYTICS.customer_health_features",
            destination_table=f"{database_name}.ANALYTICS.customer_health_scores",
            row_count=prediction_result.rows_written,
            details=_json_mapping(asdict(prediction_result)),
        )

    return {
        "run_id": run_id,
        "feature_rows_read": len(feature_rows),
        "candidate_models": len(training_results),
        "selected_model": best_result.trained_model.algorithm,
        "model_evaluations_written": evaluations_written,
        "health_scores_written": prediction_result.rows_written,
    }


def run_data_quality_validations(target_group: str, **context: object) -> dict[str, object]:
    """Run checked-in expectation suites for one pipeline stage."""
    settings = _load_runtime_settings()
    database_name = settings.snowflake.database
    run_id = _airflow_run_id(context)
    audit = _audit_logger(settings)
    reader = _table_reader(settings)
    writer = SnowflakeDataQualityWriter(
        settings.snowflake.connection_parameters(),
        database_name=database_name,
    )
    runner = GreatExpectationsRunner(data_provider=reader)
    pipeline = GreatExpectationsValidationPipeline(runner=runner, writer=writer)
    configs = _validation_configs(database_name, target_group)

    with audit.start_pipeline(
        "data_quality_validation",
        run_id=run_id,
        source_system=target_group.upper(),
        target_table=f"{database_name}.ANALYTICS.data_quality_metrics",
        metadata={"target_group": target_group},
    ) as pipeline_audit:
        result = pipeline.run(configs, run_id=run_id)
        rows_written = (
            result.metrics_written
            + result.run_summaries_written
            + result.alerts_written
        )
        pipeline_audit.add_rows(
            rows_read=sum(table_result.row_count for table_result in result.table_results),
            rows_inserted=rows_written,
        )
        pipeline_audit.record_step(
            f"validate_{target_group}",
            source_table=",".join(config.table_name for config in configs),
            destination_table=f"{database_name}.ANALYTICS.data_quality_metrics",
            row_count=rows_written,
            details={
                "success": result.success,
                "tables_validated": [config.table_name for config in configs],
            },
        )

    if not result.success:
        raise RuntimeError(f"Data quality validation failed for target_group={target_group}.")
    return {
        "run_id": run_id,
        "target_group": target_group,
        "success": result.success,
        "metrics_written": result.metrics_written,
        "run_summaries_written": result.run_summaries_written,
        "alerts_written": result.alerts_written,
    }


def run_sql_script(
    script_path: str,
    pipeline_name: str,
    step_name: str | None = None,
    **context: object,
) -> dict[str, object]:
    """Execute a checked-in SQL script through the Snowflake adapter."""
    settings = _load_runtime_settings()
    run_id = _airflow_run_id(context)
    audit = _audit_logger(settings)
    resolved_path = _repo_path(script_path)

    with audit.start_pipeline(
        pipeline_name,
        run_id=run_id,
        target_table=str(resolved_path),
        metadata={"script_path": script_path},
    ) as pipeline_audit:
        SnowflakeSqlScriptRunner(settings.snowflake.connection_parameters()).execute_sql(
            resolved_path.read_text(encoding="utf-8"),
        )
        pipeline_audit.record_step(
            step_name or resolved_path.stem,
            source_table=str(resolved_path),
            destination_table=settings.snowflake.database,
            row_count=0,
        )

    return {"run_id": run_id, "script_path": script_path, "status": "SUCCESS"}


def run_dbt_select(select: str, **context: object) -> dict[str, object]:
    """Run a dbt selection for Airflow orchestration tasks."""
    run_id = _airflow_run_id(context)
    command = [
        "dbt",
        "run",
        "--project-dir",
        "dbt/customer360",
        "--select",
        select,
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath_with_src(env.get("PYTHONPATH"))
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    LOGGER.info(
        "dbt_select_completed",
        extra={"run_id": run_id, "select": select, "stdout": completed.stdout[-4000:]},
    )
    return {"run_id": run_id, "select": select, "status": "SUCCESS"}


def publish_domo_dataset(dataset_name: str, table_name: str, **context: object) -> dict[str, object]:
    """Publish one Snowflake analytics table to Domo."""
    settings = _load_runtime_settings()
    run_id = _airflow_run_id(context)
    audit = _audit_logger(settings)
    reader = _table_reader(settings)
    publisher = DomoPublisher.from_config(settings.domo)
    qualified_table = _qualify_table(settings.snowflake.database, table_name)
    domo_dataset_name = f"{settings.domo.dataset_prefix}_{dataset_name}"

    with audit.start_pipeline(
        "dashboard_refresh",
        run_id=run_id,
        source_system="ANALYTICS",
        target_table=domo_dataset_name,
        metadata={"source_table": qualified_table},
    ) as pipeline_audit:
        rows = reader.fetch_table(qualified_table)
        dataset_id = publisher.publish_dataset(domo_dataset_name, rows)
        pipeline_audit.add_rows(rows_read=len(rows), rows_inserted=len(rows))
        pipeline_audit.record_step(
            f"publish_{dataset_name}",
            source_table=qualified_table,
            destination_table=domo_dataset_name,
            row_count=len(rows),
            details={"domo_dataset_id": dataset_id},
        )

    return {
        "run_id": run_id,
        "dataset_name": domo_dataset_name,
        "source_table": qualified_table,
        "domo_dataset_id": dataset_id,
        "rows_published": len(rows),
    }


def notify_airflow_event(event_type: str, context: Mapping[str, object]) -> None:
    """Notification callback used by Airflow DAGs for failures, retries, and SLA misses."""
    dag_id = _context_attr(context, "dag", "dag_id")
    task_id = _context_attr(context, "task_instance", "task_id")
    run_id = _airflow_run_id(context)
    exception = context.get("exception")
    LOGGER.warning(
        "airflow_event",
        extra={
            "event_type": event_type,
            "dag_id": dag_id,
            "task_id": task_id,
            "run_id": run_id,
            "exception": str(exception) if exception is not None else None,
        },
    )


def _load_runtime_settings() -> Customer360Config:
    settings = load_settings()
    configure_logging(settings.logging)
    return settings


def _audit_logger(settings: Customer360Config) -> AuditLogger:
    writer = SnowflakeAuditLogWriter(
        settings.snowflake.connection_parameters(),
        database_name=settings.snowflake.database,
    )
    return AuditLogger(writer=writer, environment=settings.environment)


def _table_reader(settings: Customer360Config) -> SnowflakeTableDataProvider:
    max_rows = _optional_positive_int(os.getenv("CUSTOMER360_AIRFLOW_MAX_TABLE_READ_ROWS"))
    return SnowflakeTableDataProvider(
        settings.snowflake.connection_parameters(),
        default_limit=max_rows,
    )


def _source_customer_record(row: Mapping[str, object]) -> SourceCustomerRecord:
    source_system = _required_text(row, "source_system")
    source_customer_id = _required_text(row, "source_customer_id")
    return SourceCustomerRecord(
        source_system=source_system,
        source_customer_id=source_customer_id,
        company_name=_clean(row.get("company_name") or row.get("company_name_normalized")),
        email=_clean(row.get("email")),
        phone=_clean(row.get("phone")),
        address=_clean(row.get("address")),
        website_domain=_clean(row.get("website_domain")),
    )


def _best_health_model(results: Sequence[HealthTrainingResult]) -> HealthTrainingResult:
    return max(
        results,
        key=lambda result: (
            result.evaluation.macro_f1,
            result.evaluation.accuracy,
            _model_preference(result.trained_model.algorithm),
        ),
    )


def _model_preference(algorithm: str) -> int:
    preferences = {
        HealthModelAlgorithm.XGBOOST.value: 3,
        HealthModelAlgorithm.RANDOM_FOREST.value: 2,
        HealthModelAlgorithm.LOGISTIC_REGRESSION.value: 1,
    }
    return preferences.get(algorithm, 0)


def _validation_configs(database_name: str, target_group: str) -> tuple[TableValidationConfig, ...]:
    tables = {
        "silver": (
            TableValidationConfig(
                table_name=f"{database_name}.SILVER.silver_customer",
                suite_name="customer_silver_suite",
            ),
        ),
        "gold": (
            TableValidationConfig(
                table_name=f"{database_name}.GOLD.gold_customer_master",
                suite_name="gold_customer_master_suite",
            ),
        ),
        "enrichment": (
            TableValidationConfig(
                table_name=f"{database_name}.GOLD.customer_enrichment_metrics",
                suite_name="customer_enrichment_metrics_suite",
            ),
        ),
        "scoring": (
            TableValidationConfig(
                table_name=f"{database_name}.ANALYTICS.customer_health_scores",
                suite_name="customer_health_scores_suite",
            ),
        ),
    }
    try:
        return tables[target_group]
    except KeyError as exc:
        raise ValueError(f"Unsupported validation target_group={target_group!r}.") from exc


def _silver_result_to_row(result: SilverPipelineResult) -> dict[str, object]:
    return _json_mapping(asdict(result))


def _airflow_run_id(context: Mapping[str, object]) -> str:
    dag_run = context.get("dag_run")
    run_id = getattr(dag_run, "run_id", None)
    if isinstance(run_id, str) and run_id:
        return run_id
    task_instance = context.get("task_instance") or context.get("ti")
    task_run_id = getattr(task_instance, "run_id", None)
    if isinstance(task_run_id, str) and task_run_id:
        return task_run_id
    return str(uuid4())


def _context_attr(context: Mapping[str, object], key: str, attr: str) -> object | None:
    value = context.get(key)
    return getattr(value, attr, None)


def _repo_path(path: str) -> Path:
    resolved = (REPO_ROOT / path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Required SQL script not found: {resolved}")
    return resolved


def _qualify_table(database_name: str, table_name: str) -> str:
    return table_name if table_name.count(".") == 2 else f"{database_name}.{table_name}"


def _pythonpath_with_src(existing: str | None) -> str:
    src_path = str(REPO_ROOT / "src")
    if not existing:
        return src_path
    return f"{src_path}{os.pathsep}{existing}"


def _optional_positive_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    parsed = int(value)
    if parsed <= 0:
        return None
    return parsed


def _required_text(row: Mapping[str, object], field_name: str) -> str:
    value = _clean(row.get(field_name))
    if value is None:
        raise ValueError(f"Missing required field {field_name!r} in Snowflake row.")
    return value


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"NULL", "NONE", "N/A", "NA"}:
        return None
    return text


def _json_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return cast(dict[str, object], _json_safe(dict(value)))


def _json_safe(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_safe(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)

