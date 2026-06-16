{{ config(
    unique_key=['source_system', 'partner_id'],
    cluster_by=['partner_region', 'partner_tier', 'partner_id']
) }}

with standardized as (
    select
        'IMPARTNER' as source_system,
        coalesce(partner_id, source_record_id) as partner_id,
        {{ customer360_clean_text('company_name') }} as company_name,
        {{ customer360_standardize_company('company_name') }} as company_name_normalized,
        {{ customer360_clean_email('email') }} as email,
        {{ customer360_clean_phone('phone') }} as phone,
        {{ customer360_clean_text('partner_tier') }} as partner_tier,
        certifications,
        coalesce(array_size(certifications), 0) as certification_count,
        {{ customer360_clean_text('partner_region') }} as partner_region,
        {{ customer360_clean_text('partner_status') }} as partner_status,
        coalesce(last_modified_timestamp, load_timestamp) as last_modified_timestamp,
        coalesce(is_deleted, false) as is_deleted,
        load_batch_id
    from {{ ref('impartner_partner_bronze') }}
    where coalesce(partner_id, source_record_id) is not null
    {{ customer360_incremental_watermark('coalesce(last_modified_timestamp, load_timestamp)') }}
)

select
    *,
    greatest(
        0,
        round(
            (
                iff(company_name is not null, 1, 0)
                + iff(email is not null, 1, 0)
                + iff(phone is not null, 1, 0)
                + iff(partner_tier is not null, 1, 0)
                + iff(partner_region is not null, 1, 0)
            ) / 5,
            4
        )
        - iff(email is not null and not regexp_like(email, '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$'), 0.25, 0)
        - iff(phone is not null and length(phone) not between 7 and 15, 0.10, 0)
    ) as data_quality_score,
    current_timestamp() as standardized_at
from standardized
qualify row_number() over (
    partition by source_system, partner_id
    order by last_modified_timestamp desc nulls last, load_batch_id desc
) = 1
