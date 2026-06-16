{{ config(
    unique_key=['source_system', 'source_customer_id'],
    cluster_by=['source_system', 'source_customer_id', 'to_date(last_modified_timestamp)']
) }}

with source_priority as (
    select source_system, source_priority
    from {{ ref('source_system_priority') }}
),

source_records as (
    select
        'SALESFORCE' as source_system,
        coalesce(customer_id, source_record_id) as source_customer_id,
        source_record_id,
        company_name,
        email,
        phone,
        billing_street as address_line_1,
        null as address_line_2,
        billing_city as city,
        billing_state as state_region,
        billing_postal_code as postal_code,
        billing_country as country,
        website,
        industry,
        null as customer_status,
        created_date,
        coalesce(last_modified_timestamp, load_timestamp) as last_modified_timestamp,
        coalesce(is_deleted, false) as is_deleted,
        load_batch_id
    from {{ ref('salesforce_customer_bronze') }}
    where coalesce(last_modified_timestamp, load_timestamp) is not null
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)') }}

    union all

    select
        'MARKETO',
        coalesce(lead_id, email, source_record_id),
        source_record_id,
        company_name,
        email,
        phone,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        lead_status,
        created_date,
        coalesce(last_modified_timestamp, load_timestamp),
        coalesce(is_deleted, false),
        load_batch_id
    from {{ ref('marketo_lead_bronze') }}
    where coalesce(last_modified_timestamp, load_timestamp) is not null
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)') }}

    union all

    select
        'ZENDESK',
        coalesce(customer_id, support_account_id, email, source_record_id),
        source_record_id,
        company_name,
        email,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        ticket_status,
        null,
        coalesce(last_modified_timestamp, load_timestamp),
        coalesce(is_deleted, false),
        load_batch_id
    from {{ ref('zendesk_support_bronze') }}
    where coalesce(last_modified_timestamp, load_timestamp) is not null
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)') }}

    union all

    select
        'PRODUCT_USAGE',
        coalesce(customer_id, source_record_id),
        source_record_id,
        company_name,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        coalesce(last_modified_timestamp, load_timestamp),
        coalesce(is_deleted, false),
        load_batch_id
    from {{ ref('product_usage_bronze') }}
    where coalesce(last_modified_timestamp, load_timestamp) is not null
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)') }}

    union all

    select
        'LICENSING',
        coalesce(customer_id, license_id, source_record_id),
        source_record_id,
        company_name,
        email,
        phone,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        renewal_status,
        null,
        coalesce(last_modified_timestamp, load_timestamp),
        coalesce(is_deleted, false),
        load_batch_id
    from {{ ref('licensing_customer_bronze') }}
    where coalesce(last_modified_timestamp, load_timestamp) is not null
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)') }}
),

standardized as (
    select
        records.source_system,
        records.source_customer_id,
        records.source_record_id,
        {{ customer360_clean_text('records.company_name') }} as company_name,
        {{ customer360_standardize_company('records.company_name') }} as company_name_normalized,
        {{ customer360_clean_email('records.email') }} as email,
        split_part({{ customer360_clean_email('records.email') }}, '@', 2) as email_domain,
        {{ customer360_clean_phone('records.phone') }} as phone,
        nullif(
            regexp_replace(
                regexp_replace(
                    regexp_replace(upper(trim(records.address_line_1)), '\\bSTREET\\b', 'ST'),
                    '\\bROAD\\b',
                    'RD'
                ),
                '\\bAVENUE\\b',
                'AVE'
            ),
            ''
        ) as address_line_1,
        nullif(upper(trim(records.address_line_2)), '') as address_line_2,
        {{ customer360_clean_text('records.city') }} as city,
        nullif(upper(trim(records.state_region)), '') as state_region,
        nullif(regexp_replace(upper(trim(records.postal_code)), '[^A-Z0-9]', ''), '') as postal_code,
        case
            when upper(trim(records.country)) in ('US', 'USA', 'UNITED STATES', 'UNITED STATES OF AMERICA') then 'US'
            when upper(trim(records.country)) in ('UK', 'UNITED KINGDOM', 'GREAT BRITAIN') then 'GB'
            else nullif(upper(trim(records.country)), '')
        end as country,
        {{ customer360_clean_website('records.website') }} as website_domain,
        {{ customer360_clean_text('records.industry') }} as industry,
        {{ customer360_clean_text('records.customer_status') }} as customer_status,
        records.created_date,
        records.last_modified_timestamp,
        records.is_deleted,
        coalesce(priority.source_priority, 100) as source_priority,
        records.load_batch_id
    from source_records records
    left join source_priority priority
        on priority.source_system = records.source_system
    where records.source_customer_id is not null
),

scored as (
    select
        *,
        nullif(
            regexp_replace(
                concat_ws(' ', address_line_1, city, state_region, postal_code, country),
                '\\s+',
                ' '
            ),
            ''
        ) as address,
        round(
            (
                iff(company_name is not null, 1, 0)
                + iff(email is not null, 1, 0)
                + iff(phone is not null, 1, 0)
                + iff(address_line_1 is not null, 1, 0)
                + iff(industry is not null, 1, 0)
                + iff(last_modified_timestamp is not null, 1, 0)
            ) / 6,
            4
        ) as completeness_score
    from standardized
)

select
    source_system,
    source_customer_id,
    source_record_id,
    company_name,
    company_name_normalized,
    email,
    email_domain,
    phone,
    address_line_1,
    address_line_2,
    city,
    state_region,
    postal_code,
    country,
    address,
    website_domain,
    industry,
    customer_status,
    created_date,
    last_modified_timestamp,
    is_deleted,
    source_priority,
    completeness_score,
    greatest(
        0,
        completeness_score
        - iff(email is not null and not regexp_like(email, '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$'), 0.25, 0)
        - iff(phone is not null and length(phone) not between 7 and 15, 0.10, 0)
    ) as data_quality_score,
    'v1' as standardization_version,
    sha2(to_json(object_construct_keep_null(
        'source_system', source_system,
        'source_customer_id', source_customer_id,
        'company_name', company_name,
        'email', email,
        'phone', phone,
        'address', address,
        'last_modified_timestamp', last_modified_timestamp
    )), 256) as record_hash,
    load_batch_id,
    current_timestamp() as standardized_at
from scored
qualify row_number() over (
    partition by source_system, source_customer_id
    order by last_modified_timestamp desc nulls last, load_batch_id desc
) = 1
