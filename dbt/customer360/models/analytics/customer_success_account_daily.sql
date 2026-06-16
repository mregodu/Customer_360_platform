{{ config(
    unique_key=['golden_customer_id', 'metric_date'],
    cluster_by=['metric_date', 'health_class', 'golden_customer_id']
) }}

select
    scores.golden_customer_id,
    scores.score_date as metric_date,
    master.company_name,
    master.industry,
    master.customer_status,
    scores.health_class,
    scores.renewal_probability,
    scores.engagement_score,
    scores.adoption_score,
    scores.support_ticket_count,
    scores.satisfaction_score,
    scores.active_users,
    enrichment.license_expiration_date,
    enrichment.renewal_status,
    'UNASSIGNED' as owner_team,
    current_timestamp() as refreshed_at
from {{ ref('customer_health_scores') }} scores
left join {{ ref('gold_customer_master') }} master
    on master.golden_customer_id = scores.golden_customer_id
left join {{ ref('customer_enrichment_metrics') }} enrichment
    on enrichment.golden_customer_id = scores.golden_customer_id
    and enrichment.metric_date = scores.score_date
