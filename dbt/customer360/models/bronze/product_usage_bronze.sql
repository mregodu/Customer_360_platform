{{ config(
    unique_key=['source_record_id', 'load_batch_id'],
    cluster_by=['source_system', 'event_date', 'customer_id']
) }}

with source as (
    select *
    from {{ source('landing', 'product_usage') }}
    where 1 = 1
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)') }}
)

select
    coalesce(source_record_id, usage_event_id, concat_ws('-', customer_id, event_date)) as source_record_id,
    usage_event_id,
    customer_id,
    company_name,
    user_id,
    event_date,
    login_count,
    active_days,
    active_users,
    feature_usage,
    product_area,
    coalesce(last_modified_timestamp, load_timestamp) as last_modified_timestamp,
    coalesce(is_deleted, false) as is_deleted,
    'PRODUCT_USAGE' as source_system,
    'USAGE_DAILY' as source_object,
    source_file_name,
    source_file_row_number,
    coalesce(load_batch_id, '{{ invocation_id }}') as load_batch_id,
    coalesce(load_timestamp, current_timestamp()) as load_timestamp,
    sha2(to_json(object_construct_keep_null(
        'usage_event_id', usage_event_id,
        'customer_id', customer_id,
        'event_date', event_date,
        'login_count', login_count,
        'active_users', active_users,
        'last_modified_timestamp', last_modified_timestamp
    )), 256) as record_hash,
    coalesce(raw_payload, object_construct_keep_null(*)) as raw_payload
from source
where coalesce(source_record_id, usage_event_id, concat_ws('-', customer_id, event_date)) is not null
