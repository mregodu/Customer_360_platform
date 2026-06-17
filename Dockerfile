# Production-ready Python image for local orchestration, CI validation, and Airflow jobs.
FROM python:3.11-slim AS runtime

ARG AIRFLOW_UID=50000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app \
    AIRFLOW_HOME=/opt/airflow \
    PYTHONPATH=/app/src \
    PATH=/home/airflow/.local/bin:${PATH}

WORKDIR ${APP_HOME}

# System dependencies support Snowflake, dbt, Airflow metadata DB drivers, and Python wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl git libpq-dev \
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
COPY docker ./docker

RUN mkdir -p ${AIRFLOW_HOME}/dags ${AIRFLOW_HOME}/logs ${AIRFLOW_HOME}/plugins \
    && useradd --uid "${AIRFLOW_UID}" --gid 0 --home-dir /home/airflow --create-home airflow \
    && chown -R "${AIRFLOW_UID}:0" ${APP_HOME} ${AIRFLOW_HOME} /home/airflow \
    && chmod -R g=u ${APP_HOME} ${AIRFLOW_HOME} /home/airflow \
    && chmod +x ${APP_HOME}/docker/*.sh

USER ${AIRFLOW_UID}:0

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD customer360 healthcheck || exit 1

CMD ["customer360", "healthcheck"]
