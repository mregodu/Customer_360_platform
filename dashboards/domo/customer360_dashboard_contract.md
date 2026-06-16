# Domo Customer 360 Reporting Layer

This contract defines the Domo datasets, KPIs, layouts, drill paths, filters, and
implementation steps for the Customer 360 reporting experience.

## Dataset Design

| Domo Dataset | Snowflake Source | Grain | Primary Dashboard | Refresh |
| --- | --- | --- | --- | --- |
| `customer360_<env>_executive_customer_kpis_daily` | `CUSTOMER360_DB.ANALYTICS.executive_customer_kpis_daily` | One row per `metric_date` | Executive Dashboard | Daily after scoring |
| `customer360_<env>_executive_segment_health_daily` | `CUSTOMER360_DB.ANALYTICS.executive_segment_health_daily` | One row per `metric_date`, `segment_type`, `segment_value` | Executive Dashboard | Daily after scoring |
| `customer360_<env>_customer_success_account_daily` | `CUSTOMER360_DB.ANALYTICS.customer_success_account_daily` | One row per `golden_customer_id`, `metric_date` | Customer Success Dashboard | Daily after scoring |
| `customer360_<env>_customer_health_drilldown` | `CUSTOMER360_DB.ANALYTICS.customer_health_drilldown` | One row per `golden_customer_id`, `metric_date` | Customer Success Dashboard | Daily after scoring |
| `customer360_<env>_partner_performance_daily` | `CUSTOMER360_DB.ANALYTICS.partner_performance_daily` | One row per `partner_id`, `metric_date` | Partner Dashboard | Daily after scoring |
| `customer360_<env>_customer_health_scores` | `CUSTOMER360_DB.ANALYTICS.customer_health_scores` | One row per `golden_customer_id`, `score_date` | Shared health cards | Daily after scoring |
| `customer360_<env>_data_quality_dashboard_daily` | `CUSTOMER360_DB.ANALYTICS.data_quality_dashboard_daily` | One row per quality suite and table per day | Executive operations section | Daily after validation |

Dataset joins in Domo should use `golden_customer_id` for account-level drilldowns,
`metric_date` for trend alignment, and `partner_id` for partner cards. Keep summary
cards on pre-aggregated datasets whenever possible so Domo does not need to perform
expensive joins at render time.

## KPI Definitions

| KPI | Dataset | Definition |
| --- | --- | --- |
| Total Customers | `executive_customer_kpis_daily` | `total_customers` on the selected `metric_date` |
| New Customers | `executive_customer_kpis_daily` | Customers whose `first_seen_at` falls on `metric_date` |
| Active Customers | `executive_customer_kpis_daily` | Customers with active golden master records |
| High Engagement Customers | `executive_customer_kpis_daily` | Customers where `engagement_score >= 0.75` |
| At Risk Customers | `executive_customer_kpis_daily` | Customers classified as `At Risk` |
| Churn Risk Customers | `executive_customer_kpis_daily` | Customers classified as `Churn Risk` |
| Total Lifetime Value | `executive_customer_kpis_daily` | Sum of `lifetime_value` for scored customers |
| Average Renewal Probability | `executive_customer_kpis_daily` | Average daily `renewal_probability` |
| Duplicate Reduction Rate | `executive_customer_kpis_daily` | `1 - total_clusters / total_source_members` |
| Match Accuracy Estimate | `executive_customer_kpis_daily` | Average Splink cluster `confidence_score` |
| Data Quality Score | `executive_customer_kpis_daily` | Average Great Expectations quality score |
| Health Class | `customer_success_account_daily` | Latest prediction: `Healthy`, `At Risk`, or `Churn Risk` |
| Churn Risk Score | `customer_health_drilldown` | Model probability for the `Churn Risk` class |
| Product Adoption Score | `customer_success_account_daily` | Product usage, active users, active days, and feature adoption |
| Engagement Score | `customer_success_account_daily` | Product, marketing, and support engagement |
| Support Health Score | `customer_health_drilldown` | Support experience score, where higher is healthier |
| Renewal Probability | `customer_success_account_daily` | Renewal-likelihood score from enrichment and model features |
| Partner Certification Count | `partner_performance_daily` | Count of active partner certifications from Impartner |
| Average Customer Health Score | `partner_performance_daily` | `1 - churn_risk_score`, averaged over the latest customer score date |

Recommended Domo Beast Modes:

```text
Healthy Rate = `healthy_customers` / NULLIF(`customer_count`, 0)
At Risk Rate = `at_risk_customers` / NULLIF(`customer_count`, 0)
Churn Risk Rate = `churn_risk_customers` / NULLIF(`customer_count`, 0)
Renewal Risk = 1 - `renewal_probability`
Customer Health Score = 1 - `churn_risk_score`
```

## Executive Dashboard

Purpose: executive view of customer base growth, value, health, matching quality, and
data-quality readiness.

Layout:

| Section | Cards |
| --- | --- |
| KPI strip | Total Customers, New Customers, Active Customers, Total Lifetime Value, Churn Risk Customers |
| Health and value trends | Daily health mix trend, total lifetime value trend, average renewal probability trend |
| Segment analysis | Segment health heatmap by `segment_type` and `segment_value`, top churn-risk segments, lifetime value by segment |
| Operations confidence | Data Quality Score, Duplicate Reduction Rate, Match Accuracy Estimate, failed quality checks by table |

Filters:

- Date range: `metric_date`
- Segment type: `Industry`, `Customer Status`, `Primary Source`, `Country`, `Health Class`
- Segment value
- Health class
- Data quality freshness status

Drill-down flow:

1. KPI card opens the corresponding trend card filtered to the selected date range.
2. Trend point opens `executive_segment_health_daily` for segment contribution.
3. Segment row opens `customer_health_drilldown` filtered to the same date, health class, and segment.
4. Customer row opens the Customer Success account detail view.

## Customer Success Dashboard

Purpose: daily account workbench for health monitoring, renewal risk, adoption, and
support follow-up.

Layout:

| Section | Cards |
| --- | --- |
| Account health strip | Healthy, At Risk, Churn Risk, Average Renewal Probability, Open Renewals |
| Risk worklist | Account table sorted by `churn_risk_score`, renewal date, and support ticket count |
| Account detail | Company profile, health class, classification reason, primary source system, source-system coverage |
| Driver analysis | Adoption, engagement, support health, active users, support tickets, satisfaction |
| Renewal view | Renewal status, license expiration, renewal probability, lifetime value |

Filters:

- Date range: `metric_date`
- Health class
- Renewal status
- License expiration window
- Industry
- Customer status
- Owner team
- Primary source system

Drill-down flow:

1. Health-class card opens the risk worklist filtered to the selected class.
2. Account row opens `customer_health_drilldown` for the selected `golden_customer_id`.
3. Driver card filters account detail to the contributing metric family.
4. Renewal card opens customers with the same renewal status and expiration window.

## Partner Dashboard

Purpose: partner operations view of partner coverage, certifications, regional
performance, and customer influence readiness.

Layout:

| Section | Cards |
| --- | --- |
| Partner KPI strip | Active Partners, Certified Partners, Average Certification Count, Influenced Customers, Influenced Lifetime Value |
| Regional performance | Partner count and certification coverage by `partner_region` |
| Tier performance | Partner tier distribution, average customer health by tier |
| Partner leaderboard | Partners sorted by certification count, region, active customer count, and average customer health |
| Partner detail | Partner status, tier, region, certifications, linked customer-health summary |

Filters:

- Date range: `metric_date`
- Partner tier
- Partner region
- Partner status
- Certification count band
- Average customer health band

Drill-down flow:

1. Region or tier card opens the partner leaderboard filtered to the selected value.
2. Partner row opens partner detail.
3. Partner detail links to Customer Success accounts once partner-to-customer attribution is available.

## Security and Access

- Use `CUSTOMER360_DOMO_ROLE` for Snowflake reads and `WH_CUSTOMER360_REPORTING`
  for refresh workloads.
- Apply Domo PDP by audience:
  - Executives: all executive and data-quality datasets.
  - Customer Success: account datasets filtered by `owner_team` or assigned segment.
  - Partner Operations: partner datasets filtered by `partner_region` or `partner_tier`.
- Treat `email`, `phone`, and address-level data as restricted fields. Hide them from
  executive cards and expose them only on role-restricted Customer Success drill pages.
- Keep API credentials in the validated platform configuration. Do not place Domo
  client secrets or dataset IDs in dashboard documentation.

## Implementation Guide

1. Run `sql/analytics/001_customer_health_scores.sql` to create Analytics tables.
2. Run scoring and data-quality jobs so `customer_health_scores` and
   `data_quality_dashboard_daily` are populated.
3. Run `sql/analytics/008_build_domo_reporting_layer.sql` to refresh the Domo
   reporting snapshots and drilldown datasets.
4. Create or map Domo datasets for each dataset listed above.
5. Set dataset ID environment variables expected by `DomoPublisher`, for example
   `DOMO_DATASET_ID_CUSTOMER360_DEV_EXECUTIVE_CUSTOMER_KPIS_DAILY`.
6. Enable `dashboard_refresh_dag`; it builds the data-quality dashboard, builds the
   Domo reporting layer, and publishes every registered Domo dataset.
7. Build cards from the pre-aggregated datasets first, then add drill pages using
   `customer_health_drilldown` and `executive_segment_health_daily`.
8. Add alerts:
   - Data Quality Score below `0.95`
   - Churn Risk Customers increasing by more than `10%` day over day
   - Average Renewal Probability below `0.65`
   - Domo dataset refresh failure or zero published rows

## Performance Notes

- Dashboard tables are clustered by `metric_date` plus high-cardinality drill filters.
- Domo should import the Analytics tables on the scheduled refresh instead of using
  live joins for primary cards.
- Keep `customer_health_drilldown` at customer/day grain. Add separate detail datasets
  only when source-level event history is required.
- Review Snowflake query history after the first two production refreshes; add dynamic
  tables or materialized views only for cards that show repeated scan pressure.
