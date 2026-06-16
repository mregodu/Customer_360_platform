-- Builds Domo-ready reporting datasets for executive, Customer Success, and partner dashboards.
-- Inputs:
--   CUSTOMER360_DB.ANALYTICS.customer_health_scores
--   CUSTOMER360_DB.ANALYTICS.data_quality_dashboard_daily
--   CUSTOMER360_DB.GOLD.gold_customer_master
--   CUSTOMER360_DB.GOLD.gold_customer_clusters
--   CUSTOMER360_DB.GOLD.customer_enrichment_metrics
--   CUSTOMER360_DB.SILVER.silver_partner_profile
-- Outputs:
--   CUSTOMER360_DB.ANALYTICS.executive_customer_kpis_daily
--   CUSTOMER360_DB.ANALYTICS.customer_success_account_daily
--   CUSTOMER360_DB.ANALYTICS.partner_performance_daily
--   CUSTOMER360_DB.ANALYTICS.customer_health_drilldown
--   CUSTOMER360_DB.ANALYTICS.executive_segment_health_daily

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema ANALYTICS;

set metric_start_date = dateadd(day, -90, current_date());

merge into CUSTOMER360_DB.ANALYTICS.executive_customer_kpis_daily target
using (
    with scores as (
        select *
        from CUSTOMER360_DB.ANALYTICS.customer_health_scores
        where score_date >= $metric_start_date
    ),

    cluster_rollup as (
        select
            count(*) as total_clusters,
            sum(cluster_size) as total_source_members,
            avg(confidence_score) as match_accuracy_estimate
        from CUSTOMER360_DB.GOLD.gold_customer_clusters
    ),

    quality_rollup as (
        select
            metric_date,
            round(avg(average_quality_score), 4) as data_quality_score
        from CUSTOMER360_DB.ANALYTICS.data_quality_dashboard_daily
        where metric_date >= $metric_start_date
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
        round(
            coalesce(
                1 - (
                    max(cluster_rollup.total_clusters)
                    / nullif(max(cluster_rollup.total_source_members), 0)
                ),
                0
            ),
            4
        ) as duplicate_reduction_rate,
        round(coalesce(max(cluster_rollup.match_accuracy_estimate), 0), 4) as match_accuracy_estimate,
        coalesce(max(quality_rollup.data_quality_score), 1.0) as data_quality_score,
        current_timestamp() as refreshed_at
    from scores
    left join CUSTOMER360_DB.GOLD.gold_customer_master master
        on master.golden_customer_id = scores.golden_customer_id
    cross join cluster_rollup
    left join quality_rollup
        on quality_rollup.metric_date = scores.score_date
    group by scores.score_date
) source
on target.metric_date = source.metric_date
when matched then update set
    total_customers = source.total_customers,
    new_customers = source.new_customers,
    active_customers = source.active_customers,
    high_engagement_customers = source.high_engagement_customers,
    at_risk_customers = source.at_risk_customers,
    churn_risk_customers = source.churn_risk_customers,
    total_lifetime_value = source.total_lifetime_value,
    average_engagement_score = source.average_engagement_score,
    average_adoption_score = source.average_adoption_score,
    average_renewal_probability = source.average_renewal_probability,
    duplicate_reduction_rate = source.duplicate_reduction_rate,
    match_accuracy_estimate = source.match_accuracy_estimate,
    data_quality_score = source.data_quality_score,
    refreshed_at = source.refreshed_at
when not matched then insert (
    metric_date,
    total_customers,
    new_customers,
    active_customers,
    high_engagement_customers,
    at_risk_customers,
    churn_risk_customers,
    total_lifetime_value,
    average_engagement_score,
    average_adoption_score,
    average_renewal_probability,
    duplicate_reduction_rate,
    match_accuracy_estimate,
    data_quality_score,
    refreshed_at
) values (
    source.metric_date,
    source.total_customers,
    source.new_customers,
    source.active_customers,
    source.high_engagement_customers,
    source.at_risk_customers,
    source.churn_risk_customers,
    source.total_lifetime_value,
    source.average_engagement_score,
    source.average_adoption_score,
    source.average_renewal_probability,
    source.duplicate_reduction_rate,
    source.match_accuracy_estimate,
    source.data_quality_score,
    source.refreshed_at
);

merge into CUSTOMER360_DB.ANALYTICS.customer_success_account_daily target
using (
    select
        scores.golden_customer_id,
        scores.score_date as metric_date,
        coalesce(master.company_name, scores.company_name) as company_name,
        master.industry,
        master.customer_status,
        scores.health_class,
        coalesce(scores.renewal_probability, enrichment.renewal_probability) as renewal_probability,
        coalesce(scores.engagement_score, enrichment.engagement_score) as engagement_score,
        coalesce(scores.adoption_score, enrichment.product_adoption_score) as adoption_score,
        coalesce(scores.support_ticket_count, enrichment.support_ticket_count) as support_ticket_count,
        coalesce(scores.satisfaction_score, enrichment.satisfaction_score) as satisfaction_score,
        coalesce(scores.active_users, enrichment.active_users) as active_users,
        enrichment.license_expiration_date,
        enrichment.renewal_status,
        'UNASSIGNED' as owner_team,
        current_timestamp() as refreshed_at
    from CUSTOMER360_DB.ANALYTICS.customer_health_scores scores
    left join CUSTOMER360_DB.GOLD.gold_customer_master master
        on master.golden_customer_id = scores.golden_customer_id
    left join CUSTOMER360_DB.GOLD.customer_enrichment_metrics enrichment
        on enrichment.golden_customer_id = scores.golden_customer_id
        and enrichment.metric_date = scores.score_date
    where scores.score_date >= $metric_start_date
) source
on target.golden_customer_id = source.golden_customer_id
    and target.metric_date = source.metric_date
when matched then update set
    company_name = source.company_name,
    industry = source.industry,
    customer_status = source.customer_status,
    health_class = source.health_class,
    renewal_probability = source.renewal_probability,
    engagement_score = source.engagement_score,
    adoption_score = source.adoption_score,
    support_ticket_count = source.support_ticket_count,
    satisfaction_score = source.satisfaction_score,
    active_users = source.active_users,
    license_expiration_date = source.license_expiration_date,
    renewal_status = source.renewal_status,
    owner_team = source.owner_team,
    refreshed_at = source.refreshed_at
when not matched then insert (
    golden_customer_id,
    metric_date,
    company_name,
    industry,
    customer_status,
    health_class,
    renewal_probability,
    engagement_score,
    adoption_score,
    support_ticket_count,
    satisfaction_score,
    active_users,
    license_expiration_date,
    renewal_status,
    owner_team,
    refreshed_at
) values (
    source.golden_customer_id,
    source.metric_date,
    source.company_name,
    source.industry,
    source.customer_status,
    source.health_class,
    source.renewal_probability,
    source.engagement_score,
    source.adoption_score,
    source.support_ticket_count,
    source.satisfaction_score,
    source.active_users,
    source.license_expiration_date,
    source.renewal_status,
    source.owner_team,
    source.refreshed_at
);

merge into CUSTOMER360_DB.ANALYTICS.partner_performance_daily target
using (
    with latest_score as (
        select max(score_date) as score_date
        from CUSTOMER360_DB.ANALYTICS.customer_health_scores
    ),

    latest_health as (
        select
            score_date,
            avg(1 - coalesce(churn_risk_score, 0)) as average_customer_health_score,
            count(distinct golden_customer_id) as active_customer_count
        from CUSTOMER360_DB.ANALYTICS.customer_health_scores
        where score_date = (select score_date from latest_score)
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
    from CUSTOMER360_DB.SILVER.silver_partner_profile partners
    left join latest_health
        on 1 = 1
    where coalesce(partners.is_deleted, false) = false
) source
on target.partner_id = source.partner_id
    and target.metric_date = source.metric_date
when matched then update set
    company_name = source.company_name,
    partner_tier = source.partner_tier,
    partner_region = source.partner_region,
    partner_status = source.partner_status,
    certification_count = source.certification_count,
    influenced_customer_count = source.influenced_customer_count,
    influenced_lifetime_value = source.influenced_lifetime_value,
    active_customer_count = source.active_customer_count,
    average_customer_health_score = source.average_customer_health_score,
    refreshed_at = source.refreshed_at
when not matched then insert (
    partner_id,
    metric_date,
    company_name,
    partner_tier,
    partner_region,
    partner_status,
    certification_count,
    influenced_customer_count,
    influenced_lifetime_value,
    active_customer_count,
    average_customer_health_score,
    refreshed_at
) values (
    source.partner_id,
    source.metric_date,
    source.company_name,
    source.partner_tier,
    source.partner_region,
    source.partner_status,
    source.certification_count,
    source.influenced_customer_count,
    source.influenced_lifetime_value,
    source.active_customer_count,
    source.average_customer_health_score,
    source.refreshed_at
);

merge into CUSTOMER360_DB.ANALYTICS.customer_health_drilldown target
using (
    select
        scores.golden_customer_id,
        scores.score_date as metric_date,
        master.cluster_id,
        coalesce(master.company_name, scores.company_name) as company_name,
        coalesce(master.email, scores.email) as email,
        master.phone,
        master.website_domain,
        master.industry,
        master.customer_status,
        scores.health_class,
        scores.classification_reason,
        scores.churn_risk_score,
        coalesce(scores.lifetime_value, enrichment.lifetime_value) as lifetime_value,
        coalesce(scores.product_usage_score, enrichment.product_usage_score) as product_usage_score,
        coalesce(scores.marketing_engagement_score, enrichment.marketing_engagement_score) as marketing_engagement_score,
        coalesce(scores.engagement_score, enrichment.engagement_score) as engagement_score,
        coalesce(scores.adoption_score, enrichment.product_adoption_score) as adoption_score,
        coalesce(scores.support_health_score, enrichment.support_health_score) as support_health_score,
        coalesce(scores.renewal_probability, enrichment.renewal_probability) as renewal_probability,
        coalesce(scores.support_ticket_count, enrichment.support_ticket_count) as support_ticket_count,
        coalesce(scores.satisfaction_score, enrichment.satisfaction_score) as satisfaction_score,
        coalesce(scores.active_users, enrichment.active_users) as active_users,
        enrichment.license_expiration_date,
        enrichment.renewal_status,
        'UNASSIGNED' as owner_team,
        master.primary_source_system,
        nullif(array_to_string(master.source_systems, ', '), '') as source_systems,
        coalesce(array_size(master.source_customer_ids), clusters.cluster_size) as source_customer_count,
        master.data_quality_score,
        current_timestamp() as refreshed_at
    from CUSTOMER360_DB.ANALYTICS.customer_health_scores scores
    left join CUSTOMER360_DB.GOLD.gold_customer_master master
        on master.golden_customer_id = scores.golden_customer_id
    left join CUSTOMER360_DB.GOLD.gold_customer_clusters clusters
        on clusters.golden_customer_id = scores.golden_customer_id
    left join CUSTOMER360_DB.GOLD.customer_enrichment_metrics enrichment
        on enrichment.golden_customer_id = scores.golden_customer_id
        and enrichment.metric_date = scores.score_date
    where scores.score_date >= $metric_start_date
) source
on target.golden_customer_id = source.golden_customer_id
    and target.metric_date = source.metric_date
when matched then update set
    cluster_id = source.cluster_id,
    company_name = source.company_name,
    email = source.email,
    phone = source.phone,
    website_domain = source.website_domain,
    industry = source.industry,
    customer_status = source.customer_status,
    health_class = source.health_class,
    classification_reason = source.classification_reason,
    churn_risk_score = source.churn_risk_score,
    lifetime_value = source.lifetime_value,
    product_usage_score = source.product_usage_score,
    marketing_engagement_score = source.marketing_engagement_score,
    engagement_score = source.engagement_score,
    adoption_score = source.adoption_score,
    support_health_score = source.support_health_score,
    renewal_probability = source.renewal_probability,
    support_ticket_count = source.support_ticket_count,
    satisfaction_score = source.satisfaction_score,
    active_users = source.active_users,
    license_expiration_date = source.license_expiration_date,
    renewal_status = source.renewal_status,
    owner_team = source.owner_team,
    primary_source_system = source.primary_source_system,
    source_systems = source.source_systems,
    source_customer_count = source.source_customer_count,
    data_quality_score = source.data_quality_score,
    refreshed_at = source.refreshed_at
when not matched then insert (
    golden_customer_id,
    metric_date,
    cluster_id,
    company_name,
    email,
    phone,
    website_domain,
    industry,
    customer_status,
    health_class,
    classification_reason,
    churn_risk_score,
    lifetime_value,
    product_usage_score,
    marketing_engagement_score,
    engagement_score,
    adoption_score,
    support_health_score,
    renewal_probability,
    support_ticket_count,
    satisfaction_score,
    active_users,
    license_expiration_date,
    renewal_status,
    owner_team,
    primary_source_system,
    source_systems,
    source_customer_count,
    data_quality_score,
    refreshed_at
) values (
    source.golden_customer_id,
    source.metric_date,
    source.cluster_id,
    source.company_name,
    source.email,
    source.phone,
    source.website_domain,
    source.industry,
    source.customer_status,
    source.health_class,
    source.classification_reason,
    source.churn_risk_score,
    source.lifetime_value,
    source.product_usage_score,
    source.marketing_engagement_score,
    source.engagement_score,
    source.adoption_score,
    source.support_health_score,
    source.renewal_probability,
    source.support_ticket_count,
    source.satisfaction_score,
    source.active_users,
    source.license_expiration_date,
    source.renewal_status,
    source.owner_team,
    source.primary_source_system,
    source.source_systems,
    source.source_customer_count,
    source.data_quality_score,
    source.refreshed_at
);

merge into CUSTOMER360_DB.ANALYTICS.executive_segment_health_daily target
using (
    with base as (
        select
            scores.golden_customer_id,
            scores.score_date as metric_date,
            scores.health_class,
            scores.churn_risk_score,
            coalesce(scores.renewal_probability, enrichment.renewal_probability) as renewal_probability,
            coalesce(scores.engagement_score, enrichment.engagement_score) as engagement_score,
            coalesce(scores.adoption_score, enrichment.product_adoption_score) as adoption_score,
            coalesce(scores.support_health_score, enrichment.support_health_score) as support_health_score,
            coalesce(scores.lifetime_value, enrichment.lifetime_value) as lifetime_value,
            coalesce(nullif(master.industry, ''), 'UNKNOWN') as industry,
            coalesce(nullif(master.customer_status, ''), 'UNKNOWN') as customer_status,
            coalesce(nullif(master.primary_source_system, ''), 'UNKNOWN') as primary_source_system,
            coalesce(nullif(master.country, ''), 'UNKNOWN') as country
        from CUSTOMER360_DB.ANALYTICS.customer_health_scores scores
        left join CUSTOMER360_DB.GOLD.gold_customer_master master
            on master.golden_customer_id = scores.golden_customer_id
        left join CUSTOMER360_DB.GOLD.customer_enrichment_metrics enrichment
            on enrichment.golden_customer_id = scores.golden_customer_id
            and enrichment.metric_date = scores.score_date
        where scores.score_date >= $metric_start_date
    ),

    segment_rows as (
        select
            metric_date,
            golden_customer_id,
            health_class,
            churn_risk_score,
            renewal_probability,
            engagement_score,
            adoption_score,
            support_health_score,
            lifetime_value,
            'Industry' as segment_type,
            industry as segment_value
        from base

        union all

        select
            metric_date,
            golden_customer_id,
            health_class,
            churn_risk_score,
            renewal_probability,
            engagement_score,
            adoption_score,
            support_health_score,
            lifetime_value,
            'Customer Status' as segment_type,
            customer_status as segment_value
        from base

        union all

        select
            metric_date,
            golden_customer_id,
            health_class,
            churn_risk_score,
            renewal_probability,
            engagement_score,
            adoption_score,
            support_health_score,
            lifetime_value,
            'Primary Source' as segment_type,
            primary_source_system as segment_value
        from base

        union all

        select
            metric_date,
            golden_customer_id,
            health_class,
            churn_risk_score,
            renewal_probability,
            engagement_score,
            adoption_score,
            support_health_score,
            lifetime_value,
            'Country' as segment_type,
            country as segment_value
        from base

        union all

        select
            metric_date,
            golden_customer_id,
            health_class,
            churn_risk_score,
            renewal_probability,
            engagement_score,
            adoption_score,
            support_health_score,
            lifetime_value,
            'Health Class' as segment_type,
            health_class as segment_value
        from base
    )

    select
        metric_date,
        segment_type,
        coalesce(nullif(segment_value, ''), 'UNKNOWN') as segment_value,
        count(distinct golden_customer_id) as customer_count,
        count_if(health_class = 'Healthy') as healthy_customers,
        count_if(health_class = 'At Risk') as at_risk_customers,
        count_if(health_class = 'Churn Risk') as churn_risk_customers,
        round(avg(churn_risk_score), 4) as avg_churn_risk_score,
        round(avg(renewal_probability), 4) as avg_renewal_probability,
        round(avg(engagement_score), 4) as avg_engagement_score,
        round(avg(adoption_score), 4) as avg_adoption_score,
        round(avg(support_health_score), 4) as avg_support_health_score,
        round(sum(coalesce(lifetime_value, 0)), 2) as total_lifetime_value,
        round(avg(lifetime_value), 2) as avg_lifetime_value,
        current_timestamp() as refreshed_at
    from segment_rows
    group by metric_date, segment_type, coalesce(nullif(segment_value, ''), 'UNKNOWN')
) source
on target.metric_date = source.metric_date
    and target.segment_type = source.segment_type
    and target.segment_value = source.segment_value
when matched then update set
    customer_count = source.customer_count,
    healthy_customers = source.healthy_customers,
    at_risk_customers = source.at_risk_customers,
    churn_risk_customers = source.churn_risk_customers,
    avg_churn_risk_score = source.avg_churn_risk_score,
    avg_renewal_probability = source.avg_renewal_probability,
    avg_engagement_score = source.avg_engagement_score,
    avg_adoption_score = source.avg_adoption_score,
    avg_support_health_score = source.avg_support_health_score,
    total_lifetime_value = source.total_lifetime_value,
    avg_lifetime_value = source.avg_lifetime_value,
    refreshed_at = source.refreshed_at
when not matched then insert (
    metric_date,
    segment_type,
    segment_value,
    customer_count,
    healthy_customers,
    at_risk_customers,
    churn_risk_customers,
    avg_churn_risk_score,
    avg_renewal_probability,
    avg_engagement_score,
    avg_adoption_score,
    avg_support_health_score,
    total_lifetime_value,
    avg_lifetime_value,
    refreshed_at
) values (
    source.metric_date,
    source.segment_type,
    source.segment_value,
    source.customer_count,
    source.healthy_customers,
    source.at_risk_customers,
    source.churn_risk_customers,
    source.avg_churn_risk_score,
    source.avg_renewal_probability,
    source.avg_engagement_score,
    source.avg_adoption_score,
    source.avg_support_health_score,
    source.total_lifetime_value,
    source.avg_lifetime_value,
    source.refreshed_at
);
