-- Analytics table supports Domo customer health and renewal reporting.
create table if not exists CUSTOMER360_DB.ANALYTICS.customer_health_scores (
    golden_customer_id varchar,
    lifetime_value number(18,2),
    engagement_score float,
    adoption_score float,
    renewal_probability float,
    health_class varchar,
    scored_at timestamp_ntz default current_timestamp()
);
