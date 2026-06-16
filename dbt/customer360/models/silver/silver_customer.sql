-- Silver standardizes source records for matching and downstream enrichment.
-- Operational Snowflake merges live in sql/silver/002_merge_silver_customer.sql.

with salesforce as (
    select
        'SALESFORCE' as source_system,
        customer_id as source_customer_id,
        source_record_id,
        upper(trim(company_name)) as company_name,
        regexp_replace(
            regexp_replace(upper(trim(company_name)), '\\b(CORP|CORPORATION|INC|LLC|LTD|CO|COMPANY)\\b', ''),
            '\\s+',
            ' '
        ) as company_name_normalized,
        lower(trim(email)) as email,
        split_part(lower(trim(email)), '@', 2) as email_domain,
        regexp_replace(phone, '[^0-9]', '') as phone,
        upper(trim(billing_street)) as address_line_1,
        null as address_line_2,
        upper(trim(billing_city)) as city,
        upper(trim(billing_state)) as state_region,
        regexp_replace(upper(trim(billing_postal_code)), '[^A-Z0-9]', '') as postal_code,
        upper(trim(billing_country)) as country,
        regexp_replace(
            concat_ws(' ', billing_street, billing_city, billing_state, billing_postal_code, billing_country),
            '\\s+',
            ' '
        ) as address,
        regexp_replace(lower(regexp_replace(trim(website), '^https?://(www\\.)?', '')), '/.*$', '') as website_domain,
        upper(trim(industry)) as industry,
        null as customer_status,
        created_date,
        last_modified_timestamp,
        is_deleted,
        10 as source_priority,
        load_batch_id,
        current_timestamp() as standardized_at
    from {{ ref('salesforce_customer_bronze') }}
)

select *
from salesforce
