{% docs customer360_layering %}

The Customer 360 dbt graph follows enterprise medallion layering:

1. Bronze preserves source-system data with operational metadata.
2. Silver standardizes identity and behavioral signals.
3. Gold resolves identities and builds trusted customer records.
4. Analytics publishes dashboard-ready facts and snapshots.

Python services remain responsible for API extraction, Splink model execution, ML training, Great Expectations runtime validation, and Domo publication. dbt provides transparent SQL lineage for warehouse transformations and dashboard marts.

{% enddocs %}
