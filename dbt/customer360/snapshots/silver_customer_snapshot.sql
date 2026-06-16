{% snapshot silver_customer_snapshot %}

{{
    config(
        unique_key="source_system || '|' || source_customer_id",
        strategy='check',
        check_cols=[
            'company_name',
            'email',
            'phone',
            'address',
            'website_domain',
            'customer_status',
            'record_hash',
            'is_deleted'
        ],
        invalidate_hard_deletes=True
    )
}}

select
    source_system,
    source_customer_id,
    source_record_id,
    company_name,
    email,
    phone,
    address,
    website_domain,
    customer_status,
    last_modified_timestamp,
    record_hash,
    is_deleted,
    load_batch_id
from {{ ref('silver_customer') }}

{% endsnapshot %}
