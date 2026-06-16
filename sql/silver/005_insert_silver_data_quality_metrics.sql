-- Inserts Silver-layer data-quality metrics into ANALYTICS.data_quality_metrics.

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema ANALYTICS;

insert into CUSTOMER360_DB.ANALYTICS.data_quality_metrics (
    metric_id,
    run_id,
    source_system,
    schema_name,
    table_name,
    rule_name,
    rule_type,
    measured_at,
    passed_count,
    failed_count,
    total_count,
    quality_score,
    threshold,
    status,
    details
)
with customer_metrics as (
    select
        source_system,
        count(*) as total_count,
        count_if(source_customer_id is not null) as id_passed,
        count_if(email is null or regexp_like(email, '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$')) as email_passed,
        count_if(phone is null or length(phone) between 7 and 15) as phone_passed,
        avg(data_quality_score) as avg_quality_score
    from CUSTOMER360_DB.SILVER.silver_customer
    group by source_system
),
partner_metrics as (
    select
        source_system,
        count(*) as total_count,
        count_if(partner_id is not null) as id_passed,
        count_if(email is null or regexp_like(email, '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$')) as email_passed,
        count_if(phone is null or length(phone) between 7 and 15) as phone_passed,
        avg(data_quality_score) as avg_quality_score
    from CUSTOMER360_DB.SILVER.silver_partner_profile
    group by source_system
),
rules as (
    select
        source_system,
        'silver_customer' as table_name,
        'source_customer_id_required' as rule_name,
        'completeness' as rule_type,
        id_passed as passed_count,
        total_count - id_passed as failed_count,
        total_count,
        id_passed / nullif(total_count, 0) as quality_score,
        avg_quality_score
    from customer_metrics
    union all
    select source_system, 'silver_customer', 'valid_email', 'validity',
        email_passed, total_count - email_passed, total_count,
        email_passed / nullif(total_count, 0), avg_quality_score
    from customer_metrics
    union all
    select source_system, 'silver_customer', 'valid_phone', 'validity',
        phone_passed, total_count - phone_passed, total_count,
        phone_passed / nullif(total_count, 0), avg_quality_score
    from customer_metrics
    union all
    select source_system, 'silver_partner_profile', 'partner_id_required', 'completeness',
        id_passed, total_count - id_passed, total_count,
        id_passed / nullif(total_count, 0), avg_quality_score
    from partner_metrics
    union all
    select source_system, 'silver_partner_profile', 'valid_email', 'validity',
        email_passed, total_count - email_passed, total_count,
        email_passed / nullif(total_count, 0), avg_quality_score
    from partner_metrics
    union all
    select source_system, 'silver_partner_profile', 'valid_phone', 'validity',
        phone_passed, total_count - phone_passed, total_count,
        phone_passed / nullif(total_count, 0), avg_quality_score
    from partner_metrics
)
select
    uuid_string() as metric_id,
    uuid_string() as run_id,
    source_system,
    'SILVER' as schema_name,
    table_name,
    rule_name,
    rule_type,
    current_timestamp() as measured_at,
    passed_count,
    failed_count,
    total_count,
    round(coalesce(quality_score, 1), 4) as quality_score,
    0.95 as threshold,
    iff(coalesce(quality_score, 1) >= 0.95, 'PASS', 'FAIL') as status,
    object_construct_keep_null('average_data_quality_score', round(avg_quality_score, 4)) as details
from rules;
