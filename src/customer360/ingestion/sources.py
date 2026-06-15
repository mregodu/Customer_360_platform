"""Source extractors for CSV and API-based ingestion."""

from __future__ import annotations

import csv
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin

import requests

from customer360.config import ApiSourceConfig, CsvSourceConfig, IngestionSourceConfig
from customer360.ingestion.exceptions import SourceExtractionError

IngestionRecord = dict[str, object]


class HttpResponse(Protocol):
    """Minimal HTTP response contract used by API extraction."""

    status_code: int
    text: str

    def json(self) -> object:
        """Return the response JSON payload."""


class HttpSession(Protocol):
    """Minimal HTTP session contract implemented by requests.Session."""

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        params: Mapping[str, object],
        timeout: int,
    ) -> HttpResponse:
        """Execute a GET request."""

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout: int,
    ) -> HttpResponse:
        """Execute a POST request."""


class SourceExtractor(Protocol):
    """Extracts changed records from an upstream source."""

    @property
    def source_name(self) -> str:
        """Return the logical source name."""

    def extract(self, since_watermark: str | None, batch_size: int) -> Iterator[list[IngestionRecord]]:
        """Yield changed records in batches."""


class CsvSourceExtractor:
    """Extract records from a CSV file or glob path."""

    def __init__(self, source_name: str, source_config: IngestionSourceConfig) -> None:
        if source_config.csv is None:
            raise SourceExtractionError(f"CSV source {source_name!r} is missing csv configuration.")
        self._source_name = source_name
        self._source_config = source_config
        self._csv_config = source_config.csv

    @property
    def source_name(self) -> str:
        """Return the logical source name."""
        return self._source_name

    def extract(self, since_watermark: str | None, batch_size: int) -> Iterator[list[IngestionRecord]]:
        """Yield CSV records changed after the current watermark."""
        batch: list[IngestionRecord] = []
        for path in _resolve_csv_paths(self._csv_config):
            with path.open("r", encoding=self._csv_config.encoding, newline="") as handle:
                reader = csv.DictReader(handle, delimiter=self._csv_config.delimiter)
                for row in reader:
                    record = {key: value for key, value in row.items() if key is not None}
                    if _is_incremental_record(
                        record,
                        self._source_config.watermark_column,
                        since_watermark,
                    ):
                        batch.append(record)
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
        if batch:
            yield batch


class ApiSourceExtractor:
    """Extract records from a paginated HTTP API."""

    def __init__(
        self,
        source_name: str,
        source_config: IngestionSourceConfig,
        session: HttpSession | None = None,
    ) -> None:
        if source_config.api is None:
            raise SourceExtractionError(f"API source {source_name!r} is missing api configuration.")
        self._source_name = source_name
        self._source_config = source_config
        self._api_config = source_config.api
        self._session = session or requests.Session()

    @property
    def source_name(self) -> str:
        """Return the logical source name."""
        return self._source_name

    def extract(self, since_watermark: str | None, batch_size: int) -> Iterator[list[IngestionRecord]]:
        """Yield API records changed after the current watermark."""
        page = 1
        offset = 0
        cursor: str | None = None
        batch: list[IngestionRecord] = []

        while True:
            payload = self._request_page(
                since_watermark=since_watermark,
                page=page,
                offset=offset,
                cursor=cursor,
            )
            records = _extract_path(payload, self._api_config.records_path)
            if not isinstance(records, list):
                raise SourceExtractionError(
                    f"API source {self.source_name!r} returned non-list records at "
                    f"path {self._api_config.records_path!r}."
                )

            for item in records:
                if isinstance(item, Mapping):
                    batch.append(dict(item))
                else:
                    batch.append({"value": item})
                if len(batch) >= batch_size:
                    yield batch
                    batch = []

            next_cursor = _next_cursor(payload, self._api_config)
            if not _has_next_page(self._api_config, records, next_cursor):
                break

            if self._api_config.pagination_strategy == "cursor":
                cursor = next_cursor
            elif self._api_config.pagination_strategy == "page":
                page += 1
            elif self._api_config.pagination_strategy == "offset":
                offset += self._api_config.page_size
            else:
                break

        if batch:
            yield batch

    def _request_page(
        self,
        *,
        since_watermark: str | None,
        page: int,
        offset: int,
        cursor: str | None,
    ) -> dict[str, object]:
        config = self._api_config
        params: dict[str, object] = dict(config.static_params)
        params[config.limit_param] = config.page_size

        if since_watermark is not None:
            params[config.watermark_param] = since_watermark
        if config.pagination_strategy == "page":
            params[config.page_param] = page
            params[config.page_size_param] = config.page_size
        elif config.pagination_strategy == "offset":
            params[config.offset_param] = offset
        elif config.pagination_strategy == "cursor" and cursor:
            params[config.cursor_param] = cursor

        headers = dict(config.static_headers)
        if config.auth_token is not None:
            headers[config.auth_header] = (
                f"{config.auth_scheme} {config.auth_token.get_secret_value()}".strip()
            )

        url = urljoin(str(config.base_url), config.endpoint)
        if config.method == "GET":
            response = self._session.get(
                url,
                headers=headers,
                params=params,
                timeout=config.timeout_seconds,
            )
        else:
            response = self._session.post(
                url,
                headers=headers,
                json=params,
                timeout=config.timeout_seconds,
            )

        if response.status_code >= 400:
            raise SourceExtractionError(
                f"API source {self.source_name!r} failed with status "
                f"{response.status_code}: {response.text[:500]}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise SourceExtractionError(f"API source {self.source_name!r} returned non-object JSON.")
        return payload


def build_source_extractor(
    source_name: str,
    source_config: IngestionSourceConfig,
) -> SourceExtractor:
    """Build a source extractor from validated source configuration."""
    if source_config.source_type == "csv":
        return CsvSourceExtractor(source_name, source_config)
    return ApiSourceExtractor(source_name, source_config)


def _resolve_csv_paths(config: CsvSourceConfig) -> list[Path]:
    path = Path(config.path)
    if any(char in config.path for char in ("*", "?", "[")):
        paths = sorted(Path().glob(config.path))
    elif path.is_dir():
        paths = sorted(path.glob("*.csv"))
    else:
        paths = [path]

    missing = [item for item in paths if not item.exists()]
    if missing:
        raise SourceExtractionError(f"CSV source file not found: {missing[0]}")
    return paths


def _is_incremental_record(
    record: Mapping[str, object],
    watermark_column: str,
    since_watermark: str | None,
) -> bool:
    if since_watermark is None:
        return True
    value = record.get(watermark_column)
    if value is None:
        return True
    return str(value) > since_watermark


def _extract_path(payload: Mapping[str, object], path: str) -> object:
    current: object = payload
    for part in path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _next_cursor(payload: Mapping[str, object], config: ApiSourceConfig) -> str | None:
    if config.next_page_token_path is None:
        return None
    value = _extract_path(payload, config.next_page_token_path)
    if value is None:
        return None
    return str(value)


def _has_next_page(
    config: ApiSourceConfig,
    records: list[object],
    next_cursor: str | None,
) -> bool:
    if config.pagination_strategy == "none":
        return False
    if config.pagination_strategy == "cursor":
        return bool(next_cursor)
    return len(records) >= config.page_size
