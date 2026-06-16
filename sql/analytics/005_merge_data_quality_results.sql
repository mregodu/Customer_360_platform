-- Merges Great Expectations metrics, run summaries, and alerts.
-- Expected staging tables:
--   CUSTOMER360_DB.ANALYTICS.stage_data_quality_metrics
--   CUSTOMER360_DB.ANALYTICS.stage_data_quality_validation_runs
--   CUSTOMER360_DB.ANALYTICS.stage_data_quality_alerts

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema ANALYTICS;

create table if not exists stage_data_quality_metrics like CUSTOMER360_DB.ANALYTICS.data_quality_metrics;
create table if not exists stage_data_quality_validation_runs like CUSTOMER360_DB.ANALYTICS.data_quality_validation_runs;
create table if not exists stage_data_quality_alerts like CUSTOMER360_DB.ANALYTICS.data_quality_alerts;

merge into CUSTOMER360_DB.ANALYTICS.data_quality_metrics target
using CUSTOMER360_DB.ANALYTICS.stage_data_quality_metrics source
on target.metric_id = source.metric_id
when matched then update set
    run_id = source.run_id,
    source_system = source.source_system,
    schema_name = source.schema_name,
    table_name = source.table_name,
    expectation_suite_name = source.expectation_suite_name,
    rule_name = source.rule_name,
    rule_type = source.rule_type,
    dimension = source.dimension,
    severity = source.severity,
    measured_at = source.measured_at,
    passed_count = source.passed_count,
    failed_count = source.failed_count,
    total_count = source.total_count,
    quality_score = source.quality_score,
    threshold = source.threshold,
    status = source.status,
    details = source.details
when not matched then insert (
    metric_id,
    run_id,
    source_system,
    schema_name,
    table_name,
    expectation_suite_name,
    rule_name,
    rule_type,
    dimension,
    severity,
    measured_at,
    passed_count,
    failed_count,
    total_count,
    quality_score,
    threshold,
    status,
    details
) values (
    source.metric_id,
    source.run_id,
    source.source_system,
    source.schema_name,
    source.table_name,
    source.expectation_suite_name,
    source.rule_name,
    source.rule_type,
    source.dimension,
    source.severity,
    source.measured_at,
    source.passed_count,
    source.failed_count,
    source.total_count,
    source.quality_score,
    source.threshold,
    source.status,
    source.details
);

merge into CUSTOMER360_DB.ANALYTICS.data_quality_validation_runs target
using CUSTOMER360_DB.ANALYTICS.stage_data_quality_validation_runs source
on target.run_id = source.run_id
   and target.expectation_suite_name = source.expectation_suite_name
   and target.schema_name = source.schema_name
   and target.table_name = source.table_name
when matched then update set
    started_at = source.started_at,
    completed_at = source.completed_at,
    status = source.status,
    row_count = source.row_count,
    metrics_total = source.metrics_total,
    metrics_failed = source.metrics_failed,
    metrics_warned = source.metrics_warned,
    quality_score = source.quality_score,
    details = source.details
when not matched then insert (
    run_id,
    expectation_suite_name,
    schema_name,
    table_name,
    started_at,
    completed_at,
    status,
    row_count,
    metrics_total,
    metrics_failed,
    metrics_warned,
    quality_score,
    details
) values (
    source.run_id,
    source.expectation_suite_name,
    source.schema_name,
    source.table_name,
    source.started_at,
    source.completed_at,
    source.status,
    source.row_count,
    source.metrics_total,
    source.metrics_failed,
    source.metrics_warned,
    source.quality_score,
    source.details
);

merge into CUSTOMER360_DB.ANALYTICS.data_quality_alerts target
using CUSTOMER360_DB.ANALYTICS.stage_data_quality_alerts source
on target.alert_id = source.alert_id
when matched then update set
    run_id = source.run_id,
    schema_name = source.schema_name,
    table_name = source.table_name,
    expectation_suite_name = source.expectation_suite_name,
    rule_name = source.rule_name,
    severity = source.severity,
    status = source.status,
    message = source.message,
    created_at = source.created_at,
    details = source.details
when not matched then insert (
    alert_id,
    run_id,
    schema_name,
    table_name,
    expectation_suite_name,
    rule_name,
    severity,
    status,
    message,
    created_at,
    details
) values (
    source.alert_id,
    source.run_id,
    source.schema_name,
    source.table_name,
    source.expectation_suite_name,
    source.rule_name,
    source.severity,
    source.status,
    source.message,
    source.created_at,
    source.details
);
