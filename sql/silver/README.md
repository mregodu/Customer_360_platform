# silver

Snowflake DDL for standardized silver-layer objects.

Silver tables contain standardized customer identities, daily conformed metrics, partner profiles,
and CDC history. Entity-resolution jobs should read from `SILVER.silver_customer`.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
