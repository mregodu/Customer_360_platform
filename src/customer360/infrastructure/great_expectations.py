"""Great Expectations validation adapter."""

from __future__ import annotations


class GreatExpectationsRunner:
    """Runs table-level quality checks before data moves downstream."""

    def validate_table(self, table_name: str) -> bool:
        """Validate a table against its configured expectation suite."""
        raise NotImplementedError(f"Great Expectations checkpoint is not wired yet for {table_name=}.")
