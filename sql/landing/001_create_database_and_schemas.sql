-- Creates the Snowflake database and managed schemas used by the Customer 360 platform.
-- Run with SYSADMIN or a role with CREATE DATABASE privileges.

use role SYSADMIN;

create database if not exists CUSTOMER360_DB
    data_retention_time_in_days = 1
    comment = 'Enterprise Customer 360 data enrichment platform';

alter database CUSTOMER360_DB set
    data_retention_time_in_days = 1
    comment = 'Enterprise Customer 360 data enrichment platform';

create schema if not exists CUSTOMER360_DB.LANDING
    with managed access
    data_retention_time_in_days = 3
    comment = 'Raw file landing, stages, file formats, manifests, and CDC watermarks';

create schema if not exists CUSTOMER360_DB.BRONZE
    with managed access
    data_retention_time_in_days = 7
    comment = 'Source-shaped raw ingested tables with audit metadata';

create schema if not exists CUSTOMER360_DB.SILVER
    with managed access
    data_retention_time_in_days = 14
    comment = 'Cleaned, standardized, and conformed customer records';

create schema if not exists CUSTOMER360_DB.GOLD
    with managed access
    data_retention_time_in_days = 30
    comment = 'Golden customer master, identity map, and entity-resolution outputs';

create schema if not exists CUSTOMER360_DB.ANALYTICS
    with managed access
    data_retention_time_in_days = 30
    comment = 'Domo-ready reporting, scoring, audit, and data-quality tables';

alter schema CUSTOMER360_DB.LANDING set data_retention_time_in_days = 3;
alter schema CUSTOMER360_DB.BRONZE set data_retention_time_in_days = 7;
alter schema CUSTOMER360_DB.SILVER set data_retention_time_in_days = 14;
alter schema CUSTOMER360_DB.GOLD set data_retention_time_in_days = 30;
alter schema CUSTOMER360_DB.ANALYTICS set data_retention_time_in_days = 30;
