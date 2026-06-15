-- Gold table stores trusted golden customer records after entity resolution.
create table if not exists CUSTOMER360_DB.GOLD.gold_customer_master (
    golden_customer_id varchar primary key,
    source_customer_ids array,
    company_name varchar,
    email varchar,
    phone varchar,
    address varchar,
    confidence_score float,
    created_at timestamp_ntz default current_timestamp()
);
