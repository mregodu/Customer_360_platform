{{ config(
    unique_key=['golden_customer_id', 'score_date'],
    cluster_by=['score_date', 'health_class', 'golden_customer_id']
) }}

with scored as (
    select
        *,
        case
            when derived_health_class = 'Healthy' then 0.05
            when derived_health_class = 'At Risk' then 0.45
            when derived_health_class = 'Churn Risk' then 0.85
            else 0.50
        end as churn_risk_score,
        case
            when derived_health_class = 'Healthy' then object_construct('Healthy', 0.85, 'At Risk', 0.10, 'Churn Risk', 0.05)
            when derived_health_class = 'At Risk' then object_construct('Healthy', 0.15, 'At Risk', 0.55, 'Churn Risk', 0.30)
            when derived_health_class = 'Churn Risk' then object_construct('Healthy', 0.05, 'At Risk', 0.20, 'Churn Risk', 0.75)
            else object_construct('Healthy', 0.33, 'At Risk', 0.34, 'Churn Risk', 0.33)
        end as class_probabilities
    from {{ ref('customer_health_features') }}
)

select
    golden_customer_id,
    score_date,
    company_name,
    email,
    industry,
    lifetime_value,
    product_usage_score,
    marketing_engagement_score,
    engagement_score,
    product_adoption_score as adoption_score,
    renewal_probability,
    null as support_activity_score,
    support_health_score,
    satisfaction_score,
    support_ticket_count,
    active_users,
    churn_risk_score,
    derived_health_class as health_class,
    'Derived from dbt enrichment features: product adoption, engagement, support health, and renewal probability.' as classification_reason,
    '{{ var("customer360_model_version") }}' as model_version,
    'dbt_rules' as model_algorithm,
    class_probabilities,
    feature_snapshot,
    current_timestamp() as scored_at,
    load_batch_id
from scored
