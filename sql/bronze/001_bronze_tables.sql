-- Bronze tables store source records exactly as received plus audit metadata.
create table if not exists CUSTOMER360_DB.BRONZE.salesforce_customer_bronze (
    customer_id varchar,
    company_name varchar,
    email varchar,
    phone varchar,
    industry varchar,
    created_date timestamp_ntz,
    load_timestamp timestamp_ntz,
    source_system varchar
);
