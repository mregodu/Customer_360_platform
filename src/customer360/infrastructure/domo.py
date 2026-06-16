"""Domo publishing adapter."""

from __future__ import annotations

import csv
import io
import os
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from customer360.config import DomoConfig


class DomoPublisher:
    """Publishes curated analytics datasets to Domo."""

    def __init__(
        self,
        *,
        api_host: str = "https://api.domo.com",
        client_id: str | None = None,
        client_secret: str | None = None,
        access_token: str | None = None,
        timeout_seconds: int = 30,
        session: Any | None = None,
        dry_run: bool = False,
    ) -> None:
        self._api_host = api_host.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = access_token
        self._timeout_seconds = timeout_seconds
        self._session = session
        self._dry_run = dry_run

    @classmethod
    def from_config(cls, config: DomoConfig) -> DomoPublisher:
        """Build a Domo publisher from validated platform configuration."""
        credentials = config.credential_payload()
        return cls(
            api_host=str(config.api_host),
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            access_token=credentials.get("access_token"),
            timeout_seconds=config.timeout_seconds,
            dry_run=_truthy(os.getenv("CUSTOMER360_DOMO_DRY_RUN")),
        )

    def publish_dataset(self, dataset_name: str, rows: Sequence[Mapping[str, object]]) -> str:
        """Publish a Domo dataset and return its identifier."""
        dataset_id = self._dataset_id_from_env(dataset_name)
        if self._dry_run:
            return dataset_id or f"dry-run:{dataset_name}"
        if dataset_id is None:
            raise RuntimeError(
                f"Missing Domo dataset id for {dataset_name!r}. "
                f"Set {self._dataset_id_env_name(dataset_name)} to publish from Airflow."
            )
        payload = _rows_to_csv(rows)
        self._put_dataset_data(dataset_id, payload)
        return dataset_id

    def _put_dataset_data(self, dataset_id: str, payload: str) -> None:
        session = self._requests_session()
        response = session.put(
            f"{self._api_host}/v1/datasets/{dataset_id}/data",
            headers={
                "Authorization": f"Bearer {self._resolve_access_token()}",
                "Content-Type": "text/csv",
            },
            data=payload,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()

    def _resolve_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        if not self._client_id or not self._client_secret:
            raise RuntimeError("Domo client_id and client_secret are required to request a token.")
        session = self._requests_session()
        response = session.get(
            f"{self._api_host}/oauth/token",
            params={"grant_type": "client_credentials", "scope": "data"},
            auth=(self._client_id, self._client_secret),
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Domo OAuth response did not include an access_token.")
        self._access_token = token
        return token

    def _requests_session(self) -> Any:
        if self._session is not None:
            return self._session
        try:
            import requests
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on runtime extras
            raise RuntimeError("requests is required for Domo publishing.") from exc
        self._session = requests.Session()
        return self._session

    def _dataset_id_from_env(self, dataset_name: str) -> str | None:
        return os.getenv(self._dataset_id_env_name(dataset_name))

    def _dataset_id_env_name(self, dataset_name: str) -> str:
        normalized = "".join(
            character if character.isalnum() else "_"
            for character in dataset_name.upper()
        )
        return f"DOMO_DATASET_ID_{normalized}"


def _rows_to_csv(rows: Sequence[Mapping[str, object]]) -> str:
    output = io.StringIO()
    fieldnames = _fieldnames(rows)
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})
    return output.getvalue()


def _fieldnames(rows: Sequence[Mapping[str, object]]) -> list[str]:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field_name in row:
            if field_name not in seen:
                seen.add(field_name)
                fieldnames.append(field_name)
    return fieldnames


def _csv_value(value: object) -> object:
    if isinstance(value, dict | list | tuple):
        return str(value)
    return value


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y"}
