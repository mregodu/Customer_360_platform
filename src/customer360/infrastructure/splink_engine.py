"""Splink entity-resolution adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from customer360.domain.customer import SourceCustomerRecord


class SplinkEntityResolutionEngine:
    """Runs probabilistic customer matching with Splink."""

    def predict_clusters(self, records: Sequence[SourceCustomerRecord]) -> Sequence[Mapping[str, object]]:
        """Return match predictions for source records.

        The implementation will configure Splink comparisons for company name,
        email, phone, address, and website domain as described in `CONTEXT.md`.
        """
        raise NotImplementedError(f"Splink matching is not wired yet for records={len(records)}.")
