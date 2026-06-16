-- Analytics tables support Domo dashboards, customer health reporting, and operations monitoring.

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema ANALYTICS;

create table if not exists customer_health_scores (
    golden_customer_id varchar not null,
    score_date date not null,
    company_name varchar,
    email varchar,
    industry varchar,
    lifetime_value number(18, 2),
    product_usage_score number(10, 4),
    marketing_engagement_score number(10, 4),
    engagement_score number(10, 4),
    adoption_score number(10, 4),
    renewal_probability number(10, 4),
    support_activity_score number(10, 4),
    support_health_score number(10, 4),
    satisfaction_score number(10, 4),
    support_ticket_count number(18, 0),
    active_users number(18, 0),
    churn_risk_score number(10, 4),
    health_class varchar not null,
    classification_reason varchar,
    model_version varchar,
    model_algorithm varchar,
    class_probabilities variant,
    feature_snapshot variant,
    scored_at timestamp_ntz not null default current_timestamp(),
    load_batch_id varchar,
    primary key (golden_customer_id, score_date) not enforced
)
cluster by (score_date, health_class, golden_customer_id)
comment = 'Domo-ready customer health, renewal, and churn-risk scores';

alter table if exists customer_health_scores
    add column if not exists product_usage_score number(10, 4);
alter table if exists customer_health_scores
    add column if not exists marketing_engagement_score number(10, 4);
alter table if exists customer_health_scores
    add column if not exists support_health_score number(10, 4);
alter table if exists customer_health_scores
    add column if not exists model_algorithm varchar;
alter table if exists customer_health_scores
    add column if not exists class_probabilities variant;
alter table if exists customer_health_scores
    add column if not exists feature_snapshot variant;

create table if not exists customer_health_features (
    golden_customer_id varchar not null,
    score_date date not null,
    company_name varchar,
    email varchar,
    industry varchar,
    lifetime_value number(18, 2),
    product_usage_score number(10, 4),
    product_adoption_score number(10, 4),
    marketing_engagement_score number(10, 4),
    engagement_score number(10, 4),
    support_health_score number(10, 4),
    support_ticket_count number(18, 0),
    satisfaction_score number(10, 4),
    response_time_minutes number(18, 4),
    active_users number(18, 0),
    active_days number(18, 0),
    renewal_probability number(10, 4),
    renewal_status varchar,
    license_expiration_date date,
    contract_value number(18, 2),
    seat_count number(18, 0),
    derived_health_class varchar,
    feature_snapshot variant,
    created_at timestamp_ntz not null default current_timestamp(),
    load_batch_id varchar,
    primary key (golden_customer_id, score_date) not enforced
)
cluster by (score_date, derived_health_class, golden_customer_id)
comment = 'Model-ready Customer Health feature table built from Gold enrichment metrics';

create table if not exists customer_health_model_evaluations (
    model_version varchar not null,
    algorithm varchar not null,
    trained_at timestamp_ntz not null,
    training_rows number(18, 0),
    validation_rows number(18, 0),
    accuracy number(10, 6),
    macro_f1 number(10, 6),
    metrics variant,
    load_batch_id varchar,
    primary key (model_version, algorithm, trained_at) not enforced
)
cluster by (to_date(trained_at), algorithm, model_version)
comment = 'Customer Health model evaluation metrics for Logistic Regression, Random Forest, and XGBoost';

create table if not exists executive_customer_kpis_daily (
    metric_date date not null,
    total_customers number(18, 0),
    new_customers number(18, 0),
    active_customers number(18, 0),
    high_engagement_customers number(18, 0),
    at_risk_customers number(18, 0),
    churn_risk_customers number(18, 0),
    total_lifetime_value number(18, 2),
    average_engagement_score number(10, 4),
    average_adoption_score number(10, 4),
    average_renewal_probability number(10, 4),
    duplicate_reduction_rate number(10, 4),
    match_accuracy_estimate number(10, 4),
    data_quality_score number(10, 4),
    refreshed_at timestamp_ntz not null default current_timestamp(),
    primary key (metric_date) not enforced
)
cluster by (metric_date)
comment = 'Executive dashboard daily KPI snapshot';

create table if not exists customer_success_account_daily (
    golden_customer_id varchar not null,
    metric_date date not null,
    company_name varchar,
    industry varchar,
    customer_status varchar,
    health_class varchar,
    renewal_probability number(10, 4),
    engagement_score number(10, 4),
    adoption_score number(10, 4),
    support_ticket_count number(18, 0),
    satisfaction_score number(10, 4),
    active_users number(18, 0),
    license_expiration_date date,
    renewal_status varchar,
    owner_team varchar,
    refreshed_at timestamp_ntz not null default current_timestamp(),
    primary key (golden_customer_id, metric_date) not enforced
)
cluster by (metric_date, health_class, golden_customer_id)
comment = 'Customer Success dashboard account-level daily snapshot';

create table if not exists partner_performance_daily (
    partner_id varchar not null,
    metric_date date not null,
    company_name varchar,
    partner_tier varchar,
    partner_region varchar,
    partner_status varchar,
    certification_count number(18, 0),
    influenced_customer_count number(18, 0),
    influenced_lifetime_value number(18, 2),
    active_customer_count number(18, 0),
    average_customer_health_score number(10, 4),
    refreshed_at timestamp_ntz not null default current_timestamp(),
    primary key (partner_id, metric_date) not enforced
)
cluster by (metric_date, partner_region, partner_tier)
comment = 'Partner dashboard daily performance and certification snapshot';

create table if not exists customer_health_drilldown (
    golden_customer_id varchar not null,
    metric_date date not null,
    cluster_id varchar,
    company_name varchar,
    email varchar,
    phone varchar,
    website_domain varchar,
    industry varchar,
    customer_status varchar,
    health_class varchar,
    classification_reason varchar,
    churn_risk_score number(10, 4),
    lifetime_value number(18, 2),
    product_usage_score number(10, 4),
    marketing_engagement_score number(10, 4),
    engagement_score number(10, 4),
    adoption_score number(10, 4),
    support_health_score number(10, 4),
    renewal_probability number(10, 4),
    support_ticket_count number(18, 0),
    satisfaction_score number(10, 4),
    active_users number(18, 0),
    license_expiration_date date,
    renewal_status varchar,
    owner_team varchar,
    primary_source_system varchar,
    source_systems varchar,
    source_customer_count number(18, 0),
    data_quality_score number(10, 4),
    refreshed_at timestamp_ntz not null default current_timestamp(),
    primary key (golden_customer_id, metric_date) not enforced
)
cluster by (metric_date, health_class, golden_customer_id)
comment = 'Account-level Domo drilldown dataset for health drivers, renewal signals, and master-data context';

create table if not exists executive_segment_health_daily (
    metric_date date not null,
    segment_type varchar not null,
    segment_value varchar not null,
    customer_count number(18, 0),
    healthy_customers number(18, 0),
    at_risk_customers number(18, 0),
    churn_risk_customers number(18, 0),
    avg_churn_risk_score number(10, 4),
    avg_renewal_probability number(10, 4),
    avg_engagement_score number(10, 4),
    avg_adoption_score number(10, 4),
    avg_support_health_score number(10, 4),
    total_lifetime_value number(18, 2),
    avg_lifetime_value number(18, 2),
    refreshed_at timestamp_ntz not null default current_timestamp(),
    primary key (metric_date, segment_type, segment_value) not enforced
)
cluster by (metric_date, segment_type, segment_value)
comment = 'Executive Domo drilldown dataset for segment-level customer health, renewal, and value analysis';

create table if not exists data_quality_metrics (
    metric_id varchar not null,
    run_id varchar not null,
    source_system varchar,
    schema_name varchar not null,
    table_name varchar not null,
    expectation_suite_name varchar,
    rule_name varchar not null,
    rule_type varchar not null,
    dimension varchar,
    severity varchar,
    measured_at timestamp_ntz not null default current_timestamp(),
    passed_count number(18, 0),
    failed_count number(18, 0),
    total_count number(18, 0),
    quality_score number(10, 4),
    threshold number(10, 4),
    status varchar not null,
    details variant,
    primary key (metric_id) not enforced
)
cluster by (schema_name, table_name, to_date(measured_at))
comment = 'Great Expectations and data-quality monitoring results';

alter table if exists data_quality_metrics
    add column if not exists expectation_suite_name varchar;
alter table if exists data_quality_metrics
    add column if not exists dimension varchar;
alter table if exists data_quality_metrics
    add column if not exists severity varchar;

create table if not exists data_quality_validation_runs (
    run_id varchar not null,
    expectation_suite_name varchar not null,
    schema_name varchar not null,
    table_name varchar not null,
    started_at timestamp_ntz not null,
    completed_at timestamp_ntz,
    status varchar not null,
    row_count number(18, 0),
    metrics_total number(18, 0),
    metrics_failed number(18, 0),
    metrics_warned number(18, 0),
    quality_score number(10, 4),
    details variant,
    primary key (run_id, expectation_suite_name, schema_name, table_name) not enforced
)
cluster by (to_date(started_at), status, schema_name, table_name)
comment = 'Run-level Great Expectations validation summaries';

create table if not exists data_quality_alerts (
    alert_id varchar not null,
    run_id varchar not null,
    schema_name varchar not null,
    table_name varchar not null,
    expectation_suite_name varchar not null,
    rule_name varchar not null,
    severity varchar not null,
    status varchar not null,
    message varchar,
    created_at timestamp_ntz not null default current_timestamp(),
    acknowledged_at timestamp_ntz,
    resolved_at timestamp_ntz,
    details variant,
    primary key (alert_id) not enforced
)
cluster by (status, severity, to_date(created_at), schema_name, table_name)
comment = 'Open and historical data-quality alerts generated from failed expectations';

create table if not exists data_quality_dashboard_daily (
    metric_date date not null,
    schema_name varchar not null,
    table_name varchar not null,
    expectation_suite_name varchar,
    total_rules number(18, 0),
    passed_rules number(18, 0),
    failed_rules number(18, 0),
    warned_rules number(18, 0),
    average_quality_score number(10, 4),
    critical_alert_count number(18, 0),
    warning_alert_count number(18, 0),
    freshness_status varchar,
    refreshed_at timestamp_ntz not null default current_timestamp(),
    primary key (metric_date, schema_name, table_name, expectation_suite_name) not enforced
)
cluster by (metric_date, schema_name, table_name)
comment = 'Daily dashboard aggregate for data quality monitoring';

create table if not exists pipeline_execution_log (
    pipeline_execution_id varchar not null,
    pipeline_name varchar not null,
    run_id varchar not null,
    environment varchar,
    source_system varchar,
    target_table varchar,
    start_time timestamp_ntz not null,
    end_time timestamp_ntz,
    duration_seconds number(18, 6),
    status varchar not null,
    rows_read number(18, 0),
    rows_inserted number(18, 0),
    rows_updated number(18, 0),
    rows_deleted number(18, 0),
    rows_processed number(18, 0),
    error_message varchar,
    error_details variant,
    metadata variant,
    created_at timestamp_ntz not null default current_timestamp(),
    primary key (pipeline_execution_id) not enforced
)
cluster by (pipeline_name, status, to_date(start_time))
comment = 'Pipeline-level execution log for operations monitoring';

alter table if exists pipeline_execution_log
    add column if not exists duration_seconds number(18, 6);
alter table if exists pipeline_execution_log
    add column if not exists rows_processed number(18, 0);
alter table if exists pipeline_execution_log
    add column if not exists error_details variant;

create table if not exists etl_audit_log (
    audit_id varchar not null,
    run_id varchar not null,
    pipeline_name varchar not null,
    source_table varchar,
    transformation_step varchar not null,
    destination_table varchar,
    execution_timestamp timestamp_ntz not null default current_timestamp(),
    row_count number(18, 0),
    rows_processed number(18, 0),
    checksum varchar,
    status varchar not null,
    error_details variant,
    details variant,
    primary key (audit_id) not enforced
)
cluster by (pipeline_name, to_date(execution_timestamp))
comment = 'Step-level ETL lineage and audit table';

alter table if exists etl_audit_log
    add column if not exists rows_processed number(18, 0);
alter table if exists etl_audit_log
    add column if not exists error_details variant;

create table if not exists domo_dataset_refresh_log (
    refresh_id varchar not null,
    dataset_name varchar not null,
    domo_dataset_id varchar,
    source_table varchar not null,
    refresh_started_at timestamp_ntz not null,
    refresh_completed_at timestamp_ntz,
    status varchar not null,
    rows_published number(18, 0),
    error_message varchar,
    metadata variant,
    primary key (refresh_id) not enforced
)
cluster by (dataset_name, to_date(refresh_started_at))
comment = 'Domo dataset refresh history and reconciliation log';

-- Optional performance enhancement for dashboard workloads:
-- define materialized views or dynamic tables over the daily snapshot tables once
-- dashboard filter patterns and Domo extract cadence are stable.
