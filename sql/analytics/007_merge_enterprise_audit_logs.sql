-- Merges enterprise audit records into pipeline and ETL audit tables.
-- Expected staging tables:
--   CUSTOMER360_DB.ANALYTICS.stage_pipeline_execution_log
--   CUSTOMER360_DB.ANALYTICS.stage_etl_audit_log

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema ANALYTICS;

create table if not exists stage_pipeline_execution_log like CUSTOMER360_DB.ANALYTICS.pipeline_execution_log;
create table if not exists stage_etl_audit_log like CUSTOMER360_DB.ANALYTICS.etl_audit_log;

merge into CUSTOMER360_DB.ANALYTICS.pipeline_execution_log target
using CUSTOMER360_DB.ANALYTICS.stage_pipeline_execution_log source
on target.pipeline_execution_id = source.pipeline_execution_id
when matched then update set
    pipeline_name = source.pipeline_name,
    run_id = source.run_id,
    environment = source.environment,
    source_system = source.source_system,
    target_table = source.target_table,
    start_time = source.start_time,
    end_time = source.end_time,
    duration_seconds = source.duration_seconds,
    status = source.status,
    rows_read = source.rows_read,
    rows_inserted = source.rows_inserted,
    rows_updated = source.rows_updated,
    rows_deleted = source.rows_deleted,
    rows_processed = source.rows_processed,
    error_message = source.error_message,
    error_details = source.error_details,
    metadata = source.metadata,
    created_at = source.created_at
when not matched then insert (
    pipeline_execution_id,
    pipeline_name,
    run_id,
    environment,
    source_system,
    target_table,
    start_time,
    end_time,
    duration_seconds,
    status,
    rows_read,
    rows_inserted,
    rows_updated,
    rows_deleted,
    rows_processed,
    error_message,
    error_details,
    metadata,
    created_at
) values (
    source.pipeline_execution_id,
    source.pipeline_name,
    source.run_id,
    source.environment,
    source.source_system,
    source.target_table,
    source.start_time,
    source.end_time,
    source.duration_seconds,
    source.status,
    source.rows_read,
    source.rows_inserted,
    source.rows_updated,
    source.rows_deleted,
    source.rows_processed,
    source.error_message,
    source.error_details,
    source.metadata,
    source.created_at
);

merge into CUSTOMER360_DB.ANALYTICS.etl_audit_log target
using CUSTOMER360_DB.ANALYTICS.stage_etl_audit_log source
on target.audit_id = source.audit_id
when matched then update set
    run_id = source.run_id,
    pipeline_name = source.pipeline_name,
    source_table = source.source_table,
    transformation_step = source.transformation_step,
    destination_table = source.destination_table,
    execution_timestamp = source.execution_timestamp,
    row_count = source.row_count,
    rows_processed = source.rows_processed,
    checksum = source.checksum,
    status = source.status,
    error_details = source.error_details,
    details = source.details
when not matched then insert (
    audit_id,
    run_id,
    pipeline_name,
    source_table,
    transformation_step,
    destination_table,
    execution_timestamp,
    row_count,
    rows_processed,
    checksum,
    status,
    error_details,
    details
) values (
    source.audit_id,
    source.run_id,
    source.pipeline_name,
    source.source_table,
    source.transformation_step,
    source.destination_table,
    source.execution_timestamp,
    source.row_count,
    source.rows_processed,
    source.checksum,
    source.status,
    source.error_details,
    source.details
);
