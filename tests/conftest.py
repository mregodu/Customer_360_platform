from __future__ import annotations

from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest

from customer360.domain.customer import SourceCustomerRecord


@pytest.fixture
def source_customer_factory() -> Any:
    def _factory(
        source_system: str = "SALESFORCE",
        source_customer_id: str = "001",
        *,
        company_name: str | None = "ACME INC",
        email: str | None = "hello@example.com",
        phone: str | None = "3125550101",
        website_domain: str | None = "acme.com",
        address: str | None = "12 MAIN ST CHICAGO IL",
    ) -> SourceCustomerRecord:
        return SourceCustomerRecord(
            source_system=source_system,
            source_customer_id=source_customer_id,
            company_name=company_name,
            email=email,
            phone=phone,
            website_domain=website_domain,
            address=address,
        )

    return _factory


@pytest.fixture
def health_training_records() -> list[dict[str, object]]:
    return [
        _health_record("gold-healthy-1", "Healthy", 0.92, 0.88, 0.85, 0.90, 0.95, "ACTIVE"),
        _health_record("gold-healthy-2", "Healthy", 0.86, 0.82, 0.78, 0.84, 0.90, "RENEWED"),
        _health_record("gold-healthy-3", "Healthy", 0.95, 0.90, 0.88, 0.91, 0.96, "AUTO_RENEW"),
        _health_record("gold-risk-1", "At Risk", 0.55, 0.50, 0.45, 0.52, 0.58, "PENDING"),
        _health_record("gold-risk-2", "At Risk", 0.48, 0.44, 0.50, 0.47, 0.50, "OPEN"),
        _health_record("gold-risk-3", "At Risk", 0.62, 0.58, 0.40, 0.56, 0.52, "IN_PROGRESS"),
        _health_record("gold-churn-1", "Churn Risk", 0.20, 0.18, 0.10, 0.20, 0.15, "AT_RISK"),
        _health_record("gold-churn-2", "Churn Risk", 0.15, 0.20, 0.15, 0.18, 0.10, "CANCELLED"),
        _health_record("gold-churn-3", "Churn Risk", 0.28, 0.24, 0.20, 0.25, 0.22, "EXPIRED"),
    ]


def _health_record(
    customer_id: str,
    health_class: str,
    product_usage: float,
    adoption: float,
    marketing: float,
    engagement: float,
    renewal_probability: float,
    renewal_status: str,
) -> dict[str, object]:
    support_health = max(0.1, min(1.0, (engagement + renewal_probability) / 2))
    return {
        "golden_customer_id": customer_id,
        "metric_date": "2024-04-01",
        "health_class": health_class,
        "company_name": customer_id.upper(),
        "lifetime_value": 10000 * renewal_probability,
        "product_usage_score": product_usage,
        "product_adoption_score": adoption,
        "marketing_engagement_score": marketing,
        "engagement_score": engagement,
        "support_health_score": support_health,
        "support_activity_score": support_health,
        "support_ticket_count": int((1 - support_health) * 25),
        "satisfaction_score": support_health * 5,
        "response_time_minutes": (1 - support_health) * 1440,
        "active_users": int(product_usage * 50),
        "active_days": int(product_usage * 30),
        "renewal_probability": renewal_probability,
        "renewal_status": renewal_status,
        "license_expiration_date": "2024-12-01",
        "contract_value": 10000 * renewal_probability,
    }


@dataclass
class FakeSnowflakeCursor:
    description: list[tuple[str]] = field(default_factory=list)
    rows: list[tuple[object, ...]] = field(default_factory=list)
    fail_on_execute_index: int | None = None
    fail_on_executemany: bool = False
    execute_calls: list[tuple[str, tuple[object, ...]]] = field(default_factory=list)
    executemany_calls: list[tuple[str, list[tuple[object, ...]]]] = field(default_factory=list)
    closed: bool = False

    def execute(self, sql: str, params: Iterable[object] = ()) -> None:
        call_index = len(self.execute_calls)
        self.execute_calls.append((sql, tuple(params)))
        if self.fail_on_execute_index is not None and call_index == self.fail_on_execute_index:
            raise RuntimeError("planned execute failure")

    def executemany(self, sql: str, rows: Iterable[Iterable[object]]) -> None:
        materialized = [tuple(row) for row in rows]
        self.executemany_calls.append((sql, materialized))
        if self.fail_on_executemany:
            raise RuntimeError("planned executemany failure")

    def fetchone(self) -> tuple[object, ...] | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows

    def close(self) -> None:
        self.closed = True


@dataclass
class FakeSnowflakeConnection:
    cursor_obj: FakeSnowflakeCursor
    commit_count: int = 0
    rollback_count: int = 0
    closed: bool = False

    def cursor(self) -> FakeSnowflakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1

    def close(self) -> None:
        self.closed = True


class FakeSnowflakeConnectionFactory:
    def __init__(self, connection: FakeSnowflakeConnection) -> None:
        self.connection = connection

    @contextmanager
    def connect(self) -> Any:
        yield self.connection


@pytest.fixture
def fake_snowflake_connection() -> FakeSnowflakeConnection:
    cursor = FakeSnowflakeCursor()
    return FakeSnowflakeConnection(cursor_obj=cursor)


@pytest.fixture
def fake_snowflake_factory_builder() -> Any:
    def _builder(
        *,
        description: list[tuple[str]] | None = None,
        rows: list[tuple[object, ...]] | None = None,
        fail_on_execute_index: int | None = None,
        fail_on_executemany: bool = False,
    ) -> tuple[FakeSnowflakeConnectionFactory, FakeSnowflakeConnection, FakeSnowflakeCursor]:
        cursor = FakeSnowflakeCursor(
            description=description or [],
            rows=rows or [],
            fail_on_execute_index=fail_on_execute_index,
            fail_on_executemany=fail_on_executemany,
        )
        connection = FakeSnowflakeConnection(cursor_obj=cursor)
        return FakeSnowflakeConnectionFactory(connection), connection, cursor

    return _builder


class RecordingWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def write_records(self, table_name: str, records: Iterable[Mapping[str, object]]) -> int:
        rows = [dict(record) for record in records]
        self.records.extend({"table_name": table_name, **row} for row in rows)
        return len(rows)
