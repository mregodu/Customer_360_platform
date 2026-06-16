{{ config(
    unique_key=['source_record_id', 'load_batch_id'],
    cluster_by=['source_system', 'to_date(load_timestamp)', 'source_record_id']
) }}

with source as (
    select *
    from {{ source('landing', 'zendesk_support') }}
    where 1 = 1
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)') }}
)

select
    coalesce(source_record_id, support_account_id, ticket_id, customer_id, email) as source_record_id,
    support_account_id,
    ticket_id,
    customer_id,
    company_name,
    email,
    ticket_count,
    satisfaction_score,
    response_time_minutes,
    ticket_status,
    ticket_priority,
    last_ticket_created_at,
    coalesce(last_modified_timestamp, load_timestamp) as last_modified_timestamp,
    coalesce(is_deleted, false) as is_deleted,
    'ZENDESK' as source_system,
    'SUPPORT_ACCOUNT' as source_object,
    source_file_name,
    source_file_row_number,
    coalesce(load_batch_id, '{{ invocation_id }}') as load_batch_id,
    coalesce(load_timestamp, current_timestamp()) as load_timestamp,
    sha2(to_json(object_construct_keep_null(
        'support_account_id', support_account_id,
        'ticket_id', ticket_id,
        'customer_id', customer_id,
        'email', email,
        'last_modified_timestamp', last_modified_timestamp
    )), 256) as record_hash,
    coalesce(raw_payload, object_construct_keep_null(*)) as raw_payload
from source
where coalesce(source_record_id, support_account_id, ticket_id, customer_id, email) is not null
