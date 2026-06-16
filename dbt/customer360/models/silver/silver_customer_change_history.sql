{{ config(
    materialized='table',
    cluster_by=['source_system', 'source_customer_id', 'to_date(effective_from)']
) }}

select
    {{ customer360_surrogate_key(["source_system", "source_customer_id", "dbt_valid_from"]) }} as change_id,
    source_system,
    source_customer_id,
    iff(dbt_valid_to is null, 'CURRENT', 'HISTORICAL') as change_type,
    array_construct(
        'company_name',
        'email',
        'phone',
        'address',
        'website_domain',
        'customer_status'
    ) as changed_columns,
    lag(record_hash) over (
        partition by source_system, source_customer_id
        order by dbt_valid_from
    ) as previous_record_hash,
    record_hash as current_record_hash,
    dbt_valid_from as effective_from,
    dbt_valid_to as effective_to,
    dbt_valid_to is null as is_current,
    load_batch_id,
    current_timestamp() as captured_at
from {{ ref('silver_customer_snapshot') }}
