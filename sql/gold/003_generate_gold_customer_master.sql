-- Generates trusted golden customer records from customer clusters and Silver records.
-- Input tables:
--   CUSTOMER360_DB.GOLD.gold_customer_clusters
--   CUSTOMER360_DB.SILVER.silver_customer

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema GOLD;

merge into CUSTOMER360_DB.GOLD.gold_customer_master target
using (
    with cluster_base as (
        select
            cluster_id,
            golden_customer_id,
            source_members,
            source_customer_ids,
            source_systems,
            representative_source_system,
            representative_source_customer_id,
            confidence_score,
            load_batch_id
        from CUSTOMER360_DB.GOLD.gold_customer_clusters
    ),

    cluster_members as (
        select
            cluster_id,
            golden_customer_id,
            member.value:source_system::varchar as source_system,
            member.value:source_customer_id::varchar as source_customer_id
        from cluster_base,
            lateral flatten(input => coalesce(source_members, array_construct())) member
        where source_members is not null

        union all

        select
            cluster_id,
            golden_customer_id,
            source_systems[0]::varchar as source_system,
            source_id.value::varchar as source_customer_id
        from cluster_base,
            lateral flatten(input => coalesce(source_customer_ids, array_construct())) source_id
        where source_members is null
            and array_size(source_systems) = 1
    ),

    silver_members as (
        select
            members.cluster_id,
            members.golden_customer_id,
            silver.source_system,
            silver.source_customer_id,
            silver.source_record_id,
            silver.company_name,
            silver.email,
            silver.phone,
            silver.address_line_1,
            silver.address_line_2,
            silver.city,
            silver.state_region,
            silver.postal_code,
            silver.country,
            coalesce(
                nullif(trim(silver.address), ''),
                nullif(
                    regexp_replace(
                        trim(
                            concat_ws(
                                ' ',
                                silver.address_line_1,
                                silver.city,
                                silver.state_region,
                                silver.postal_code,
                                silver.country
                            )
                        ),
                        '\\s+',
                        ' '
                    ),
                    ''
                )
            ) as address,
            silver.website_domain,
            silver.industry,
            silver.customer_status,
            silver.created_date,
            silver.last_modified_timestamp,
            silver.source_priority,
            silver.completeness_score,
            silver.data_quality_score
        from cluster_members members
        inner join CUSTOMER360_DB.SILVER.silver_customer silver
            on silver.source_system = members.source_system
            and silver.source_customer_id = members.source_customer_id
        where coalesce(silver.is_deleted, false) = false
    ),

    member_rollup as (
        select
            cluster_id,
            golden_customer_id,
            min(coalesce(created_date, last_modified_timestamp)) as first_seen_at,
            max(coalesce(last_modified_timestamp, created_date)) as last_seen_at,
            round(avg(coalesce(data_quality_score, 0)), 4) as data_quality_score
        from silver_members
        group by cluster_id, golden_customer_id
    ),

    primary_source as (
        select
            cluster_id,
            golden_customer_id,
            source_system as primary_source_system,
            source_customer_id as primary_source_customer_id
        from (
            select
                members.cluster_id,
                members.golden_customer_id,
                members.source_system,
                members.source_customer_id,
                iff(
                    members.source_system = base.representative_source_system
                    and members.source_customer_id = base.representative_source_customer_id,
                    0,
                    1
                ) as representative_rank,
                members.source_priority,
                members.data_quality_score,
                members.completeness_score,
                members.last_modified_timestamp
            from cluster_base base
            inner join silver_members members
                on members.cluster_id = base.cluster_id
        )
        qualify row_number() over (
            partition by cluster_id
            order by
                representative_rank asc,
                coalesce(source_priority, 100) asc,
                coalesce(data_quality_score, 0) desc,
                coalesce(completeness_score, 0) desc,
                last_modified_timestamp desc nulls last,
                source_system asc,
                source_customer_id asc
        ) = 1
    ),

    company_winner as (
        select *
        from silver_members
        where nullif(trim(company_name), '') is not null
        qualify row_number() over (
            partition by cluster_id
            order by
                coalesce(source_priority, 100) asc,
                coalesce(data_quality_score, 0) desc,
                coalesce(completeness_score, 0) desc,
                last_modified_timestamp desc nulls last,
                length(company_name) desc,
                source_system asc,
                source_customer_id asc
        ) = 1
    ),

    email_winner as (
        select *
        from silver_members
        where regexp_like(email, '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$')
        qualify row_number() over (
            partition by cluster_id
            order by
                coalesce(source_priority, 100) asc,
                coalesce(data_quality_score, 0) desc,
                coalesce(completeness_score, 0) desc,
                last_modified_timestamp desc nulls last,
                source_system asc,
                source_customer_id asc
        ) = 1
    ),

    phone_winner as (
        select *
        from silver_members
        where length(regexp_replace(phone, '[^0-9]', '')) >= 7
        qualify row_number() over (
            partition by cluster_id
            order by
                coalesce(source_priority, 100) asc,
                coalesce(data_quality_score, 0) desc,
                coalesce(completeness_score, 0) desc,
                last_modified_timestamp desc nulls last,
                source_system asc,
                source_customer_id asc
        ) = 1
    ),

    address_winner as (
        select *
        from silver_members
        where address is not null
        qualify row_number() over (
            partition by cluster_id
            order by
                coalesce(source_priority, 100) asc,
                coalesce(data_quality_score, 0) desc,
                coalesce(completeness_score, 0) desc,
                last_modified_timestamp desc nulls last,
                length(address) desc,
                source_system asc,
                source_customer_id asc
        ) = 1
    ),

    website_winner as (
        select *
        from silver_members
        where nullif(trim(website_domain), '') is not null
        qualify row_number() over (
            partition by cluster_id
            order by
                coalesce(source_priority, 100) asc,
                coalesce(data_quality_score, 0) desc,
                coalesce(completeness_score, 0) desc,
                last_modified_timestamp desc nulls last,
                source_system asc,
                source_customer_id asc
        ) = 1
    ),

    industry_winner as (
        select *
        from silver_members
        where nullif(trim(industry), '') is not null
        qualify row_number() over (
            partition by cluster_id
            order by
                coalesce(source_priority, 100) asc,
                coalesce(data_quality_score, 0) desc,
                coalesce(completeness_score, 0) desc,
                last_modified_timestamp desc nulls last,
                source_system asc,
                source_customer_id asc
        ) = 1
    ),

    status_winner as (
        select *
        from silver_members
        where nullif(trim(customer_status), '') is not null
        qualify row_number() over (
            partition by cluster_id
            order by
                coalesce(source_priority, 100) asc,
                coalesce(data_quality_score, 0) desc,
                coalesce(completeness_score, 0) desc,
                last_modified_timestamp desc nulls last,
                source_system asc,
                source_customer_id asc
        ) = 1
    )

    select
        base.golden_customer_id,
        base.cluster_id,
        base.source_customer_ids,
        base.source_systems,
        company.company_name,
        email.email,
        regexp_replace(phone.phone, '[^0-9]', '') as phone,
        address.address_line_1,
        address.address_line_2,
        address.city,
        address.state_region,
        address.postal_code,
        address.country,
        address.address,
        website.website_domain,
        industry.industry,
        status.customer_status,
        primary_source.primary_source_system,
        primary_source.primary_source_customer_id,
        member_rollup.first_seen_at,
        member_rollup.last_seen_at,
        coalesce(base.confidence_score, 1.0) as confidence_score,
        round(
            (
                iff(company.company_name is not null, 1, 0)
                + iff(email.email is not null, 1, 0)
                + iff(phone.phone is not null, 1, 0)
                + iff(address.address is not null, 1, 0)
            ) / 4,
            4
        ) as completeness_score,
        coalesce(member_rollup.data_quality_score, 0) as data_quality_score,
        object_construct_keep_null(
            'company_name',
            object_construct_keep_null(
                'source_system',
                company.source_system,
                'source_customer_id',
                company.source_customer_id,
                'rule_name',
                'source_priority_quality_recency'
            ),
            'email',
            object_construct_keep_null(
                'source_system',
                email.source_system,
                'source_customer_id',
                email.source_customer_id,
                'rule_name',
                'source_priority_quality_recency'
            ),
            'phone',
            object_construct_keep_null(
                'source_system',
                phone.source_system,
                'source_customer_id',
                phone.source_customer_id,
                'rule_name',
                'source_priority_quality_recency'
            ),
            'address',
            object_construct_keep_null(
                'source_system',
                address.source_system,
                'source_customer_id',
                address.source_customer_id,
                'rule_name',
                'source_priority_quality_recency'
            )
        ) as survivorship_rules,
        'v1' as golden_record_version,
        true as is_active,
        current_timestamp() as created_at,
        current_timestamp() as updated_at,
        base.load_batch_id
    from cluster_base base
    inner join member_rollup
        on member_rollup.cluster_id = base.cluster_id
    left join company_winner company
        on company.cluster_id = base.cluster_id
    left join email_winner email
        on email.cluster_id = base.cluster_id
    left join phone_winner phone
        on phone.cluster_id = base.cluster_id
    left join address_winner address
        on address.cluster_id = base.cluster_id
    left join website_winner website
        on website.cluster_id = base.cluster_id
    left join industry_winner industry
        on industry.cluster_id = base.cluster_id
    left join status_winner status
        on status.cluster_id = base.cluster_id
    left join primary_source
        on primary_source.cluster_id = base.cluster_id
) source
on target.golden_customer_id = source.golden_customer_id
when matched then update set
    cluster_id = source.cluster_id,
    source_customer_ids = source.source_customer_ids,
    source_systems = source.source_systems,
    company_name = source.company_name,
    email = source.email,
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
    primary_source_system = source.primary_source_system,
    primary_source_customer_id = source.primary_source_customer_id,
    first_seen_at = source.first_seen_at,
    last_seen_at = source.last_seen_at,
    confidence_score = source.confidence_score,
    completeness_score = source.completeness_score,
    data_quality_score = source.data_quality_score,
    survivorship_rules = source.survivorship_rules,
    golden_record_version = source.golden_record_version,
    is_active = source.is_active,
    updated_at = current_timestamp(),
    load_batch_id = source.load_batch_id
when not matched then insert (
    golden_customer_id,
    cluster_id,
    source_customer_ids,
    source_systems,
    company_name,
    email,
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
    primary_source_system,
    primary_source_customer_id,
    first_seen_at,
    last_seen_at,
    confidence_score,
    completeness_score,
    data_quality_score,
    survivorship_rules,
    golden_record_version,
    is_active,
    created_at,
    updated_at,
    load_batch_id
) values (
    source.golden_customer_id,
    source.cluster_id,
    source.source_customer_ids,
    source.source_systems,
    source.company_name,
    source.email,
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
    source.primary_source_system,
    source.primary_source_customer_id,
    source.first_seen_at,
    source.last_seen_at,
    source.confidence_score,
    source.completeness_score,
    source.data_quality_score,
    source.survivorship_rules,
    source.golden_record_version,
    source.is_active,
    source.created_at,
    source.updated_at,
    source.load_batch_id
);
