{{ config(
    unique_key='metric_date',
    cluster_by=['metric_date']
) }}

with scores as (
    select *
    from {{ ref('customer_health_scores') }}
),

cluster_rollup as (
    select
        count(*) as total_clusters,
        sum(cluster_size) as total_source_members,
        avg(confidence_score) as match_accuracy_estimate
    from {{ ref('gold_customer_clusters') }}
),

quality_rollup as (
    select
        metric_date,
        round(avg(average_quality_score), 4) as data_quality_score
    from {{ ref('data_quality_dashboard_daily') }}
    group by metric_date
)

select
    scores.score_date as metric_date,
    count(distinct scores.golden_customer_id) as total_customers,
    count_if(to_date(master.first_seen_at) = scores.score_date) as new_customers,
    count_if(coalesce(master.is_active, true)) as active_customers,
    count_if(scores.engagement_score >= 0.75) as high_engagement_customers,
    count_if(scores.health_class = 'At Risk') as at_risk_customers,
    count_if(scores.health_class = 'Churn Risk') as churn_risk_customers,
    round(sum(coalesce(scores.lifetime_value, 0)), 2) as total_lifetime_value,
    round(avg(scores.engagement_score), 4) as average_engagement_score,
    round(avg(scores.adoption_score), 4) as average_adoption_score,
    round(avg(scores.renewal_probability), 4) as average_renewal_probability,
    round(1 - (max(cluster_rollup.total_clusters) / nullif(max(cluster_rollup.total_source_members), 0)), 4) as duplicate_reduction_rate,
    round(max(cluster_rollup.match_accuracy_estimate), 4) as match_accuracy_estimate,
    coalesce(max(quality_rollup.data_quality_score), 1.0) as data_quality_score,
    current_timestamp() as refreshed_at
from scores
left join {{ ref('gold_customer_master') }} master
    on master.golden_customer_id = scores.golden_customer_id
cross join cluster_rollup
left join quality_rollup
    on quality_rollup.metric_date = scores.score_date
group by scores.score_date
