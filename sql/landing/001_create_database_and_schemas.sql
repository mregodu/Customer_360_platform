-- Creates the Snowflake database and schemas used by the Customer 360 platform.
create database if not exists CUSTOMER360_DB;

create schema if not exists CUSTOMER360_DB.LANDING;
create schema if not exists CUSTOMER360_DB.BRONZE;
create schema if not exists CUSTOMER360_DB.SILVER;
create schema if not exists CUSTOMER360_DB.GOLD;
create schema if not exists CUSTOMER360_DB.ANALYTICS;
