from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pytest

from customer360.config import IngestionSourceConfig, RetryConfig
from customer360.ingestion.exceptions import SourceExtractionError
from customer360.ingestion.retry import RetryPolicy, retry_call
from customer360.ingestion.service import IngestionService
from customer360.ingestion.sources import ApiSourceExtractor, CsvSourceExtractor
from customer360.ingestion.watermarks import InMemoryWatermarkStore


class FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> object:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        params: Mapping[str, object],
        timeout: int,
    ) -> FakeResponse:
        self.calls.append(
            {"method": "GET", "url": url, "headers": dict(headers), "params": dict(params), "timeout": timeout}
        )
        return self.responses.pop(0)

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout: int,
    ) -> FakeResponse:
        self.calls.append(
            {"method": "POST", "url": url, "headers": dict(headers), "json": dict(json), "timeout": timeout}
        )
        return self.responses.pop(0)


class StaticSource:
    def __init__(self, batches: list[list[dict[str, object]]]) -> None:
        self._batches = batches

    @property
    def source_name(self) -> str:
        return "static"

    def extract(self, since_watermark: str | None, batch_size: int) -> Any:
        assert batch_size == 5
        assert since_watermark is None
        yield from self._batches


class RecordingLoader:
    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []

    def write_records(self, table_name: str, records: Iterable[Mapping[str, object]]) -> int:
        materialized = [dict(record) for record in records]
        self.rows.extend({"table_name": table_name, **row} for row in materialized)
        return len(materialized)


def test_csv_source_reads_directory_and_batches_incremental_records(tmp_path: Path) -> None:
    source_dir = tmp_path / "extracts"
    source_dir.mkdir()
    (source_dir / "a.csv").write_text(
        "customer_id,last_modified_timestamp\nold,2024-01-01T00:00:00\nnew-1,2024-01-02T00:00:00\n",
        encoding="utf-8",
    )
    (source_dir / "b.csv").write_text(
        "customer_id,last_modified_timestamp\nnew-2,2024-01-03T00:00:00\n",
        encoding="utf-8",
    )

    extractor = CsvSourceExtractor("salesforce", _csv_config(source_dir))

    batches = list(extractor.extract("2024-01-01T00:00:00", batch_size=1))

    assert batches == [
        [{"customer_id": "new-1", "last_modified_timestamp": "2024-01-02T00:00:00"}],
        [{"customer_id": "new-2", "last_modified_timestamp": "2024-01-03T00:00:00"}],
    ]


def test_api_source_supports_cursor_pagination_and_nested_records_path() -> None:
    config = _api_config(
        {
            "pagination_strategy": "cursor",
            "records_path": "payload.records",
            "next_page_token_path": "payload.next",
            "cursor_param": "after",
            "watermark_param": "updated_after",
        }
    )
    session = FakeSession(
        [
            FakeResponse({"payload": {"records": [{"id": "1"}], "next": "cursor-2"}}),
            FakeResponse({"payload": {"records": [{"id": "2"}]}}),
        ]
    )

    batches = list(ApiSourceExtractor("source", config, session=session).extract("2024-01-01", 10))

    assert batches == [[{"id": "1"}, {"id": "2"}]]
    assert session.calls[0]["params"] == {"limit": 1000, "updated_after": "2024-01-01"}
    assert session.calls[1]["params"] == {"limit": 1000, "updated_after": "2024-01-01", "after": "cursor-2"}


def test_api_source_supports_post_and_offset_pagination() -> None:
    config = _api_config({"method": "POST", "pagination_strategy": "offset", "page_size": 2})
    session = FakeSession(
        [
            FakeResponse({"data": [{"id": "1"}, {"id": "2"}]}),
            FakeResponse({"data": [{"id": "3"}]}),
        ]
    )

    batches = list(ApiSourceExtractor("source", config, session=session).extract(None, 2))

    assert batches == [[{"id": "1"}, {"id": "2"}], [{"id": "3"}]]
    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["json"] == {"limit": 2, "offset": 0}
    assert session.calls[1]["json"] == {"limit": 2, "offset": 2}


def test_api_source_raises_clear_error_for_http_failure() -> None:
    extractor = ApiSourceExtractor("source", _api_config({}), session=FakeSession([FakeResponse({"error": "no"}, 503)]))

    with pytest.raises(SourceExtractionError, match="503"):
        list(extractor.extract(None, 10))


def test_api_source_raises_when_records_path_is_not_a_list() -> None:
    extractor = ApiSourceExtractor("source", _api_config({}), session=FakeSession([FakeResponse({"data": {"id": "1"}})]))

    with pytest.raises(SourceExtractionError, match="non-list records"):
        list(extractor.extract(None, 10))


def test_ingestion_service_skips_disabled_source() -> None:
    config = _csv_config(Path("unused.csv"), enabled=False)
    service = IngestionService(
        source_configs={"salesforce": config},
        sources={"salesforce": StaticSource([])},
        loader=RecordingLoader(),
        watermarks=InMemoryWatermarkStore(),
        default_batch_size=5,
    )

    result = service.ingest_source("salesforce")

    assert result.status == "SKIPPED"
    assert result.rows_loaded == 0


def test_ingestion_service_ingests_all_sources_with_prepared_bronze_rows() -> None:
    loader = RecordingLoader()
    config = _csv_config(Path("unused.csv"))
    service = IngestionService(
        source_configs={"salesforce": config},
        sources={"salesforce": StaticSource([[{"customer_id": "001", "last_modified_timestamp": "2024-01-01"}]])},
        loader=loader,
        watermarks=InMemoryWatermarkStore(),
        default_batch_size=5,
    )

    results = service.ingest_all()

    assert [result.status for result in results] == ["SUCCESS"]
    assert loader.rows[0]["table_name"] == "CUSTOMER360_DB.BRONZE.salesforce_customer_bronze"
    assert loader.rows[0]["source_record_id"] == "001"
    assert isinstance(loader.rows[0]["raw_payload"], dict)


def test_retry_policy_from_config_and_backoff_sequence() -> None:
    policy = RetryPolicy.from_config(
        RetryConfig.model_validate(
            {
                "max_attempts": 3,
                "initial_delay_seconds": 1,
                "max_delay_seconds": 3,
                "backoff_multiplier": 2,
                "retryable_status_codes": [503],
            }
        )
    )
    sleeps: list[float] = []
    attempts = 0

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("transient")
        return "done"

    result = retry_call(
        operation,
        policy=policy,
        operation_name="test",
        logger=logging.getLogger("tests.ingestion"),
        sleep=sleeps.append,
    )

    assert result == "done"
    assert sleeps == [1, 2]


def _csv_config(path: Path, *, enabled: bool = True) -> IngestionSourceConfig:
    return IngestionSourceConfig.model_validate(
        {
            "enabled": enabled,
            "source_system": "SALESFORCE",
            "source_object": "ACCOUNT",
            "source_type": "csv",
            "target_table": "CUSTOMER360_DB.BRONZE.salesforce_customer_bronze",
            "primary_key": "customer_id",
            "watermark_column": "last_modified_timestamp",
            "batch_size": 5,
            "csv": {"path": str(path)},
        }
    )


def _api_config(overrides: Mapping[str, object]) -> IngestionSourceConfig:
    payload: dict[str, object] = {
        "source_system": "PRODUCT_USAGE",
        "source_object": "USAGE_DAILY",
        "source_type": "api",
        "target_table": "CUSTOMER360_DB.BRONZE.product_usage_bronze",
        "primary_key": "id",
        "watermark_column": "updated_at",
        "api": {
            "base_url": "https://api.example.com",
            "endpoint": "/v1/records",
            "auth_token": "token",
            "records_path": "data",
            "pagination_strategy": "none",
            **dict(overrides),
        },
    }
    return IngestionSourceConfig.model_validate(payload)
