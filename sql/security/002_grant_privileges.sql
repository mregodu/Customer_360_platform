-- Grants database, schema, warehouse, and object privileges for Customer 360 roles.
-- Run after warehouses, database, schemas, and tables exist.
-- Run with SECURITYADMIN or an equivalent grant-management role.

use role SECURITYADMIN;

grant usage, monitor, operate on warehouse WH_CUSTOMER360_INGEST to role CUSTOMER360_LOADER;
grant usage, monitor on warehouse WH_CUSTOMER360_INGEST to role CUSTOMER360_PLATFORM_ADMIN;

grant usage, monitor, operate on warehouse WH_CUSTOMER360_TRANSFORM to role CUSTOMER360_TRANSFORMER;
grant usage, monitor on warehouse WH_CUSTOMER360_TRANSFORM to role CUSTOMER360_PLATFORM_ADMIN;

grant usage, monitor, operate on warehouse WH_CUSTOMER360_MATCHING to role CUSTOMER360_TRANSFORMER;
grant usage, monitor on warehouse WH_CUSTOMER360_MATCHING to role CUSTOMER360_PLATFORM_ADMIN;

grant usage, monitor, operate on warehouse WH_CUSTOMER360_REPORTING to role CUSTOMER360_ANALYST;
grant usage, monitor, operate on warehouse WH_CUSTOMER360_REPORTING to role CUSTOMER360_DOMO_ROLE;
grant usage, monitor on warehouse WH_CUSTOMER360_REPORTING to role CUSTOMER360_PLATFORM_ADMIN;

grant usage on database CUSTOMER360_DB to role CUSTOMER360_LOADER;
grant usage on database CUSTOMER360_DB to role CUSTOMER360_TRANSFORMER;
grant usage on database CUSTOMER360_DB to role CUSTOMER360_ANALYST;
grant usage on database CUSTOMER360_DB to role CUSTOMER360_DOMO_ROLE;
grant usage on database CUSTOMER360_DB to role CUSTOMER360_SECURITY_ADMIN;
grant all privileges on database CUSTOMER360_DB to role CUSTOMER360_PLATFORM_ADMIN;

grant usage on schema CUSTOMER360_DB.LANDING to role CUSTOMER360_LOADER;
grant usage on schema CUSTOMER360_DB.BRONZE to role CUSTOMER360_LOADER;
grant usage on schema CUSTOMER360_DB.BRONZE to role CUSTOMER360_TRANSFORMER;
grant usage on schema CUSTOMER360_DB.SILVER to role CUSTOMER360_TRANSFORMER;
grant usage on schema CUSTOMER360_DB.GOLD to role CUSTOMER360_TRANSFORMER;
grant usage on schema CUSTOMER360_DB.GOLD to role CUSTOMER360_ANALYST;
grant usage on schema CUSTOMER360_DB.ANALYTICS to role CUSTOMER360_TRANSFORMER;
grant usage on schema CUSTOMER360_DB.ANALYTICS to role CUSTOMER360_ANALYST;
grant usage on schema CUSTOMER360_DB.ANALYTICS to role CUSTOMER360_DOMO_ROLE;
grant usage on all schemas in database CUSTOMER360_DB to role CUSTOMER360_PLATFORM_ADMIN;
grant usage on future schemas in database CUSTOMER360_DB to role CUSTOMER360_PLATFORM_ADMIN;

grant create table, create stage, create file format on schema CUSTOMER360_DB.LANDING
    to role CUSTOMER360_LOADER;
grant create table on schema CUSTOMER360_DB.BRONZE to role CUSTOMER360_LOADER;
grant create table, create view on schema CUSTOMER360_DB.SILVER to role CUSTOMER360_TRANSFORMER;
grant create table, create view on schema CUSTOMER360_DB.GOLD to role CUSTOMER360_TRANSFORMER;
grant create table, create view on schema CUSTOMER360_DB.ANALYTICS to role CUSTOMER360_TRANSFORMER;
grant all privileges on all schemas in database CUSTOMER360_DB to role CUSTOMER360_PLATFORM_ADMIN;

grant select, insert, update, delete on all tables in schema CUSTOMER360_DB.LANDING
    to role CUSTOMER360_LOADER;
grant select, insert, update, delete on future tables in schema CUSTOMER360_DB.LANDING
    to role CUSTOMER360_LOADER;
grant usage on all stages in schema CUSTOMER360_DB.LANDING to role CUSTOMER360_LOADER;
grant usage on future stages in schema CUSTOMER360_DB.LANDING to role CUSTOMER360_LOADER;
grant usage on all file formats in schema CUSTOMER360_DB.LANDING to role CUSTOMER360_LOADER;
grant usage on future file formats in schema CUSTOMER360_DB.LANDING to role CUSTOMER360_LOADER;

grant select, insert, update, delete on all tables in schema CUSTOMER360_DB.BRONZE
    to role CUSTOMER360_LOADER;
grant select, insert, update, delete on future tables in schema CUSTOMER360_DB.BRONZE
    to role CUSTOMER360_LOADER;
grant select on all tables in schema CUSTOMER360_DB.BRONZE to role CUSTOMER360_TRANSFORMER;
grant select on future tables in schema CUSTOMER360_DB.BRONZE to role CUSTOMER360_TRANSFORMER;

grant select, insert, update, delete, truncate on all tables in schema CUSTOMER360_DB.SILVER
    to role CUSTOMER360_TRANSFORMER;
grant select, insert, update, delete, truncate on future tables in schema CUSTOMER360_DB.SILVER
    to role CUSTOMER360_TRANSFORMER;
grant select on all tables in schema CUSTOMER360_DB.SILVER to role CUSTOMER360_ANALYST;
grant select on future tables in schema CUSTOMER360_DB.SILVER to role CUSTOMER360_ANALYST;

grant select, insert, update, delete, truncate on all tables in schema CUSTOMER360_DB.GOLD
    to role CUSTOMER360_TRANSFORMER;
grant select, insert, update, delete, truncate on future tables in schema CUSTOMER360_DB.GOLD
    to role CUSTOMER360_TRANSFORMER;
grant select on all tables in schema CUSTOMER360_DB.GOLD to role CUSTOMER360_ANALYST;
grant select on future tables in schema CUSTOMER360_DB.GOLD to role CUSTOMER360_ANALYST;

grant select, insert, update, delete, truncate on all tables in schema CUSTOMER360_DB.ANALYTICS
    to role CUSTOMER360_TRANSFORMER;
grant select, insert, update, delete, truncate on future tables in schema CUSTOMER360_DB.ANALYTICS
    to role CUSTOMER360_TRANSFORMER;
grant select on all tables in schema CUSTOMER360_DB.ANALYTICS to role CUSTOMER360_ANALYST;
grant select on future tables in schema CUSTOMER360_DB.ANALYTICS to role CUSTOMER360_ANALYST;
grant select on all tables in schema CUSTOMER360_DB.ANALYTICS to role CUSTOMER360_DOMO_ROLE;
grant select on future tables in schema CUSTOMER360_DB.ANALYTICS to role CUSTOMER360_DOMO_ROLE;

grant all privileges on all tables in schema CUSTOMER360_DB.LANDING to role CUSTOMER360_PLATFORM_ADMIN;
grant select, insert, update, delete, truncate, references
    on future tables in schema CUSTOMER360_DB.LANDING to role CUSTOMER360_PLATFORM_ADMIN;
grant all privileges on all tables in schema CUSTOMER360_DB.BRONZE to role CUSTOMER360_PLATFORM_ADMIN;
grant select, insert, update, delete, truncate, references
    on future tables in schema CUSTOMER360_DB.BRONZE to role CUSTOMER360_PLATFORM_ADMIN;
grant all privileges on all tables in schema CUSTOMER360_DB.SILVER to role CUSTOMER360_PLATFORM_ADMIN;
grant select, insert, update, delete, truncate, references
    on future tables in schema CUSTOMER360_DB.SILVER to role CUSTOMER360_PLATFORM_ADMIN;
grant all privileges on all tables in schema CUSTOMER360_DB.GOLD to role CUSTOMER360_PLATFORM_ADMIN;
grant select, insert, update, delete, truncate, references
    on future tables in schema CUSTOMER360_DB.GOLD to role CUSTOMER360_PLATFORM_ADMIN;
grant all privileges on all tables in schema CUSTOMER360_DB.ANALYTICS to role CUSTOMER360_PLATFORM_ADMIN;
grant select, insert, update, delete, truncate, references
    on future tables in schema CUSTOMER360_DB.ANALYTICS to role CUSTOMER360_PLATFORM_ADMIN;

grant select on all tables in schema CUSTOMER360_DB.GOLD to role CUSTOMER360_SECURITY_ADMIN;
grant select on future tables in schema CUSTOMER360_DB.GOLD to role CUSTOMER360_SECURITY_ADMIN;
grant select on all tables in schema CUSTOMER360_DB.ANALYTICS to role CUSTOMER360_SECURITY_ADMIN;
grant select on future tables in schema CUSTOMER360_DB.ANALYTICS to role CUSTOMER360_SECURITY_ADMIN;
