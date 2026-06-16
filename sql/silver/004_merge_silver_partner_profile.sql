-- Merges standardized partner profiles from Impartner bronze records.

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema SILVER;

set since_watermark = '1900-01-01 00:00:00';

merge into CUSTOMER360_DB.SILVER.silver_partner_profile target
using (
    with standardized as (
        select
            'IMPARTNER' as source_system,
            coalesce(partner_id, source_record_id) as partner_id,
            nullif(regexp_replace(upper(trim(company_name)), '\\s+', ' '), '') as company_name,
            nullif(
                regexp_replace(
                    regexp_replace(upper(trim(company_name)), '\\b(CORP|CORPORATION|INC|LLC|LTD|CO|COMPANY)\\b', ''),
                    '\\s+',
                    ' '
                ),
                ''
            ) as company_name_normalized,
            nullif(lower(trim(email)), '') as email,
            nullif(regexp_replace(phone, '[^0-9]', ''), '') as phone,
            nullif(regexp_replace(upper(trim(partner_tier)), '\\s+', ' '), '') as partner_tier,
            certifications,
            coalesce(array_size(certifications), 0) as certification_count,
            nullif(regexp_replace(upper(trim(partner_region)), '\\s+', ' '), '') as partner_region,
            nullif(regexp_replace(upper(trim(partner_status)), '\\s+', ' '), '') as partner_status,
            coalesce(last_modified_timestamp, load_timestamp) as last_modified_timestamp,
            coalesce(is_deleted, false) as is_deleted,
            load_batch_id
        from CUSTOMER360_DB.BRONZE.impartner_partner_bronze
        where coalesce(last_modified_timestamp, load_timestamp) > to_timestamp_ntz($since_watermark)
    )
    select
        *,
        greatest(
            0,
            round(
                (
                    iff(company_name is not null, 1, 0) +
                    iff(email is not null, 1, 0) +
                    iff(phone is not null, 1, 0) +
                    iff(partner_tier is not null, 1, 0) +
                    iff(partner_region is not null, 1, 0)
                ) / 5,
                4
            ) -
            iff(email is not null and not regexp_like(email, '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$'), 0.25, 0) -
            iff(phone is not null and length(phone) not between 7 and 15, 0.10, 0)
        ) as data_quality_score,
        current_timestamp() as standardized_at
    from standardized
    where partner_id is not null
) source
on target.source_system = source.source_system
   and target.partner_id = source.partner_id
when matched then update set
    company_name = source.company_name,
    company_name_normalized = source.company_name_normalized,
    email = source.email,
    phone = source.phone,
    partner_tier = source.partner_tier,
    certifications = source.certifications,
    certification_count = source.certification_count,
    partner_region = source.partner_region,
    partner_status = source.partner_status,
    last_modified_timestamp = source.last_modified_timestamp,
    is_deleted = source.is_deleted,
    data_quality_score = source.data_quality_score,
    load_batch_id = source.load_batch_id,
    standardized_at = source.standardized_at
when not matched then insert (
    source_system,
    partner_id,
    company_name,
    company_name_normalized,
    email,
    phone,
    partner_tier,
    certifications,
    certification_count,
    partner_region,
    partner_status,
    last_modified_timestamp,
    is_deleted,
    data_quality_score,
    load_batch_id,
    standardized_at
) values (
    source.source_system,
    source.partner_id,
    source.company_name,
    source.company_name_normalized,
    source.email,
    source.phone,
    source.partner_tier,
    source.certifications,
    source.certification_count,
    source.partner_region,
    source.partner_status,
    source.last_modified_timestamp,
    source.is_deleted,
    source.data_quality_score,
    source.load_batch_id,
    source.standardized_at
);
