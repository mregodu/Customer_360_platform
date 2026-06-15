# security

Snowflake role, grant, and masking-policy scripts for the Customer 360 warehouse.

Recommended order:

1. Run `001_create_roles.sql` with `SECURITYADMIN`.
2. Run database, schema, warehouse, and table DDLs.
3. Run `002_grant_privileges.sql` with `SECURITYADMIN`.
4. Run `003_masking_policies.sql` with `CUSTOMER360_PLATFORM_ADMIN` or an equivalent owner role.
