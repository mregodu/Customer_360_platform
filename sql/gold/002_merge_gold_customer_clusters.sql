-- Merges Splink-generated customer clusters into GOLD.gold_customer_clusters.
-- Expected staging table: CUSTOMER360_DB.GOLD.stage_gold_customer_clusters

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema GOLD;

create table if not exists stage_gold_customer_clusters (
    cluster_id varchar not null,
    golden_customer_id varchar not null,
    cluster_size number(18, 0) not null,
    source_customer_ids array,
    source_systems array,
    representative_source_system varchar,
    representative_source_customer_id varchar,
    max_match_probability number(10, 8),
    avg_match_probability number(10, 8),
    confidence_score number(10, 8),
    cluster_rules array,
    model_version varchar not null,
    created_at timestamp_ntz,
    updated_at timestamp_ntz,
    load_batch_id varchar
);

merge into CUSTOMER360_DB.GOLD.gold_customer_clusters target
using CUSTOMER360_DB.GOLD.stage_gold_customer_clusters source
on target.cluster_id = source.cluster_id
when matched then update set
    golden_customer_id = source.golden_customer_id,
    cluster_size = source.cluster_size,
    source_customer_ids = source.source_customer_ids,
    source_systems = source.source_systems,
    representative_source_system = source.representative_source_system,
    representative_source_customer_id = source.representative_source_customer_id,
    max_match_probability = source.max_match_probability,
    avg_match_probability = source.avg_match_probability,
    confidence_score = source.confidence_score,
    cluster_rules = source.cluster_rules,
    model_version = source.model_version,
    updated_at = current_timestamp(),
    load_batch_id = source.load_batch_id
when not matched then insert (
    cluster_id,
    golden_customer_id,
    cluster_size,
    source_customer_ids,
    source_systems,
    representative_source_system,
    representative_source_customer_id,
    max_match_probability,
    avg_match_probability,
    confidence_score,
    cluster_rules,
    model_version,
    created_at,
    updated_at,
    load_batch_id
) values (
    source.cluster_id,
    source.golden_customer_id,
    source.cluster_size,
    source.source_customer_ids,
    source.source_systems,
    source.representative_source_system,
    source.representative_source_customer_id,
    source.max_match_probability,
    source.avg_match_probability,
    source.confidence_score,
    source.cluster_rules,
    source.model_version,
    coalesce(source.created_at, current_timestamp()),
    coalesce(source.updated_at, current_timestamp()),
    source.load_batch_id
);
