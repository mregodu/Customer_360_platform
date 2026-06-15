-- Bronze models preserve source shape. In production this can point to raw Snowflake landing tables.
select
    customer_id,
    company_name,
    email,
    phone,
    industry,
    created_date,
    current_timestamp() as load_timestamp,
    'salesforce' as source_system
from {{ source('landing', 'salesforce_customer') }}
