select
    source_system,
    source_customer_id,
    count(*) as duplicate_count
from {{ ref('silver_customer') }}
where coalesce(is_deleted, false) = false
group by source_system, source_customer_id
having count(*) > 1
