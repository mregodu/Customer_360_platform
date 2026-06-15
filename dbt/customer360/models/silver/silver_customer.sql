-- Silver standardizes source records for matching and downstream enrichment.
select
    customer_id as source_customer_id,
    upper(trim(company_name)) as company_name,
    lower(trim(email)) as email,
    regexp_replace(phone, '[^0-9]', '') as phone,
    industry,
    created_date,
    load_timestamp,
    source_system
from {{ ref('salesforce_customer_bronze') }}
