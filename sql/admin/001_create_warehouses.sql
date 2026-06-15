-- Creates workload-isolated Snowflake warehouses for the Customer 360 platform.
-- Run with SYSADMIN or a role with CREATE WAREHOUSE privileges.

use role SYSADMIN;

create warehouse if not exists WH_CUSTOMER360_INGEST
    warehouse_size = 'SMALL'
    warehouse_type = 'STANDARD'
    auto_suspend = 60
    auto_resume = true
    initially_suspended = true
    statement_timeout_in_seconds = 1800
    comment = 'Customer 360 ingestion and landing-to-bronze workloads';

alter warehouse WH_CUSTOMER360_INGEST set
    warehouse_size = 'SMALL'
    auto_suspend = 60
    auto_resume = true
    statement_timeout_in_seconds = 1800;

create warehouse if not exists WH_CUSTOMER360_TRANSFORM
    warehouse_size = 'MEDIUM'
    warehouse_type = 'STANDARD'
    auto_suspend = 120
    auto_resume = true
    initially_suspended = true
    statement_timeout_in_seconds = 3600
    comment = 'Customer 360 standardization, enrichment, and dbt transformations';

alter warehouse WH_CUSTOMER360_TRANSFORM set
    warehouse_size = 'MEDIUM'
    auto_suspend = 120
    auto_resume = true
    statement_timeout_in_seconds = 3600;

create warehouse if not exists WH_CUSTOMER360_MATCHING
    warehouse_size = 'LARGE'
    warehouse_type = 'STANDARD'
    auto_suspend = 300
    auto_resume = true
    initially_suspended = true
    statement_timeout_in_seconds = 7200
    comment = 'Customer 360 Splink entity-resolution and clustering workloads';

alter warehouse WH_CUSTOMER360_MATCHING set
    warehouse_size = 'LARGE'
    auto_suspend = 300
    auto_resume = true
    statement_timeout_in_seconds = 7200;

create warehouse if not exists WH_CUSTOMER360_REPORTING
    warehouse_size = 'SMALL'
    warehouse_type = 'STANDARD'
    auto_suspend = 60
    auto_resume = true
    initially_suspended = true
    statement_timeout_in_seconds = 900
    comment = 'Customer 360 Domo and analyst reporting workloads';

alter warehouse WH_CUSTOMER360_REPORTING set
    warehouse_size = 'SMALL'
    auto_suspend = 60
    auto_resume = true
    statement_timeout_in_seconds = 900;
