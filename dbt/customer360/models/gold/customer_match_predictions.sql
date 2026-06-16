{{ config(
    unique_key='match_id',
    cluster_by=['to_date(predicted_at)', 'match_probability']
) }}

select
    match_id,
    left_source_system,
    left_source_customer_id,
    right_source_system,
    right_source_customer_id,
    match_probability,
    confidence_score,
    comparison_vector,
    blocking_rule,
    model_version,
    coalesce(predicted_at, current_timestamp()) as predicted_at,
    load_batch_id
from {{ source('gold_stage', 'stage_customer_match_predictions') }}
where match_id is not null
qualify row_number() over (
    partition by match_id
    order by coalesce(predicted_at, current_timestamp()) desc
) = 1
