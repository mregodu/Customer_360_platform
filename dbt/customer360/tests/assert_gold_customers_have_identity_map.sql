select master.golden_customer_id
from {{ ref('gold_customer_master') }} master
left join {{ ref('customer_identity_map') }} identity_map
    on identity_map.golden_customer_id = master.golden_customer_id
where identity_map.golden_customer_id is null
