-- Creates and applies masking policies for sensitive Customer 360 attributes.
-- Run after table DDLs exist with CUSTOMER360_PLATFORM_ADMIN or an equivalent owner role.

use role CUSTOMER360_PLATFORM_ADMIN;
use database CUSTOMER360_DB;

create masking policy if not exists GOLD.mask_customer_email
    as (val string) returns string ->
        case
            when val is null then null
            when current_role() in (
                'CUSTOMER360_PLATFORM_ADMIN',
                'CUSTOMER360_SECURITY_ADMIN',
                'CUSTOMER360_TRANSFORMER'
            ) then val
            when position('@' in val) > 1 then
                left(val, 1) || '***' || substr(val, position('@' in val))
            else '***'
        end;

create masking policy if not exists GOLD.mask_customer_phone
    as (val string) returns string ->
        case
            when val is null then null
            when current_role() in (
                'CUSTOMER360_PLATFORM_ADMIN',
                'CUSTOMER360_SECURITY_ADMIN',
                'CUSTOMER360_TRANSFORMER'
            ) then val
            when length(regexp_replace(val, '[^0-9]', '')) >= 4 then
                '***-***-' || right(regexp_replace(val, '[^0-9]', ''), 4)
            else '***'
        end;

create masking policy if not exists GOLD.mask_customer_address
    as (val string) returns string ->
        case
            when val is null then null
            when current_role() in (
                'CUSTOMER360_PLATFORM_ADMIN',
                'CUSTOMER360_SECURITY_ADMIN',
                'CUSTOMER360_TRANSFORMER'
            ) then val
            else 'REDACTED'
        end;

alter table if exists SILVER.silver_customer modify column email
    set masking policy GOLD.mask_customer_email force;
alter table if exists SILVER.silver_customer modify column phone
    set masking policy GOLD.mask_customer_phone force;
alter table if exists SILVER.silver_customer modify column address_line_1
    set masking policy GOLD.mask_customer_address force;
alter table if exists SILVER.silver_customer modify column address_line_2
    set masking policy GOLD.mask_customer_address force;

alter table if exists GOLD.gold_customer_master modify column email
    set masking policy GOLD.mask_customer_email force;
alter table if exists GOLD.gold_customer_master modify column phone
    set masking policy GOLD.mask_customer_phone force;
alter table if exists GOLD.gold_customer_master modify column address_line_1
    set masking policy GOLD.mask_customer_address force;
alter table if exists GOLD.gold_customer_master modify column address_line_2
    set masking policy GOLD.mask_customer_address force;
alter table if exists GOLD.gold_customer_master modify column address
    set masking policy GOLD.mask_customer_address force;

alter table if exists ANALYTICS.customer_health_scores modify column email
    set masking policy GOLD.mask_customer_email force;
