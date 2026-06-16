{{ config(
    unique_key=['golden_customer_id', 'score_date'],
    cluster_by=['score_date', 'derived_health_class', 'golden_customer_id']
) }}

select
    enrichment.golden_customer_id,
    enrichment.metric_date as score_date,
    master.company_name,
    master.email,
    master.industry,
    enrichment.lifetime_value,
    enrichment.product_usage_score,
    enrichment.product_adoption_score,
    enrichment.marketing_engagement_score,
    enrichment.engagement_score,
    enrichment.support_health_score,
    enrichment.support_ticket_count,
    enrichment.satisfaction_score,
    enrichment.response_time_minutes,
    enrichment.active_users,
    enrichment.active_days,
    enrichment.renewal_probability,
    enrichment.renewal_status,
    enrichment.license_expiration_date,
    enrichment.contract_value,
    enrichment.seat_count,
    case
        when upper(enrichment.renewal_status) in ('CANCELLED', 'CANCELED', 'CHURNED', 'EXPIRED', 'LOST') then 'Churn Risk'
        when enrichment.renewal_probability <= 0.20 then 'Churn Risk'
        when coalesce(enrichment.support_health_score, 1) <= 0.25 then 'Churn Risk'
        when enrichment.engagement_score >= 0.75
            and enrichment.product_adoption_score >= 0.75
            and coalesce(enrichment.support_health_score, 1) >= 0.75
            and coalesce(enrichment.renewal_probability, 1) >= 0.55
            then 'Healthy'
        when enrichment.engagement_score < 0.35
            or enrichment.product_adoption_score < 0.35
            or coalesce(enrichment.support_health_score, 1) < 0.45
            or coalesce(enrichment.renewal_probability, 1) < 0.55
            then 'At Risk'
        else 'At Risk'
    end as derived_health_class,
    object_construct_keep_null(
        'product_usage_score', enrichment.product_usage_score,
        'product_adoption_score', enrichment.product_adoption_score,
        'marketing_engagement_score', enrichment.marketing_engagement_score,
        'engagement_score', enrichment.engagement_score,
        'support_health_score', enrichment.support_health_score,
        'support_ticket_count', enrichment.support_ticket_count,
        'satisfaction_score', enrichment.satisfaction_score,
        'response_time_minutes', enrichment.response_time_minutes,
        'active_users', enrichment.active_users,
        'active_days', enrichment.active_days,
        'renewal_probability', enrichment.renewal_probability,
        'renewal_status', enrichment.renewal_status,
        'license_expiration_date', enrichment.license_expiration_date,
        'contract_value', enrichment.contract_value
    ) as feature_snapshot,
    current_timestamp() as created_at,
    enrichment.load_batch_id
from {{ ref('customer_enrichment_metrics') }} enrichment
left join {{ ref('gold_customer_master') }} master
    on master.golden_customer_id = enrichment.golden_customer_id
where enrichment.metric_date >= dateadd(day, -{{ var('customer360_feature_lookback_days') }}, current_date())
