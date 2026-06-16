# checkpoints

Checkpoint definitions that bundle validation suites into executable quality gates.

`customer360_data_quality_checkpoint.yml` runs the production Customer 360 suites
for Silver customer records, golden customer records, enrichment metrics, and
health scoring outputs.

## Engineering Notes

- Keep code and assets aligned with this folder's responsibility.
- Avoid secrets and production customer data.
- Add or update tests when behavior changes.
