{{ config(
    unique_key=['source_system', 'source_customer_id', 'metric_date'],
    cluster_by=['metric_date', 'source_system', 'source_customer_id']
) }}

with source_metrics as (
    select
        'MARKETO' as source_system,
        coalesce(lead_id, email, source_record_id) as source_customer_id,
        to_date(coalesce(last_modified_timestamp, created_date, load_timestamp)) as metric_date,
        null as product_usage_score,
        engagement_score as marketing_engagement_score,
        null as support_activity_score,
        null as login_count,
        null as active_days,
        null as active_users,
        null as feature_usage,
        iff(campaign is not null, 1, 0) as campaign_count,
        null as ticket_count,
        null as satisfaction_score,
        null as response_time_minutes,
        null as license_type,
        null as renewal_status,
        null as license_expiration_date,
        null as contract_value,
        null as seat_count,
        load_batch_id,
        coalesce(last_modified_timestamp, load_timestamp) as updated_at
    from {{ ref('marketo_lead_bronze') }}
    where coalesce(last_modified_timestamp, load_timestamp) is not null
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)', 'updated_at') }}

    union all

    select
        'ZENDESK',
        coalesce(customer_id, support_account_id, email, source_record_id),
        to_date(coalesce(last_ticket_created_at, last_modified_timestamp, load_timestamp)),
        null,
        null,
        round(
            least(coalesce(ticket_count, 0) / 25, 1) * 0.4
            + least(coalesce(satisfaction_score, 0) / 5, 1) * 0.4
            + greatest(0, 1 - least(coalesce(response_time_minutes, 0) / 1440, 1)) * 0.2,
            4
        ),
        null,
        null,
        null,
        null,
        null,
        ticket_count,
        satisfaction_score,
        response_time_minutes,
        null,
        null,
        null,
        null,
        null,
        load_batch_id,
        coalesce(last_modified_timestamp, load_timestamp)
    from {{ ref('zendesk_support_bronze') }}
    where coalesce(last_modified_timestamp, load_timestamp) is not null
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)', 'updated_at') }}

    union all

    select
        'PRODUCT_USAGE',
        coalesce(customer_id, source_record_id),
        event_date,
        round(
            least(coalesce(login_count, 0) / 100, 1) * 0.4
            + least(coalesce(active_days, 0) / 30, 1) * 0.3
            + least(coalesce(active_users, 0) / 50, 1) * 0.3,
            4
        ),
        null,
        null,
        login_count,
        active_days,
        active_users,
        feature_usage,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        load_batch_id,
        coalesce(last_modified_timestamp, load_timestamp)
    from {{ ref('product_usage_bronze') }}
    where coalesce(last_modified_timestamp, load_timestamp) is not null
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)', 'updated_at') }}

    union all

    select
        'LICENSING',
        coalesce(customer_id, license_id, source_record_id),
        expiration_date,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        upper(trim(license_type)),
        upper(trim(renewal_status)),
        expiration_date,
        contract_value,
        seat_count,
        load_batch_id,
        coalesce(last_modified_timestamp, load_timestamp)
    from {{ ref('licensing_customer_bronze') }}
    where coalesce(last_modified_timestamp, load_timestamp) is not null
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)', 'updated_at') }}
)

select
    source_system,
    source_customer_id,
    metric_date,
    round(avg(product_usage_score), 4) as product_usage_score,
    round(avg(marketing_engagement_score), 4) as marketing_engagement_score,
    round(avg(support_activity_score), 4) as support_activity_score,
    sum(login_count) as login_count,
    max(active_days) as active_days,
    sum(active_users) as active_users,
    max(feature_usage) as feature_usage,
    sum(campaign_count) as campaign_count,
    sum(ticket_count) as ticket_count,
    round(avg(satisfaction_score), 4) as satisfaction_score,
    round(avg(response_time_minutes), 4) as response_time_minutes,
    max(license_type) as license_type,
    max(renewal_status) as renewal_status,
    min(license_expiration_date) as license_expiration_date,
    sum(contract_value) as contract_value,
    sum(seat_count) as seat_count,
    max(load_batch_id) as load_batch_id,
    current_timestamp() as updated_at
from source_metrics
where source_customer_id is not null
  and metric_date is not null
group by source_system, source_customer_id, metric_date
