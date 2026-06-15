-- Creates Customer 360 access roles and a least-privilege role hierarchy.
-- Run with SECURITYADMIN.

use role SECURITYADMIN;

create role if not exists CUSTOMER360_PLATFORM_ADMIN
    comment = 'Owns and administers Customer 360 Snowflake objects';

create role if not exists CUSTOMER360_SECURITY_ADMIN
    comment = 'Maintains masking policies, grants, and access reviews for Customer 360';

create role if not exists CUSTOMER360_LOADER
    comment = 'Loads source extracts into landing and bronze tables';

create role if not exists CUSTOMER360_TRANSFORMER
    comment = 'Runs standardization, matching, enrichment, and analytics transformations';

create role if not exists CUSTOMER360_ANALYST
    comment = 'Reads curated Customer 360 gold and analytics data';

create role if not exists CUSTOMER360_DOMO_ROLE
    comment = 'Read-only service role for Domo dataset refreshes';

create role if not exists CUSTOMER360_DEVELOPER
    comment = 'Non-production engineering role for Customer 360 development and testing';

grant role CUSTOMER360_PLATFORM_ADMIN to role SYSADMIN;
grant role CUSTOMER360_SECURITY_ADMIN to role SECURITYADMIN;

grant role CUSTOMER360_LOADER to role CUSTOMER360_DEVELOPER;
grant role CUSTOMER360_TRANSFORMER to role CUSTOMER360_DEVELOPER;
grant role CUSTOMER360_ANALYST to role CUSTOMER360_DEVELOPER;

grant role CUSTOMER360_LOADER to role CUSTOMER360_PLATFORM_ADMIN;
grant role CUSTOMER360_TRANSFORMER to role CUSTOMER360_PLATFORM_ADMIN;
grant role CUSTOMER360_ANALYST to role CUSTOMER360_PLATFORM_ADMIN;
grant role CUSTOMER360_DOMO_ROLE to role CUSTOMER360_PLATFORM_ADMIN;
grant role CUSTOMER360_SECURITY_ADMIN to role CUSTOMER360_PLATFORM_ADMIN;
