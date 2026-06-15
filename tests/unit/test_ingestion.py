from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pytest

from customer360.config import IngestionSourceConfig
from customer360.ingestion.exceptions import IngestionRunError
from customer360.ingestion.retry import RetryPolicy
from customer360.ingestion.service import IngestionService
from customer360.ingestion.sources import ApiSourceExtractor, CsvSourceExtractor
from customer360.ingestion.watermarks import InMemoryWatermarkStore


class RecordingLoader:
    def __init__(self, fail_attempts: int = 0) -> None:
        self.fail_attempts = fail_attempts
        self.attempts = 0
        self.records: list[dict[str, object]] = []
        self.tables: list[str] = []

    def write_records(self, table_name: str, records: Iterable[Mapping[str, object]]) -> int:
        self.attempts += 1
        if self.attempts <= self.fail_attempts:
            raise RuntimeError("temporary warehouse failure")
        rows = [dict(record) for record in records]
        self.records.extend(rows)
        self.tables.append(table_name)
        return len(rows)


class FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> dict[str, object]:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        params: Mapping[str, object],
        timeout: int,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "params": dict(params),
                "timeout": timeout,
            }
        )
        return self._responses.pop(0)

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout: int,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "json": dict(json),
                "timeout": timeout,
            }
        )
        return self._responses.pop(0)


def test_csv_ingestion_filters_incremental_rows_and_updates_watermark(tmp_path: Path) -> None:
    source_file = tmp_path / "salesforce.csv"
    source_file.write_text(
        "customer_id,company_name,last_modified_timestamp\n"
        "old,Old Co,2024-01-01T00:00:00\n"
        "new,New Co,2024-01-02T00:00:00\n",
        encoding="utf-8",
    )
    source_config = _csv_config(source_file)
    loader = RecordingLoader()
    watermarks = InMemoryWatermarkStore(
        {("SALESFORCE", "ACCOUNT"): "2024-01-01T00:00:00"}
    )
    service = IngestionService(
        source_configs={"salesforce": source_config},
        sources={"salesforce": CsvSourceExtractor("salesforce", source_config)},
        loader=loader,
        watermarks=watermarks,
        retry_policy=RetryPolicy(max_attempts=1),
        default_batch_size=10,
    )

    result = service.ingest_source("salesforce")

    assert result.status == "SUCCESS"
    assert result.rows_extracted == 1
    assert result.rows_loaded == 1
    assert result.new_watermark == "2024-01-02T00:00:00"
    assert watermarks.get_watermark("SALESFORCE", "ACCOUNT") == "2024-01-02T00:00:00"
    assert loader.records[0]["source_record_id"] == "new"
    assert loader.records[0]["source_system"] == "SALESFORCE"
    assert loader.records[0]["raw_payload"] == {
        "customer_id": "new",
        "company_name": "New Co",
        "last_modified_timestamp": "2024-01-02T00:00:00",
    }


def test_ingestion_retries_transient_bronze_load_failures(tmp_path: Path) -> None:
    source_file = tmp_path / "salesforce.csv"
    source_file.write_text(
        "customer_id,company_name,last_modified_timestamp\n"
        "cust-1,Acme,2024-01-02T00:00:00\n",
        encoding="utf-8",
    )
    source_config = _csv_config(source_file)
    loader = RecordingLoader(fail_attempts=1)
    service = IngestionService(
        source_configs={"salesforce": source_config},
        sources={"salesforce": CsvSourceExtractor("salesforce", source_config)},
        loader=loader,
        watermarks=InMemoryWatermarkStore(),
        retry_policy=RetryPolicy(max_attempts=2, initial_delay_seconds=0),
        default_batch_size=10,
    )

    result = service.ingest_source("salesforce")

    assert result.status == "SUCCESS"
    assert loader.attempts == 2
    assert result.rows_loaded == 1


def test_ingestion_can_return_failed_result_without_raising(tmp_path: Path) -> None:
    source_config = _csv_config(tmp_path / "missing.csv")
    service = IngestionService(
        source_configs={"salesforce": source_config},
        sources={"salesforce": CsvSourceExtractor("salesforce", source_config)},
        loader=RecordingLoader(),
        watermarks=InMemoryWatermarkStore(),
        retry_policy=RetryPolicy(max_attempts=1),
        default_batch_size=10,
    )

    result = service.ingest_source("salesforce", raise_on_error=False)

    assert result.status == "FAILED"
    assert "CSV source file not found" in str(result.error_message)


def test_ingestion_raises_contextual_error_by_default(tmp_path: Path) -> None:
    source_config = _csv_config(tmp_path / "missing.csv")
    service = IngestionService(
        source_configs={"salesforce": source_config},
        sources={"salesforce": CsvSourceExtractor("salesforce", source_config)},
        loader=RecordingLoader(),
        watermarks=InMemoryWatermarkStore(),
        retry_policy=RetryPolicy(max_attempts=1),
        default_batch_size=10,
    )

    with pytest.raises(IngestionRunError, match="salesforce"):
        service.ingest_source("salesforce")


def test_api_source_extracts_paginated_records() -> None:
    source_config = IngestionSourceConfig.model_validate(
        {
            "source_system": "PRODUCT_USAGE",
            "source_object": "USAGE_DAILY",
            "source_type": "api",
            "target_table": "CUSTOMER360_DB.BRONZE.product_usage_bronze",
            "primary_key": "usage_event_id",
            "watermark_column": "last_modified_timestamp",
            "api": {
                "base_url": "https://usage.example.com",
                "endpoint": "/v1/usage",
                "auth_token": "token",
                "records_path": "data",
                "pagination_strategy": "page",
                "page_size": 2,
            },
        }
    )
    session = FakeSession(
        [
            FakeResponse({"data": [{"usage_event_id": "1"}, {"usage_event_id": "2"}]}),
            FakeResponse({"data": [{"usage_event_id": "3"}]}),
        ]
    )
    source = ApiSourceExtractor("product_usage", source_config, session=session)

    batches = list(source.extract("2024-01-01T00:00:00", batch_size=10))

    assert batches == [[{"usage_event_id": "1"}, {"usage_event_id": "2"}, {"usage_event_id": "3"}]]
    assert session.calls[0]["params"]["page"] == 1
    assert session.calls[1]["params"]["page"] == 2
    assert session.calls[0]["headers"]["Authorization"] == "Bearer token"


def _csv_config(path: Path) -> IngestionSourceConfig:
    return IngestionSourceConfig.model_validate(
        {
            "source_system": "SALESFORCE",
            "source_object": "ACCOUNT",
            "source_type": "csv",
            "target_table": "CUSTOMER360_DB.BRONZE.salesforce_customer_bronze",
            "primary_key": "customer_id",
            "watermark_column": "last_modified_timestamp",
            "csv": {"path": str(path)},
        }
    )
