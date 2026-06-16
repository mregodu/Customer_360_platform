# enrichment

Customer enrichment turns clustered Silver activity metrics into daily Gold
metrics for Customer 360 analytics.

- `scoring.py`: explainable formulas for customer lifetime value, product
  adoption, engagement, support health, and renewal probability.
- `pipeline.py`: joins cluster membership to Silver metric rows, aggregates
  customer/date signals, and emits `GOLD.customer_enrichment_metrics` rows.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
