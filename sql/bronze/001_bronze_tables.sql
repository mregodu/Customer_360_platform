-- Bronze tables store source records as received plus audit metadata.
-- Each table includes CDC, lineage, and reconciliation columns used by downstream merges.

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema BRONZE;

create table if not exists salesforce_customer_bronze (
    source_record_id varchar not null,
    customer_id varchar,
    company_name varchar,
    email varchar,
    phone varchar,
    industry varchar,
    billing_street varchar,
    billing_city varchar,
    billing_state varchar,
    billing_postal_code varchar,
    billing_country varchar,
    website varchar,
    annual_revenue number(18, 2),
    number_of_employees number(18, 0),
    created_date timestamp_ntz,
    last_modified_timestamp timestamp_ntz,
    is_deleted boolean default false,
    source_system varchar not null default 'SALESFORCE',
    source_object varchar not null default 'ACCOUNT',
    source_file_name varchar,
    source_file_row_number number(38, 0),
    load_batch_id varchar not null,
    load_timestamp timestamp_ntz not null default current_timestamp(),
    record_hash varchar,
    raw_payload variant,
    primary key (source_record_id, load_batch_id) not enforced
)
cluster by (source_system, to_date(load_timestamp), source_record_id)
comment = 'Raw Salesforce customer records with audit metadata';

create table if not exists marketo_lead_bronze (
    source_record_id varchar not null,
    lead_id varchar,
    email varchar,
    company_name varchar,
    phone varchar,
    campaign varchar,
    engagement_score number(10, 4),
    lead_status varchar,
    first_name varchar,
    last_name varchar,
    created_date timestamp_ntz,
    last_modified_timestamp timestamp_ntz,
    is_deleted boolean default false,
    source_system varchar not null default 'MARKETO',
    source_object varchar not null default 'LEAD',
    source_file_name varchar,
    source_file_row_number number(38, 0),
    load_batch_id varchar not null,
    load_timestamp timestamp_ntz not null default current_timestamp(),
    record_hash varchar,
    raw_payload variant,
    primary key (source_record_id, load_batch_id) not enforced
)
cluster by (source_system, to_date(load_timestamp), source_record_id)
comment = 'Raw Marketo lead and engagement records with audit metadata';

create table if not exists zendesk_support_bronze (
    source_record_id varchar not null,
    support_account_id varchar,
    ticket_id varchar,
    customer_id varchar,
    company_name varchar,
    email varchar,
    ticket_count number(18, 0),
    satisfaction_score number(10, 4),
    response_time_minutes number(18, 4),
    ticket_status varchar,
    ticket_priority varchar,
    last_ticket_created_at timestamp_ntz,
    last_modified_timestamp timestamp_ntz,
    is_deleted boolean default false,
    source_system varchar not null default 'ZENDESK',
    source_object varchar not null default 'SUPPORT_ACCOUNT',
    source_file_name varchar,
    source_file_row_number number(38, 0),
    load_batch_id varchar not null,
    load_timestamp timestamp_ntz not null default current_timestamp(),
    record_hash varchar,
    raw_payload variant,
    primary key (source_record_id, load_batch_id) not enforced
)
cluster by (source_system, to_date(load_timestamp), source_record_id)
comment = 'Raw Zendesk support activity and satisfaction records';

create table if not exists product_usage_bronze (
    source_record_id varchar not null,
    usage_event_id varchar,
    customer_id varchar,
    company_name varchar,
    user_id varchar,
    event_date date,
    login_count number(18, 0),
    active_days number(18, 0),
    active_users number(18, 0),
    feature_usage variant,
    product_area varchar,
    last_modified_timestamp timestamp_ntz,
    is_deleted boolean default false,
    source_system varchar not null default 'PRODUCT_USAGE',
    source_object varchar not null default 'USAGE_DAILY',
    source_file_name varchar,
    source_file_row_number number(38, 0),
    load_batch_id varchar not null,
    load_timestamp timestamp_ntz not null default current_timestamp(),
    record_hash varchar,
    raw_payload variant,
    primary key (source_record_id, load_batch_id) not enforced
)
cluster by (source_system, event_date, customer_id)
comment = 'Raw product usage metrics from application logs';

create table if not exists licensing_customer_bronze (
    source_record_id varchar not null,
    license_id varchar,
    customer_id varchar,
    company_name varchar,
    email varchar,
    phone varchar,
    license_type varchar,
    expiration_date date,
    renewal_status varchar,
    contract_value number(18, 2),
    seat_count number(18, 0),
    contract_start_date date,
    contract_end_date date,
    last_modified_timestamp timestamp_ntz,
    is_deleted boolean default false,
    source_system varchar not null default 'LICENSING',
    source_object varchar not null default 'LICENSE',
    source_file_name varchar,
    source_file_row_number number(38, 0),
    load_batch_id varchar not null,
    load_timestamp timestamp_ntz not null default current_timestamp(),
    record_hash varchar,
    raw_payload variant,
    primary key (source_record_id, load_batch_id) not enforced
)
cluster by (source_system, expiration_date, customer_id)
comment = 'Raw licensing, renewal, and contract records';

create table if not exists impartner_partner_bronze (
    source_record_id varchar not null,
    partner_id varchar,
    company_name varchar,
    email varchar,
    phone varchar,
    partner_tier varchar,
    certifications array,
    partner_region varchar,
    partner_status varchar,
    created_date timestamp_ntz,
    last_modified_timestamp timestamp_ntz,
    is_deleted boolean default false,
    source_system varchar not null default 'IMPARTNER',
    source_object varchar not null default 'PARTNER',
    source_file_name varchar,
    source_file_row_number number(38, 0),
    load_batch_id varchar not null,
    load_timestamp timestamp_ntz not null default current_timestamp(),
    record_hash varchar,
    raw_payload variant,
    primary key (source_record_id, load_batch_id) not enforced
)
cluster by (source_system, partner_region, partner_id)
comment = 'Raw Impartner partner profile and certification records';

-- Optional performance enhancement for large point-lookup workloads:
-- enable Search Optimization Service on source_record_id, customer_id, email, and phone
-- for high-volume bronze tables after validating edition support and cost controls.
