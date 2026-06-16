-- Builds model-ready Customer Health features from Gold enrichment metrics.

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema ANALYTICS;

set feature_start_date = dateadd(day, -180, current_date());

merge into CUSTOMER360_DB.ANALYTICS.customer_health_features target
using (
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
            'product_usage_score',
            enrichment.product_usage_score,
            'product_adoption_score',
            enrichment.product_adoption_score,
            'marketing_engagement_score',
            enrichment.marketing_engagement_score,
            'engagement_score',
            enrichment.engagement_score,
            'support_health_score',
            enrichment.support_health_score,
            'support_ticket_count',
            enrichment.support_ticket_count,
            'satisfaction_score',
            enrichment.satisfaction_score,
            'response_time_minutes',
            enrichment.response_time_minutes,
            'active_users',
            enrichment.active_users,
            'active_days',
            enrichment.active_days,
            'renewal_probability',
            enrichment.renewal_probability,
            'renewal_status',
            enrichment.renewal_status,
            'license_expiration_date',
            enrichment.license_expiration_date,
            'contract_value',
            enrichment.contract_value
        ) as feature_snapshot,
        current_timestamp() as created_at,
        enrichment.load_batch_id
    from CUSTOMER360_DB.GOLD.customer_enrichment_metrics enrichment
    left join CUSTOMER360_DB.GOLD.gold_customer_master master
        on master.golden_customer_id = enrichment.golden_customer_id
    where enrichment.metric_date >= $feature_start_date
) source
on target.golden_customer_id = source.golden_customer_id
   and target.score_date = source.score_date
when matched then update set
    company_name = source.company_name,
    email = source.email,
    industry = source.industry,
    lifetime_value = source.lifetime_value,
    product_usage_score = source.product_usage_score,
    product_adoption_score = source.product_adoption_score,
    marketing_engagement_score = source.marketing_engagement_score,
    engagement_score = source.engagement_score,
    support_health_score = source.support_health_score,
    support_ticket_count = source.support_ticket_count,
    satisfaction_score = source.satisfaction_score,
    response_time_minutes = source.response_time_minutes,
    active_users = source.active_users,
    active_days = source.active_days,
    renewal_probability = source.renewal_probability,
    renewal_status = source.renewal_status,
    license_expiration_date = source.license_expiration_date,
    contract_value = source.contract_value,
    seat_count = source.seat_count,
    derived_health_class = source.derived_health_class,
    feature_snapshot = source.feature_snapshot,
    created_at = source.created_at,
    load_batch_id = source.load_batch_id
when not matched then insert (
    golden_customer_id,
    score_date,
    company_name,
    email,
    industry,
    lifetime_value,
    product_usage_score,
    product_adoption_score,
    marketing_engagement_score,
    engagement_score,
    support_health_score,
    support_ticket_count,
    satisfaction_score,
    response_time_minutes,
    active_users,
    active_days,
    renewal_probability,
    renewal_status,
    license_expiration_date,
    contract_value,
    seat_count,
    derived_health_class,
    feature_snapshot,
    created_at,
    load_batch_id
) values (
    source.golden_customer_id,
    source.score_date,
    source.company_name,
    source.email,
    source.industry,
    source.lifetime_value,
    source.product_usage_score,
    source.product_adoption_score,
    source.marketing_engagement_score,
    source.engagement_score,
    source.support_health_score,
    source.support_ticket_count,
    source.satisfaction_score,
    source.response_time_minutes,
    source.active_users,
    source.active_days,
    source.renewal_probability,
    source.renewal_status,
    source.license_expiration_date,
    source.contract_value,
    source.seat_count,
    source.derived_health_class,
    source.feature_snapshot,
    source.created_at,
    source.load_batch_id
);
