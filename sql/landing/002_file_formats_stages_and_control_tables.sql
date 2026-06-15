-- Creates landing file formats, internal stages, load manifests, and CDC controls.

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema LANDING;

create file format if not exists csv_utf8_format
    type = csv
    field_delimiter = ','
    skip_header = 1
    field_optionally_enclosed_by = '"'
    trim_space = true
    empty_field_as_null = true
    null_if = ('', 'NULL', 'null')
    error_on_column_count_mismatch = false
    comment = 'Default UTF-8 CSV format for source extracts';

create file format if not exists json_format
    type = json
    strip_outer_array = true
    ignore_utf8_errors = false
    comment = 'Default JSON format for semi-structured source extracts';

create file format if not exists parquet_format
    type = parquet
    use_logical_type = true
    comment = 'Default Parquet format for high-volume source extracts';

create stage if not exists stage_salesforce
    file_format = (format_name = csv_utf8_format)
    encryption = (type = 'SNOWFLAKE_SSE')
    comment = 'Internal landing stage for Salesforce customer extracts';

create stage if not exists stage_marketo
    file_format = (format_name = csv_utf8_format)
    encryption = (type = 'SNOWFLAKE_SSE')
    comment = 'Internal landing stage for Marketo lead and campaign extracts';

create stage if not exists stage_zendesk
    file_format = (format_name = json_format)
    encryption = (type = 'SNOWFLAKE_SSE')
    comment = 'Internal landing stage for Zendesk support extracts';

create stage if not exists stage_product_usage
    file_format = (format_name = parquet_format)
    encryption = (type = 'SNOWFLAKE_SSE')
    comment = 'Internal landing stage for product usage extracts';

create stage if not exists stage_licensing
    file_format = (format_name = csv_utf8_format)
    encryption = (type = 'SNOWFLAKE_SSE')
    comment = 'Internal landing stage for licensing extracts';

create stage if not exists stage_impartner
    file_format = (format_name = json_format)
    encryption = (type = 'SNOWFLAKE_SSE')
    comment = 'Internal landing stage for Impartner extracts';

create sequence if not exists load_batch_sequence
    start = 1
    increment = 1
    comment = 'Sequence for generating landing load batch identifiers';

create table if not exists raw_file_manifest (
    file_load_id varchar not null,
    source_system varchar not null,
    source_object varchar not null,
    stage_name varchar not null,
    file_name varchar not null,
    file_content_key varchar,
    file_row_count number(38, 0),
    file_size_bytes number(38, 0),
    load_batch_id varchar not null,
    load_status varchar not null,
    first_seen_at timestamp_ntz not null default current_timestamp(),
    loaded_at timestamp_ntz,
    rejected_at timestamp_ntz,
    error_message varchar,
    metadata variant,
    created_at timestamp_ntz not null default current_timestamp(),
    updated_at timestamp_ntz not null default current_timestamp(),
    primary key (file_load_id) not enforced
)
cluster by (source_system, source_object, to_date(first_seen_at))
comment = 'Manifest of files discovered, loaded, rejected, or awaiting ingestion';

create table if not exists source_extract_watermarks (
    source_system varchar not null,
    source_object varchar not null,
    watermark_column varchar not null,
    high_watermark_value varchar,
    high_watermark_timestamp timestamp_ntz,
    last_successful_run_id varchar,
    last_successful_load_at timestamp_ntz,
    is_active boolean not null default true,
    created_at timestamp_ntz not null default current_timestamp(),
    updated_at timestamp_ntz not null default current_timestamp(),
    primary key (source_system, source_object) not enforced
)
cluster by (source_system, source_object)
comment = 'CDC high-watermarks used by incremental extract pipelines';

create table if not exists load_batch_control (
    load_batch_id varchar not null,
    pipeline_name varchar not null,
    source_system varchar,
    source_object varchar,
    run_id varchar,
    status varchar not null,
    started_at timestamp_ntz not null default current_timestamp(),
    ended_at timestamp_ntz,
    records_discovered number(38, 0) default 0,
    records_loaded number(38, 0) default 0,
    records_rejected number(38, 0) default 0,
    error_message varchar,
    metadata variant,
    primary key (load_batch_id) not enforced
)
cluster by (pipeline_name, source_system, to_date(started_at))
comment = 'Landing and ingestion batch-level control table';

create table if not exists raw_rejection_log (
    rejection_id varchar not null,
    load_batch_id varchar not null,
    source_system varchar not null,
    source_object varchar not null,
    source_file_name varchar,
    source_file_row_number number(38, 0),
    rejection_reason varchar not null,
    raw_record variant,
    rejected_at timestamp_ntz not null default current_timestamp(),
    primary key (rejection_id) not enforced
)
cluster by (source_system, source_object, to_date(rejected_at))
comment = 'Rejected landing records retained for reconciliation and remediation';
