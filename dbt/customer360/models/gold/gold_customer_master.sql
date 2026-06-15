-- Golden customer records are assembled after Splink cluster output is available.
select
    md5(source_customer_id) as golden_customer_id,
    array_construct(source_customer_id) as source_customer_ids,
    company_name,
    email,
    phone,
    null as address,
    1.0 as confidence_score
from {{ ref('silver_customer') }}
