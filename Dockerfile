# Production-ready Python image for local orchestration, CI validation, and containerized jobs.
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# System dependencies support Snowflake, dbt, and common Python build wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install -e .

COPY configs ./configs
COPY airflow ./airflow
COPY dbt ./dbt
COPY great_expectations ./great_expectations
COPY sql ./sql

CMD ["customer360", "healthcheck"]
