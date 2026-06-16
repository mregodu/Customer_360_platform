-- Generates daily customer enrichment metrics from Gold clusters and Silver activity metrics.
-- Outputs:
--   CUSTOMER360_DB.GOLD.customer_enrichment_metrics

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema GOLD;

set metric_start_date = dateadd(day, -90, current_date());

merge into CUSTOMER360_DB.GOLD.customer_enrichment_metrics target
using (
    with cluster_members as (
        select
            clusters.golden_customer_id,
            member.value:source_system::varchar as source_system,
            member.value:source_customer_id::varchar as source_customer_id
        from CUSTOMER360_DB.GOLD.gold_customer_clusters clusters,
            lateral flatten(input => coalesce(clusters.source_members, array_construct())) member
        where clusters.source_members is not null

        union all

        select
            clusters.golden_customer_id,
            clusters.source_systems[0]::varchar as source_system,
            source_id.value::varchar as source_customer_id
        from CUSTOMER360_DB.GOLD.gold_customer_clusters clusters,
            lateral flatten(input => coalesce(clusters.source_customer_ids, array_construct())) source_id
        where clusters.source_members is null
            and array_size(clusters.source_systems) = 1
    ),

    source_metrics as (
        select
            members.golden_customer_id,
            metrics.metric_date,
            metrics.source_system,
            metrics.source_customer_id,
            metrics.product_usage_score,
            metrics.marketing_engagement_score,
            metrics.support_activity_score,
            metrics.ticket_count,
            metrics.satisfaction_score,
            metrics.response_time_minutes,
            metrics.active_users,
            metrics.active_days,
            coalesce(
                try_to_double(metrics.feature_usage:feature_utilization_score),
                metrics.product_usage_score
            ) as feature_utilization_score,
            metrics.renewal_status,
            metrics.license_expiration_date,
            metrics.contract_value,
            metrics.seat_count,
            metrics.load_batch_id
        from cluster_members members
        inner join CUSTOMER360_DB.SILVER.silver_customer_metric_daily metrics
            on metrics.source_system = members.source_system
            and metrics.source_customer_id = members.source_customer_id
        where metrics.metric_date >= $metric_start_date
    ),

    aggregated as (
        select
            golden_customer_id,
            metric_date,
            round(avg(product_usage_score), 4) as product_usage_score,
            round(avg(marketing_engagement_score), 4) as marketing_engagement_score,
            round(avg(support_activity_score), 4) as support_activity_score,
            sum(ticket_count) as support_ticket_count,
            round(avg(satisfaction_score), 4) as satisfaction_score,
            round(avg(response_time_minutes), 4) as response_time_minutes,
            sum(active_users) as active_users,
            max(active_days) as active_days,
            round(avg(feature_utilization_score), 4) as feature_utilization_score,
            min(license_expiration_date) as license_expiration_date,
            sum(contract_value) as contract_value,
            sum(seat_count) as seat_count,
            max(load_batch_id) as load_batch_id,
            object_construct(
                'source_systems',
                array_agg(distinct source_system),
                'source_metric_count',
                count(*),
                'formula_version',
                'customer_enrichment_v1'
            ) as metric_components
        from source_metrics
        group by golden_customer_id, metric_date
    ),

    status_ranked as (
        select
            golden_customer_id,
            metric_date,
            renewal_status,
            case
                when upper(renewal_status) in ('CANCELLED', 'CANCELED', 'CHURNED', 'EXPIRED', 'LOST') then 0
                when upper(renewal_status) in ('AT RISK', 'AT_RISK', 'RISK', 'DOWNGRADE_RISK') then 1
                when upper(renewal_status) in ('OPEN', 'PENDING', 'IN_PROGRESS') then 2
                when upper(renewal_status) in ('RENEWED', 'ACTIVE', 'AUTO_RENEW', 'AUTO RENEWAL') then 3
                else 2
            end as renewal_status_rank
        from source_metrics
        where renewal_status is not null
        qualify row_number() over (
            partition by golden_customer_id, metric_date
            order by renewal_status_rank asc, renewal_status asc
        ) = 1
    ),

    component_scores as (
        select
            aggregated.*,
            status_ranked.renewal_status,
            round(
                (
                    coalesce(least(greatest(product_usage_score, 0), 1), 0) * 0.45
                    + coalesce(least(greatest(active_users / 50, 0), 1), 0) * 0.15
                    + coalesce(least(greatest(active_days / 30, 0), 1), 0) * 0.15
                    + coalesce(least(greatest(feature_utilization_score, 0), 1), 0) * 0.25
                )
                /
                nullif(
                    iff(product_usage_score is not null, 0.45, 0)
                    + iff(active_users is not null, 0.15, 0)
                    + iff(active_days is not null, 0.15, 0)
                    + iff(feature_utilization_score is not null, 0.25, 0),
                    0
                ),
                4
            ) as product_adoption_score,
            round(
                (
                    coalesce(least(greatest(product_usage_score, 0), 1), 0) * 0.40
                    + coalesce(least(greatest(marketing_engagement_score, 0), 1), 0) * 0.35
                    + coalesce(least(greatest(support_activity_score, 0), 1), 0) * 0.25
                )
                /
                nullif(
                    iff(product_usage_score is not null, 0.40, 0)
                    + iff(marketing_engagement_score is not null, 0.35, 0)
                    + iff(support_activity_score is not null, 0.25, 0),
                    0
                ),
                4
            ) as engagement_score,
            round(
                (
                    coalesce(1 - least(greatest(support_ticket_count / 25, 0), 1), 0) * 0.30
                    + coalesce(least(greatest(satisfaction_score / 5, 0), 1), 0) * 0.35
                    + coalesce(1 - least(greatest(response_time_minutes / 1440, 0), 1), 0) * 0.20
                    + coalesce(least(greatest(support_activity_score, 0), 1), 0) * 0.15
                )
                /
                nullif(
                    iff(support_ticket_count is not null, 0.30, 0)
                    + iff(satisfaction_score is not null, 0.35, 0)
                    + iff(response_time_minutes is not null, 0.20, 0)
                    + iff(support_activity_score is not null, 0.15, 0),
                    0
                ),
                4
            ) as support_health_score,
            case
                when upper(status_ranked.renewal_status) in ('RENEWED', 'ACTIVE', 'AUTO_RENEW', 'AUTO RENEWAL') then 0.95
                when upper(status_ranked.renewal_status) in ('OPEN', 'PENDING', 'IN_PROGRESS') then 0.65
                when upper(status_ranked.renewal_status) in ('AT RISK', 'AT_RISK', 'RISK', 'DOWNGRADE_RISK') then 0.35
                when upper(status_ranked.renewal_status) in ('CANCELLED', 'CANCELED', 'CHURNED', 'EXPIRED', 'LOST') then 0.10
                when status_ranked.renewal_status is not null then 0.55
                else null
            end as renewal_status_probability,
            case
                when license_expiration_date is null then null
                when datediff(day, metric_date, license_expiration_date) < 0 then 0.20
                when datediff(day, metric_date, license_expiration_date) <= 30 then 0.45
                when datediff(day, metric_date, license_expiration_date) <= 90 then 0.65
                else 0.85
            end as expiration_timing_score
        from aggregated
        left join status_ranked
            on status_ranked.golden_customer_id = aggregated.golden_customer_id
            and status_ranked.metric_date = aggregated.metric_date
    ),

    final_scores as (
        select
            *,
            coalesce(support_health_score, 1.0) as support_health_score_filled,
            round(
                (
                    coalesce(renewal_status_probability, 0) * 0.30
                    + coalesce(engagement_score, 0) * 0.25
                    + coalesce(product_adoption_score, 0) * 0.20
                    + coalesce(coalesce(support_health_score, 1.0), 0) * 0.20
                    + coalesce(expiration_timing_score, 0) * 0.05
                )
                /
                nullif(
                    iff(renewal_status_probability is not null, 0.30, 0)
                    + iff(engagement_score is not null, 0.25, 0)
                    + iff(product_adoption_score is not null, 0.20, 0)
                    + 0.20
                    + iff(expiration_timing_score is not null, 0.05, 0),
                    0
                ),
                4
            ) as renewal_probability
        from component_scores
    )

    select
        golden_customer_id,
        metric_date,
        round(
            coalesce(contract_value, 0)
            * (1 + coalesce(renewal_probability, 0))
            * (1 + ((coalesce(engagement_score, 0) + coalesce(product_adoption_score, 0)) / 4)),
            2
        ) as lifetime_value,
        product_adoption_score,
        engagement_score,
        support_health_score_filled as support_health_score,
        renewal_probability,
        product_usage_score,
        marketing_engagement_score,
        support_activity_score,
        support_ticket_count,
        satisfaction_score,
        response_time_minutes,
        active_users,
        active_days,
        feature_utilization_score,
        renewal_status,
        license_expiration_date,
        contract_value,
        seat_count,
        metric_components,
        'customer_enrichment_v1' as model_version,
        current_timestamp() as calculated_at,
        load_batch_id
    from final_scores
) source
on target.golden_customer_id = source.golden_customer_id
   and target.metric_date = source.metric_date
when matched then update set
    lifetime_value = source.lifetime_value,
    product_adoption_score = source.product_adoption_score,
    engagement_score = source.engagement_score,
    support_health_score = source.support_health_score,
    renewal_probability = source.renewal_probability,
    product_usage_score = source.product_usage_score,
    marketing_engagement_score = source.marketing_engagement_score,
    support_activity_score = source.support_activity_score,
    support_ticket_count = source.support_ticket_count,
    satisfaction_score = source.satisfaction_score,
    response_time_minutes = source.response_time_minutes,
    active_users = source.active_users,
    active_days = source.active_days,
    feature_utilization_score = source.feature_utilization_score,
    renewal_status = source.renewal_status,
    license_expiration_date = source.license_expiration_date,
    contract_value = source.contract_value,
    seat_count = source.seat_count,
    metric_components = source.metric_components,
    model_version = source.model_version,
    calculated_at = source.calculated_at,
    load_batch_id = source.load_batch_id
when not matched then insert (
    golden_customer_id,
    metric_date,
    lifetime_value,
    product_adoption_score,
    engagement_score,
    support_health_score,
    renewal_probability,
    product_usage_score,
    marketing_engagement_score,
    support_activity_score,
    support_ticket_count,
    satisfaction_score,
    response_time_minutes,
    active_users,
    active_days,
    feature_utilization_score,
    renewal_status,
    license_expiration_date,
    contract_value,
    seat_count,
    metric_components,
    model_version,
    calculated_at,
    load_batch_id
) values (
    source.golden_customer_id,
    source.metric_date,
    source.lifetime_value,
    source.product_adoption_score,
    source.engagement_score,
    source.support_health_score,
    source.renewal_probability,
    source.product_usage_score,
    source.marketing_engagement_score,
    source.support_activity_score,
    source.support_ticket_count,
    source.satisfaction_score,
    source.response_time_minutes,
    source.active_users,
    source.active_days,
    source.feature_utilization_score,
    source.renewal_status,
    source.license_expiration_date,
    source.contract_value,
    source.seat_count,
    source.metric_components,
    source.model_version,
    source.calculated_at,
    source.load_batch_id
);
