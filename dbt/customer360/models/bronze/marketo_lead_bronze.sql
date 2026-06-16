{{ config(
    unique_key=['source_record_id', 'load_batch_id'],
    cluster_by=['source_system', 'to_date(load_timestamp)', 'source_record_id']
) }}

with source as (
    select *
    from {{ source('landing', 'marketo_lead') }}
    where 1 = 1
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)') }}
)

select
    coalesce(source_record_id, lead_id, email) as source_record_id,
    lead_id,
    email,
    company_name,
    phone,
    campaign,
    engagement_score,
    lead_status,
    first_name,
    last_name,
    created_date,
    coalesce(last_modified_timestamp, load_timestamp) as last_modified_timestamp,
    coalesce(is_deleted, false) as is_deleted,
    'MARKETO' as source_system,
    'LEAD' as source_object,
    source_file_name,
    source_file_row_number,
    coalesce(load_batch_id, '{{ invocation_id }}') as load_batch_id,
    coalesce(load_timestamp, current_timestamp()) as load_timestamp,
    sha2(to_json(object_construct_keep_null(
        'lead_id', lead_id,
        'email', email,
        'company_name', company_name,
        'campaign', campaign,
        'last_modified_timestamp', last_modified_timestamp
    )), 256) as record_hash,
    coalesce(raw_payload, object_construct_keep_null(*)) as raw_payload
from source
where coalesce(source_record_id, lead_id, email) is not null
