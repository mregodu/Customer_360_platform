# Customer 360 Data Enrichment Platform Context

Source document: `/Users/user/Downloads/Customer 360 Data Enrichment Platform.pdf`
Extracted and summarized for project reuse on 2026-06-14.

## Project Overview

Build an enterprise-grade Customer 360 Data Enrichment Platform that consolidates customer information from multiple business systems into a single trusted customer profile using Snowflake, Python, Splink, and Domo.

The platform supports:

- Customer Master Data Management (MDM)
- Entity resolution and record linkage
- Customer enrichment
- Customer health scoring
- Customer classification
- Incremental ETL processing
- Data quality monitoring
- Executive reporting

## Business Problem

Customer data currently exists across disconnected systems, causing duplicate records, inconsistent customer information, inaccurate reporting, weak health measurement, and unreliable segmentation.

Source systems include:

- Salesforce CRM
- Marketing automation platform, specifically Marketo
- Customer support system, specifically Zendesk
- Product usage platform / application logs
- Licensing system
- Partner management system, specifically Impartner

The organization needs a unified Customer 360 solution and a trusted customer profile.

## Business Goals

- Create a single source of truth for customers.
- Identify duplicate customers across systems.
- Generate golden customer records.
- Enrich customer profiles using behavioral and operational metrics.
- Classify customers based on risk and engagement.
- Provide actionable dashboards.

## Success Metrics

| Metric | Target |
| --- | --- |
| Duplicate reduction | >35% |
| Match accuracy | >95% |
| Customer coverage | >98% |
| ETL runtime reduction | >70% |
| Dashboard load time | <5 seconds |
| Data quality score | >95% |

## Technology Stack

| Capability | Technology |
| --- | --- |
| Data warehouse | Snowflake |
| Programming | Python 3.11+ |
| Entity resolution | Splink |
| Orchestration | Apache Airflow |
| Transformation | dbt |
| Data validation | Great Expectations |
| Visualization | Domo |
| CI/CD | GitHub Actions |
| Infrastructure | Docker |

## High-Level Architecture

Flow:

Source Systems -> Landing Layer -> Bronze Layer -> Silver Layer -> Splink Matching Engine -> Golden Customer Layer -> Customer Enrichment Layer -> Analytics Layer -> Domo Dashboards

## Source System Fields

### Salesforce CRM

- `customer_id`
- `company_name`
- `email`
- `phone`
- `industry`
- `created_date`

### Marketo

- `lead_id`
- `email`
- `campaign`
- `engagement_score`

### Zendesk

- `ticket_count`
- `satisfaction_score`
- `response_time`

### Product Usage / Application Logs

- `login_count`
- `active_days`
- `feature_usage`

### License Management System

- `license_type`
- `expiration_date`
- `renewal_status`

### Impartner

- `partner_id`
- `partner_tier`
- `certifications`
- `partner_region`

## Expected Repository Structure

```text
customer360-platform/
├── docs/
│   ├── architecture.md
│   ├── data_dictionary.md
│   └── onboarding.md
├── configs/
│   ├── dev.yaml
│   ├── test.yaml
│   └── prod.yaml
├── data/
│   ├── raw/
│   ├── processed/
│   └── reference/
├── airflow/
│   ├── dags/
│   └── plugins/
├── pipelines/
│   ├── ingestion/
│   ├── cleansing/
│   ├── enrichment/
│   ├── matching/
│   └── classification/
├── dbt/
│   ├── models/
│   ├── snapshots/
│   └── tests/
├── sql/
│   ├── bronze/
│   ├── silver/
│   ├── gold/
│   └── analytics/
├── tests/
├── dashboards/
├── notebooks/
├── Dockerfile
├── requirements.txt
└── README.md
```

## Snowflake Architecture

Database: `CUSTOMER360_DB`

Schemas:

- `LANDING`: raw files
- `BRONZE`: raw ingested tables
- `SILVER`: cleaned and standardized data
- `GOLD`: golden customer records
- `ANALYTICS`: business reporting tables

## Bronze Layer Requirements

Store source data exactly as received.

Requirements:

- No transformations
- Audit columns
- Load timestamp
- Source system indicator

Example table: `salesforce_customer_bronze`

## Silver Layer Requirements

Perform standardization.

Required transformations:

- Names: convert to uppercase.
- Email: trim whitespace and lowercase values.
- Phone: normalize formats.
- Address: standardize abbreviations such as `Street -> ST`, `Road -> RD`, and `Avenue -> AVE`.

## Splink Entity Resolution

Use Splink for probabilistic matching.

Matching attributes:

- Company name
- Email
- Phone
- Address
- Website domain

Blocking rules:

- `l.email = r.email`
- `l.phone = r.phone`
- `l.company_name = r.company_name`

Comparison methods:

- Exact match
- Jaro-Winkler
- Levenshtein distance

Expected outputs:

- Match probability
- Cluster ID
- Confidence score

## Golden Customer Record Logic

For each customer cluster, select:

- Most recent email
- Most recent phone
- Most complete address
- Highest-confidence company name

Create table: `gold_customer_master`

Columns:

- `golden_customer_id`
- `source_customer_ids`
- `company_name`
- `email`
- `phone`
- `address`
- `confidence_score`

## Customer Enrichment

Generate derived metrics.

### Customer Lifetime Value

Revenue generated by the customer.

### Engagement Score

Formula:

```text
(0.4 * Product Usage) + (0.3 * Marketing Engagement) + (0.3 * Support Activity)
```

### Adoption Score

Based on:

- Feature utilization
- Active users
- Login frequency

### Renewal Probability

Predict likelihood of renewal.

## Customer Classification

Build a classification model.

Target classes:

- `Healthy`: high engagement, high adoption, low support issues.
- `At Risk`: medium engagement, declining activity.
- `Churn Risk`: low engagement, low usage, negative support trends.

Candidate algorithms:

- Logistic Regression
- Random Forest
- XGBoost

Store outputs in: `customer_health_scores`

## Incremental ETL Framework

All pipelines must support CDC using `last_modified_timestamp`.

Workflow:

1. Extract new records.
2. Extract updated records.
3. Merge into target tables.
4. Maintain audit history.

## Data Quality Framework

Use Great Expectations.

Rules:

- Completeness: required fields cannot be null.
- Uniqueness: customer IDs must be unique.
- Validity: emails must be valid.
- Consistency: state abbreviations must be standardized.
- Timeliness: data freshness must be less than 24 hours.

## Data Lineage

Track:

- Source table
- Transformation step
- Destination table
- Execution timestamp

Store metadata in: `etl_audit_log`

## Domo Dashboards

### Executive Dashboard

Metrics:

- Total customers
- New customers
- Active customers
- Revenue
- Churn risk customers

### Customer Success Dashboard

Metrics:

- Health scores
- Renewal probability
- Product adoption
- Support trends

### Partner Dashboard

Metrics:

- Partner count
- Partner tier distribution
- Regional performance
- Certification status

## Airflow DAG Requirements

### `customer_ingestion_dag`

Frequency: hourly

Tasks:

- Extract
- Load Bronze

### `customer_standardization_dag`

Frequency: hourly

Tasks:

- Bronze to Silver

### `customer_matching_dag`

Frequency: daily

Tasks:

- Splink matching
- Golden record generation

### `customer_enrichment_dag`

Frequency: daily

Tasks:

- Enrichment
- Classification

### `dashboard_refresh_dag`

Frequency: not fully visible in extracted PDF context.

## Required Tests

- ETL validation
- Matching validation
- Enrichment validation
- Classification validation
- Data quality validation

## Performance Targets

- Daily volume: 5 million records
- Target runtime: <60 minutes
- Matching runtime: <20 minutes
- Dashboard refresh: <5 minutes

## Deliverables

1. Snowflake DDL scripts
2. Python ETL framework
3. Splink matching engine
4. Airflow DAGs
5. dbt models
6. Great Expectations suite
7. Domo dashboards
8. CI/CD pipeline
9. Architecture documentation
10. Deployment guide

## Acceptance Criteria

The project is complete when:

- Customer matching accuracy exceeds 95%.
- Duplicate reduction exceeds 35%.
- Data quality score exceeds 95%.
- Dashboard refresh completes successfully.
- End-to-end pipeline completes within SLA.
- Golden customer records are generated daily.
- Customer classifications are available for reporting.

## Extraction Notes

The PDF text was successfully extracted for pages 1-13 and 15-16. Pages 14 and 17-21 appeared blank in the extracted text. The dashboard refresh DAG frequency line was cut off in the extracted text, but the performance target specifies dashboard refresh should complete in less than 5 minutes.
