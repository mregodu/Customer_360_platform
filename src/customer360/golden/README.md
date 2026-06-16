# golden

Golden-record generation turns Splink customer clusters into trusted
`GOLD.gold_customer_master` rows.

- `survivorship.py`: deterministic survivorship rules for company name, email,
  phone, address, and supporting profile fields.
- `service.py`: application-level orchestration for generating and persisting
  golden customer records.

The Snowflake-native merge lives in `sql/gold/003_generate_gold_customer_master.sql`.
