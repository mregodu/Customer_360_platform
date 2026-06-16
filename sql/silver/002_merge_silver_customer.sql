-- Merges standardized customer identity records from all customer-like bronze sources.
-- Override the default watermark before running when needed:
-- set since_watermark = '2026-01-01 00:00:00';

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema SILVER;

set since_watermark = '1900-01-01 00:00:00';

merge into CUSTOMER360_DB.SILVER.silver_customer target
using (
    with source_records as (
        select
            'SALESFORCE' as source_system,
            coalesce(customer_id, source_record_id) as source_customer_id,
            source_record_id,
            company_name,
            email,
            phone,
            billing_street as address_line_1,
            null as address_line_2,
            billing_city as city,
            billing_state as state_region,
            billing_postal_code as postal_code,
            billing_country as country,
            website,
            industry,
            null as customer_status,
            created_date,
            coalesce(last_modified_timestamp, load_timestamp) as last_modified_timestamp,
            coalesce(is_deleted, false) as is_deleted,
            10 as source_priority,
            load_batch_id
        from CUSTOMER360_DB.BRONZE.salesforce_customer_bronze
        where coalesce(last_modified_timestamp, load_timestamp) > to_timestamp_ntz($since_watermark)

        union all

        select
            'MARKETO',
            coalesce(lead_id, email, source_record_id),
            source_record_id,
            company_name,
            email,
            phone,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            lead_status,
            created_date,
            coalesce(last_modified_timestamp, load_timestamp),
            coalesce(is_deleted, false),
            50,
            load_batch_id
        from CUSTOMER360_DB.BRONZE.marketo_lead_bronze
        where coalesce(last_modified_timestamp, load_timestamp) > to_timestamp_ntz($since_watermark)

        union all

        select
            'ZENDESK',
            coalesce(customer_id, support_account_id, email, source_record_id),
            source_record_id,
            company_name,
            email,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            ticket_status,
            null,
            coalesce(last_modified_timestamp, load_timestamp),
            coalesce(is_deleted, false),
            40,
            load_batch_id
        from CUSTOMER360_DB.BRONZE.zendesk_support_bronze
        where coalesce(last_modified_timestamp, load_timestamp) > to_timestamp_ntz($since_watermark)

        union all

        select
            'PRODUCT_USAGE',
            coalesce(customer_id, source_record_id),
            source_record_id,
            company_name,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            coalesce(last_modified_timestamp, load_timestamp),
            coalesce(is_deleted, false),
            30,
            load_batch_id
        from CUSTOMER360_DB.BRONZE.product_usage_bronze
        where coalesce(last_modified_timestamp, load_timestamp) > to_timestamp_ntz($since_watermark)

        union all

        select
            'LICENSING',
            coalesce(customer_id, license_id, source_record_id),
            source_record_id,
            company_name,
            email,
            phone,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            renewal_status,
            null,
            coalesce(last_modified_timestamp, load_timestamp),
            coalesce(is_deleted, false),
            20,
            load_batch_id
        from CUSTOMER360_DB.BRONZE.licensing_customer_bronze
        where coalesce(last_modified_timestamp, load_timestamp) > to_timestamp_ntz($since_watermark)
    ),
    standardized as (
        select
            source_system,
            source_customer_id,
            source_record_id,
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
            split_part(nullif(lower(trim(email)), ''), '@', 2) as email_domain,
            nullif(regexp_replace(phone, '[^0-9]', ''), '') as phone,
            nullif(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(upper(trim(address_line_1)), '\\bSTREET\\b', 'ST'),
                        '\\bROAD\\b',
                        'RD'
                    ),
                    '\\bAVENUE\\b',
                    'AVE'
                ),
                ''
            ) as address_line_1,
            nullif(upper(trim(address_line_2)), '') as address_line_2,
            nullif(regexp_replace(upper(trim(city)), '\\s+', ' '), '') as city,
            nullif(upper(trim(state_region)), '') as state_region,
            nullif(regexp_replace(upper(trim(postal_code)), '[^A-Z0-9]', ''), '') as postal_code,
            case
                when upper(trim(country)) in ('US', 'USA', 'UNITED STATES', 'UNITED STATES OF AMERICA') then 'US'
                when upper(trim(country)) in ('UK', 'UNITED KINGDOM', 'GREAT BRITAIN') then 'GB'
                else nullif(upper(trim(country)), '')
            end as country,
            nullif(regexp_replace(lower(regexp_replace(trim(website), '^https?://(www\\.)?', '')), '/.*$', ''), '') as website_domain,
            nullif(regexp_replace(upper(trim(industry)), '\\s+', ' '), '') as industry,
            nullif(regexp_replace(upper(trim(customer_status)), '\\s+', ' '), '') as customer_status,
            created_date,
            last_modified_timestamp,
            is_deleted,
            source_priority,
            load_batch_id
        from source_records
        where source_customer_id is not null
    ),
    scored as (
        select
            *,
            nullif(
                regexp_replace(
                    concat_ws(' ', address_line_1, city, state_region, postal_code, country),
                    '\\s+',
                    ' '
                ),
                ''
            ) as address,
            round(
                (
                    iff(company_name is not null, 1, 0) +
                    iff(email is not null, 1, 0) +
                    iff(phone is not null, 1, 0) +
                    iff(address_line_1 is not null, 1, 0) +
                    iff(industry is not null, 1, 0) +
                    iff(last_modified_timestamp is not null, 1, 0)
                ) / 6,
                4
            ) as completeness_score
        from standardized
    )
    select
        source_system,
        source_customer_id,
        source_record_id,
        company_name,
        company_name_normalized,
        email,
        email_domain,
        phone,
        address_line_1,
        address_line_2,
        city,
        state_region,
        postal_code,
        country,
        address,
        website_domain,
        industry,
        customer_status,
        created_date,
        last_modified_timestamp,
        is_deleted,
        source_priority,
        completeness_score,
        greatest(
            0,
            completeness_score -
            iff(email is not null and not regexp_like(email, '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$'), 0.25, 0) -
            iff(phone is not null and length(phone) not between 7 and 15, 0.10, 0)
        ) as data_quality_score,
        'v1' as standardization_version,
        sha2(to_json(object_construct_keep_null(
            'source_system', source_system,
            'source_customer_id', source_customer_id,
            'company_name', company_name,
            'email', email,
            'phone', phone,
            'address', address,
            'last_modified_timestamp', last_modified_timestamp
        )), 256) as record_hash,
        load_batch_id,
        current_timestamp() as standardized_at
    from scored
) source
on target.source_system = source.source_system
   and target.source_customer_id = source.source_customer_id
when matched and coalesce(target.record_hash, '') <> source.record_hash then update set
    source_record_id = source.source_record_id,
    company_name = source.company_name,
    company_name_normalized = source.company_name_normalized,
    email = source.email,
    email_domain = source.email_domain,
    phone = source.phone,
    address_line_1 = source.address_line_1,
    address_line_2 = source.address_line_2,
    city = source.city,
    state_region = source.state_region,
    postal_code = source.postal_code,
    country = source.country,
    address = source.address,
    website_domain = source.website_domain,
    industry = source.industry,
    customer_status = source.customer_status,
    created_date = source.created_date,
    last_modified_timestamp = source.last_modified_timestamp,
    is_deleted = source.is_deleted,
    source_priority = source.source_priority,
    completeness_score = source.completeness_score,
    data_quality_score = source.data_quality_score,
    standardization_version = source.standardization_version,
    record_hash = source.record_hash,
    load_batch_id = source.load_batch_id,
    standardized_at = source.standardized_at
when not matched then insert (
    source_system,
    source_customer_id,
    source_record_id,
    company_name,
    company_name_normalized,
    email,
    email_domain,
    phone,
    address_line_1,
    address_line_2,
    city,
    state_region,
    postal_code,
    country,
    address,
    website_domain,
    industry,
    customer_status,
    created_date,
    last_modified_timestamp,
    is_deleted,
    source_priority,
    completeness_score,
    data_quality_score,
    standardization_version,
    record_hash,
    load_batch_id,
    standardized_at
) values (
    source.source_system,
    source.source_customer_id,
    source.source_record_id,
    source.company_name,
    source.company_name_normalized,
    source.email,
    source.email_domain,
    source.phone,
    source.address_line_1,
    source.address_line_2,
    source.city,
    source.state_region,
    source.postal_code,
    source.country,
    source.address,
    source.website_domain,
    source.industry,
    source.customer_status,
    source.created_date,
    source.last_modified_timestamp,
    source.is_deleted,
    source.source_priority,
    source.completeness_score,
    source.data_quality_score,
    source.standardization_version,
    source.record_hash,
    source.load_batch_id,
    source.standardized_at
);
