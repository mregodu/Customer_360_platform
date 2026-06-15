"""Domo publishing adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


class DomoPublisher:
    """Publishes curated analytics datasets to Domo."""

    def publish_dataset(self, dataset_name: str, rows: Sequence[Mapping[str, object]]) -> str:
        """Publish a Domo dataset and return its identifier."""
        raise NotImplementedError(f"Domo publishing is not wired yet for {dataset_name=} rows={len(rows)}.")
