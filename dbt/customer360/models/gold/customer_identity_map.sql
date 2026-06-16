{{ config(
    unique_key=['golden_customer_id', 'source_system', 'source_customer_id'],
    cluster_by=['source_system', 'source_customer_id', 'golden_customer_id']
) }}

with cluster_members as (
    select
        clusters.cluster_id,
        clusters.golden_customer_id,
        member.value:source_system::varchar as source_system,
        member.value:source_customer_id::varchar as source_customer_id,
        clusters.representative_source_system,
        clusters.representative_source_customer_id,
        clusters.confidence_score,
        clusters.created_at,
        clusters.load_batch_id
    from {{ ref('gold_customer_clusters') }} clusters,
        lateral flatten(input => coalesce(clusters.source_members, array_construct())) member
    where clusters.source_members is not null

    union all

    select
        clusters.cluster_id,
        clusters.golden_customer_id,
        clusters.source_systems[0]::varchar as source_system,
        source_id.value::varchar as source_customer_id,
        clusters.representative_source_system,
        clusters.representative_source_customer_id,
        clusters.confidence_score,
        clusters.created_at,
        clusters.load_batch_id
    from {{ ref('gold_customer_clusters') }} clusters,
        lateral flatten(input => coalesce(clusters.source_customer_ids, array_construct())) source_id
    where clusters.source_members is null
      and array_size(clusters.source_systems) = 1
)

select
    members.golden_customer_id,
    members.cluster_id,
    members.source_system,
    members.source_customer_id,
    silver.source_record_id,
    members.confidence_score as match_probability,
    members.source_system = members.representative_source_system
        and members.source_customer_id = members.representative_source_customer_id
        as is_primary_source,
    coalesce(members.created_at, current_timestamp()) as active_from,
    null as active_to,
    true as is_current,
    members.load_batch_id
from cluster_members members
left join {{ ref('silver_customer') }} silver
    on silver.source_system = members.source_system
    and silver.source_customer_id = members.source_customer_id
where members.source_system is not null
  and members.source_customer_id is not null
qualify row_number() over (
    partition by members.golden_customer_id, members.source_system, members.source_customer_id
    order by coalesce(members.created_at, current_timestamp()) desc
) = 1
