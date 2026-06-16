{{ config(
    unique_key=['partner_id', 'metric_date'],
    cluster_by=['metric_date', 'partner_region', 'partner_tier']
) }}

with latest_health as (
    select
        score_date,
        avg(1 - churn_risk_score) as average_customer_health_score,
        count(distinct golden_customer_id) as active_customer_count
    from {{ ref('customer_health_scores') }}
    where score_date = (select max(score_date) from {{ ref('customer_health_scores') }})
    group by score_date
)

select
    partners.partner_id,
    coalesce(latest_health.score_date, current_date()) as metric_date,
    partners.company_name,
    partners.partner_tier,
    partners.partner_region,
    partners.partner_status,
    partners.certification_count,
    0 as influenced_customer_count,
    0.00 as influenced_lifetime_value,
    coalesce(latest_health.active_customer_count, 0) as active_customer_count,
    round(coalesce(latest_health.average_customer_health_score, 0), 4) as average_customer_health_score,
    current_timestamp() as refreshed_at
from {{ ref('silver_partner_profile') }} partners
left join latest_health
    on 1 = 1
where coalesce(partners.is_deleted, false) = false
