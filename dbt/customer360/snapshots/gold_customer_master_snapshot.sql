{% snapshot gold_customer_master_snapshot %}

{{
    config(
        unique_key='golden_customer_id',
        strategy='check',
        check_cols=[
            'company_name',
            'email',
            'phone',
            'address',
            'website_domain',
            'industry',
            'customer_status',
            'confidence_score',
            'data_quality_score',
            'is_active'
        ],
        invalidate_hard_deletes=True
    )
}}

select
    golden_customer_id,
    cluster_id,
    company_name,
    email,
    phone,
    address,
    website_domain,
    industry,
    customer_status,
    confidence_score,
    data_quality_score,
    is_active,
    updated_at,
    load_batch_id
from {{ ref('gold_customer_master') }}

{% endsnapshot %}
