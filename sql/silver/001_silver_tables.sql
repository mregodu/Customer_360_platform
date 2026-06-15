-- Silver tables store standardized, conformed records ready for matching and enrichment.

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema SILVER;

create table if not exists silver_customer (
    source_system varchar not null,
    source_customer_id varchar not null,
    source_record_id varchar,
    company_name varchar,
    company_name_normalized varchar,
    email varchar,
    email_domain varchar,
    phone varchar,
    address_line_1 varchar,
    address_line_2 varchar,
    city varchar,
    state_region varchar,
    postal_code varchar,
    country varchar,
    address varchar,
    website_domain varchar,
    industry varchar,
    customer_status varchar,
    created_date timestamp_ntz,
    last_modified_timestamp timestamp_ntz,
    is_deleted boolean not null default false,
    source_priority number(5, 0) not null default 100,
    completeness_score number(5, 4),
    data_quality_score number(5, 4),
    standardization_version varchar not null default 'v1',
    record_hash varchar,
    load_batch_id varchar,
    standardized_at timestamp_ntz not null default current_timestamp(),
    primary key (source_system, source_customer_id) not enforced
)
cluster by (source_system, source_customer_id, to_date(last_modified_timestamp))
comment = 'Standardized customer identity records used by Splink matching';

create table if not exists silver_customer_metric_daily (
    source_system varchar not null,
    source_customer_id varchar not null,
    metric_date date not null,
    product_usage_score number(10, 4),
    marketing_engagement_score number(10, 4),
    support_activity_score number(10, 4),
    login_count number(18, 0),
    active_days number(18, 0),
    active_users number(18, 0),
    feature_usage variant,
    campaign_count number(18, 0),
    ticket_count number(18, 0),
    satisfaction_score number(10, 4),
    response_time_minutes number(18, 4),
    license_type varchar,
    renewal_status varchar,
    license_expiration_date date,
    contract_value number(18, 2),
    seat_count number(18, 0),
    load_batch_id varchar,
    updated_at timestamp_ntz not null default current_timestamp(),
    primary key (source_system, source_customer_id, metric_date) not enforced
)
cluster by (metric_date, source_system, source_customer_id)
comment = 'Daily standardized behavioral and operational customer metrics';

create table if not exists silver_partner_profile (
    source_system varchar not null,
    partner_id varchar not null,
    company_name varchar,
    company_name_normalized varchar,
    email varchar,
    phone varchar,
    partner_tier varchar,
    certifications array,
    certification_count number(18, 0),
    partner_region varchar,
    partner_status varchar,
    last_modified_timestamp timestamp_ntz,
    is_deleted boolean not null default false,
    data_quality_score number(5, 4),
    load_batch_id varchar,
    standardized_at timestamp_ntz not null default current_timestamp(),
    primary key (source_system, partner_id) not enforced
)
cluster by (partner_region, partner_tier, partner_id)
comment = 'Standardized partner profile records for partner analytics';

create table if not exists silver_customer_change_history (
    change_id varchar not null,
    source_system varchar not null,
    source_customer_id varchar not null,
    change_type varchar not null,
    changed_columns array,
    previous_record_hash varchar,
    current_record_hash varchar,
    effective_from timestamp_ntz not null,
    effective_to timestamp_ntz,
    is_current boolean not null default true,
    load_batch_id varchar,
    captured_at timestamp_ntz not null default current_timestamp(),
    primary key (change_id) not enforced
)
cluster by (source_system, source_customer_id, to_date(effective_from))
comment = 'CDC audit history for standardized customer records';

-- Optional performance enhancement for matching workloads:
-- enable Search Optimization Service on silver_customer(email, phone, website_domain)
-- when match-time point lookups become a bottleneck.
