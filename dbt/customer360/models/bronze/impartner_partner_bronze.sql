{{ config(
    unique_key=['source_record_id', 'load_batch_id'],
    cluster_by=['source_system', 'partner_region', 'partner_id']
) }}

with source as (
    select *
    from {{ source('landing', 'impartner_partner') }}
    where 1 = 1
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)') }}
)

select
    coalesce(source_record_id, partner_id) as source_record_id,
    partner_id,
    company_name,
    email,
    phone,
    partner_tier,
    certifications,
    partner_region,
    partner_status,
    created_date,
    coalesce(last_modified_timestamp, load_timestamp) as last_modified_timestamp,
    coalesce(is_deleted, false) as is_deleted,
    'IMPARTNER' as source_system,
    'PARTNER' as source_object,
    source_file_name,
    source_file_row_number,
    coalesce(load_batch_id, '{{ invocation_id }}') as load_batch_id,
    coalesce(load_timestamp, current_timestamp()) as load_timestamp,
    sha2(to_json(object_construct_keep_null(
        'partner_id', partner_id,
        'company_name', company_name,
        'email', email,
        'partner_tier', partner_tier,
        'last_modified_timestamp', last_modified_timestamp
    )), 256) as record_hash,
    coalesce(raw_payload, object_construct_keep_null(*)) as raw_payload
from source
where coalesce(source_record_id, partner_id) is not null
