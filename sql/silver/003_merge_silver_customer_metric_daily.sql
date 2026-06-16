-- Merges standardized daily customer metrics from behavioral and operational bronze sources.

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema SILVER;

set since_watermark = '1900-01-01 00:00:00';

merge into CUSTOMER360_DB.SILVER.silver_customer_metric_daily target
using (
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
        current_timestamp() as updated_at
    from CUSTOMER360_DB.BRONZE.marketo_lead_bronze
    where coalesce(last_modified_timestamp, load_timestamp) > to_timestamp_ntz($since_watermark)

    union all

    select
        'ZENDESK',
        coalesce(customer_id, support_account_id, email, source_record_id),
        to_date(coalesce(last_ticket_created_at, last_modified_timestamp, load_timestamp)),
        null,
        null,
        round(
            least(coalesce(ticket_count, 0) / 25, 1) * 0.4 +
            least(coalesce(satisfaction_score, 0) / 5, 1) * 0.4 +
            greatest(0, 1 - least(coalesce(response_time_minutes, 0) / 1440, 1)) * 0.2,
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
        current_timestamp()
    from CUSTOMER360_DB.BRONZE.zendesk_support_bronze
    where coalesce(last_modified_timestamp, load_timestamp) > to_timestamp_ntz($since_watermark)

    union all

    select
        'PRODUCT_USAGE',
        coalesce(customer_id, source_record_id),
        event_date,
        round(
            least(coalesce(login_count, 0) / 100, 1) * 0.4 +
            least(coalesce(active_days, 0) / 30, 1) * 0.3 +
            least(coalesce(active_users, 0) / 50, 1) * 0.3,
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
        current_timestamp()
    from CUSTOMER360_DB.BRONZE.product_usage_bronze
    where coalesce(last_modified_timestamp, load_timestamp) > to_timestamp_ntz($since_watermark)

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
        current_timestamp()
    from CUSTOMER360_DB.BRONZE.licensing_customer_bronze
    where coalesce(last_modified_timestamp, load_timestamp) > to_timestamp_ntz($since_watermark)
) source
on target.source_system = source.source_system
   and target.source_customer_id = source.source_customer_id
   and target.metric_date = source.metric_date
when matched then update set
    product_usage_score = source.product_usage_score,
    marketing_engagement_score = source.marketing_engagement_score,
    support_activity_score = source.support_activity_score,
    login_count = source.login_count,
    active_days = source.active_days,
    active_users = source.active_users,
    feature_usage = source.feature_usage,
    campaign_count = source.campaign_count,
    ticket_count = source.ticket_count,
    satisfaction_score = source.satisfaction_score,
    response_time_minutes = source.response_time_minutes,
    license_type = source.license_type,
    renewal_status = source.renewal_status,
    license_expiration_date = source.license_expiration_date,
    contract_value = source.contract_value,
    seat_count = source.seat_count,
    load_batch_id = source.load_batch_id,
    updated_at = source.updated_at
when not matched then insert (
    source_system,
    source_customer_id,
    metric_date,
    product_usage_score,
    marketing_engagement_score,
    support_activity_score,
    login_count,
    active_days,
    active_users,
    feature_usage,
    campaign_count,
    ticket_count,
    satisfaction_score,
    response_time_minutes,
    license_type,
    renewal_status,
    license_expiration_date,
    contract_value,
    seat_count,
    load_batch_id,
    updated_at
) values (
    source.source_system,
    source.source_customer_id,
    source.metric_date,
    source.product_usage_score,
    source.marketing_engagement_score,
    source.support_activity_score,
    source.login_count,
    source.active_days,
    source.active_users,
    source.feature_usage,
    source.campaign_count,
    source.ticket_count,
    source.satisfaction_score,
    source.response_time_minutes,
    source.license_type,
    source.renewal_status,
    source.license_expiration_date,
    source.contract_value,
    source.seat_count,
    source.load_batch_id,
    source.updated_at
);
