{{ config(
    unique_key='cluster_id',
    cluster_by=['golden_customer_id', 'cluster_id']
) }}

select
    cluster_id,
    golden_customer_id,
    cluster_size,
    source_members,
    source_customer_ids,
    source_systems,
    representative_source_system,
    representative_source_customer_id,
    max_match_probability,
    avg_match_probability,
    confidence_score,
    cluster_rules,
    model_version,
    coalesce(created_at, current_timestamp()) as created_at,
    coalesce(updated_at, current_timestamp()) as updated_at,
    load_batch_id
from {{ source('gold_stage', 'stage_gold_customer_clusters') }}
where cluster_id is not null
qualify row_number() over (
    partition by cluster_id
    order by coalesce(updated_at, created_at, current_timestamp()) desc
) = 1
