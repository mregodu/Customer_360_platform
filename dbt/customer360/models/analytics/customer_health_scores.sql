-- Analytics table consumed by Domo Customer Success dashboards.
select
    golden_customer_id,
    0.0 as lifetime_value,
    0.0 as engagement_score,
    0.0 as adoption_score,
    0.0 as renewal_probability,
    'At Risk' as health_class
from {{ ref('gold_customer_master') }}
