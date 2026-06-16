{{ config(
    unique_key=['metric_date', 'schema_name', 'table_name', 'expectation_suite_name'],
    cluster_by=['metric_date', 'schema_name', 'table_name']
) }}

with metric_rollup as (
    select
        to_date(measured_at) as metric_date,
        schema_name,
        table_name,
        expectation_suite_name,
        count(*) as total_rules,
        count_if(status = 'PASS') as passed_rules,
        count_if(status = 'FAIL') as failed_rules,
        count_if(status = 'WARN') as warned_rules,
        round(avg(quality_score), 4) as average_quality_score,
        min(case when rule_type = 'freshness' then status end) as freshness_status
    from {{ source('analytics_runtime', 'data_quality_metrics') }}
    group by
        to_date(measured_at),
        schema_name,
        table_name,
        expectation_suite_name
),

alert_rollup as (
    select
        to_date(created_at) as metric_date,
        schema_name,
        table_name,
        expectation_suite_name,
        count_if(severity = 'CRITICAL' and status = 'OPEN') as critical_alert_count,
        count_if(severity = 'WARNING' and status = 'OPEN') as warning_alert_count
    from {{ source('analytics_runtime', 'data_quality_alerts') }}
    group by
        to_date(created_at),
        schema_name,
        table_name,
        expectation_suite_name
)

    select
        metrics.metric_date,
        metrics.schema_name,
        metrics.table_name,
        coalesce(metrics.expectation_suite_name, 'unspecified') as expectation_suite_name,
        metrics.total_rules,
    metrics.passed_rules,
    metrics.failed_rules,
    metrics.warned_rules,
    metrics.average_quality_score,
    coalesce(alerts.critical_alert_count, 0) as critical_alert_count,
    coalesce(alerts.warning_alert_count, 0) as warning_alert_count,
    coalesce(metrics.freshness_status, 'NOT_EVALUATED') as freshness_status,
    current_timestamp() as refreshed_at
from metric_rollup metrics
left join alert_rollup alerts
    on alerts.metric_date = metrics.metric_date
    and alerts.schema_name = metrics.schema_name
    and alerts.table_name = metrics.table_name
    and coalesce(alerts.expectation_suite_name, '') = coalesce(metrics.expectation_suite_name, '')
