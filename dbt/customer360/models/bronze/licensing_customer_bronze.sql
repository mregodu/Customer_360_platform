{{ config(
    unique_key=['source_record_id', 'load_batch_id'],
    cluster_by=['source_system', 'expiration_date', 'customer_id']
) }}

with source as (
    select *
    from {{ source('landing', 'licensing_customer') }}
    where 1 = 1
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)') }}
)

select
    coalesce(source_record_id, license_id, customer_id) as source_record_id,
    license_id,
    customer_id,
    company_name,
    email,
    phone,
    license_type,
    expiration_date,
    renewal_status,
    contract_value,
    seat_count,
    contract_start_date,
    contract_end_date,
    coalesce(last_modified_timestamp, load_timestamp) as last_modified_timestamp,
    coalesce(is_deleted, false) as is_deleted,
    'LICENSING' as source_system,
    'LICENSE' as source_object,
    source_file_name,
    source_file_row_number,
    coalesce(load_batch_id, '{{ invocation_id }}') as load_batch_id,
    coalesce(load_timestamp, current_timestamp()) as load_timestamp,
    sha2(to_json(object_construct_keep_null(
        'license_id', license_id,
        'customer_id', customer_id,
        'renewal_status', renewal_status,
        'expiration_date', expiration_date,
        'contract_value', contract_value,
        'last_modified_timestamp', last_modified_timestamp
    )), 256) as record_hash,
    coalesce(raw_payload, object_construct_keep_null(*)) as raw_payload
from source
where coalesce(source_record_id, license_id, customer_id) is not null
