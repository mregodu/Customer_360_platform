select *
from {{ ref('customer_health_scores') }}
where churn_risk_score < 0
   or churn_risk_score > 1
   or renewal_probability < 0
   or renewal_probability > 1
   or health_class not in ('Healthy', 'At Risk', 'Churn Risk')
