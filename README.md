# Customer 360 Data Enrichment Platform

Enterprise-grade starter repository for a Customer 360 platform that consolidates CRM, marketing, support, product usage, licensing, and partner data into trusted golden customer profiles.

## What This Platform Does

- Ingests source-system customer data into Snowflake landing and bronze layers.
- Cleanses and standardizes records into a silver layer.
- Uses Splink for probabilistic entity resolution and duplicate detection.
- Generates golden customer records in the gold layer.
- Enriches customer profiles with lifetime value, product adoption, engagement,
  support health, and renewal probability metrics.
- Classifies customers as `Healthy`, `At Risk`, or `Churn Risk` using Logistic
  Regression, Random Forest, or XGBoost scoring pipelines.
- Validates quality with Great Expectations.
- Orchestrates pipelines with Airflow.
- Serves analytics tables and Domo dashboard extracts.

## Folder Guide

Every major folder includes a `README.md` explaining its purpose and ownership boundaries.

```text
.github/              CI/CD workflows for tests, linting, image builds, and deployment gates.
airflow/              Airflow DAGs and plugins that orchestrate ingestion, dbt, matching, and dashboard refreshes.
configs/              Environment-specific YAML configuration with no secrets committed.
dashboards/           Domo dashboard specs, dataset contracts, and operational dashboard documentation.
data/                 Local-only sample/reference data zones; production data belongs in Snowflake.
dbt/                  dbt project for Snowflake transformations across bronze, silver, gold, and analytics layers.
docs/                 Architecture, onboarding, data dictionary, runbooks, and design records.
great_expectations/   Data quality suites, checkpoints, and custom validation plugins.
notebooks/            Exploratory notebooks; production logic must graduate into src/ modules.
sql/                  Snowflake DDL and administrative SQL organized by warehouse layer.
src/customer360/      Clean architecture Python package for domain, application, infrastructure, and interfaces.
tests/                Unit, integration, and fixture tests for Python, SQL contracts, and pipeline behavior.
```

## Clean Architecture

The Python package follows a dependency direction that keeps business logic portable:

- `domain`: business entities, value objects, and rules with no vendor dependencies.
- `application`: use cases and orchestration services that coordinate domain behavior.
- `infrastructure`: Snowflake, Domo, filesystem, and external service adapters.
- `interfaces`: CLIs and entrypoints used by humans, Airflow, and automation.
- business modules (`ingestion`, `cleansing`, `matching`, `golden`, `enrichment`, `classification`, `monitoring`) expose production use cases while delegating vendor-specific work to infrastructure adapters.

## Quick Start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
cp .env.example .env
customer360 healthcheck
pytest
```

## Configuration

Use `CUSTOMER360_CONFIG_PATH` to choose the active YAML config. Secrets must come from environment variables, Airflow connections, or a secret manager.

Default local config:

```bash
export CUSTOMER360_CONFIG_PATH=configs/dev.yaml
```

## Pipeline Layers

- `LANDING`: raw files staged before ingestion.
- `BRONZE`: raw tables loaded exactly as received with audit columns.
- `SILVER`: standardized and validated source tables.
- `GOLD`: golden customer master records and entity-resolution outputs.
- `ANALYTICS`: reporting-ready marts for Domo dashboards.

## Acceptance Targets

- Customer matching accuracy greater than 95%.
- Duplicate reduction greater than 35%.
- Data quality score greater than 95%.
- End-to-end daily pipeline runtime under 60 minutes.
- Matching runtime under 20 minutes.
- Dashboard refresh under 5 minutes.
